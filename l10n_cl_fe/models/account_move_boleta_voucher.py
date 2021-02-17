# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import dateutil.relativedelta as relativedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
import logging
_logger = logging.getLogger(__name__)

try:
    from io import BytesIO
except:
    _logger.warning("no se ha cargado io")
try:
    from facturacion_electronica import facturacion_electronica as fe
except Exception as e:
    _logger.warning("Problema al cargar Facturación electrónica: %s" % str(e))
try:
    import pdf417gen
except ImportError:
    _logger.warning('Cannot import pdf417gen library')
try:
    import base64
except ImportError:
    _logger.warning('Cannot import base64 library')


class SIIResumenBoletaVoucher(models.Model):
    _name = 'account.move.boleta_voucher'
    _description = "Resumen Mensual Boletas Electronica con pagos Electronico"

    @api.multi
    def get_barcode_img(self, columns=13, ratio=3):
        barcodefile = BytesIO()
        image = self.pdf417bc(self.sii_barcode, columns, ratio)
        image.save(barcodefile, 'PNG')
        data = barcodefile.getvalue()
        return base64.b64encode(data)

    def _get_barcode_img(self):
        for r in self:
            if r.sii_barcode:
                r.sii_barcode_img = r.get_barcode_img()

    sii_document_number = fields.Integer(
        string="Folio del Documento",
        copy=False,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    sii_xml_request = fields.Many2one(
        'sii.xml.envio',
        string='SII XML Request',
        copy=False,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('NoEnviado', 'No Enviado'),
            ('EnCola', 'En Cola'),
            ('Enviado', 'Enviado'),
            ('Aceptado', 'Aceptado'),
            ('Rechazado', 'Rechazado'),
            ('Reparo', 'Reparo'),
            ('Proceso', 'Proceso'),
            ('Reenviar', 'Reenviar'),
            ('Anulado', 'Anulado')],
        string='Resultado',
        index=True,
        readonly=True,
        default='draft',
        track_visibility='onchange',
        copy=False,
        help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed Invoice.\n"
             " * The 'Pro-forma' status is used the invoice does not have an invoice number.\n"
             " * The 'Open' status is used when user create invoice, an invoice number is generated. Its in open status till user does not pay invoice.\n"
             " * The 'Paid' status is set automatically when the invoice is paid. Its related journal entries may or may not be reconciled.\n"
             " * The 'Cancelled' status is used when user cancel invoice.")
    sii_barcode = fields.Char(
        copy=False,
        string=_('SII Barcode'),
        help='SII Barcode Name',
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    sii_barcode_img = fields.Binary(
        string=_('SII Barcode Image'),
        help='SII Barcode Image in PDF417 format',
        compute="_get_barcode_img",
    )
    sii_message = fields.Text(
            string='SII Message',
            copy=False,
        )
    sii_xml_dte = fields.Text(
        string='SII XML DTE',
        copy=False,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    move_ids = fields.Many2many(
        'account.move',
    	readonly=True,
        states={'draft': [('readonly', False)]},
    )
    fecha_emision = fields.Date(
        string="Fecha Emisión",
        readonly=True,
        states={'draft': [('readonly', False)]},
        default=lambda self: fields.Date.context_today(self),
    )
    total_neto = fields.Monetary(
        string="Total Neto",
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    total_iva = fields.Monetary(
        string="Total IVA",
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    total_exento = fields.Monetary(
        string="Total Exento",
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    total = fields.Monetary(
        string="Monto Total",
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    total_neto_calculado = fields.Monetary(
        string="Total Neto Calculado",
        store=True,
        compute='set_totales',
    )
    total_iva_calculado = fields.Monetary(
        string="Total IVA Calculado",
        store=True,
        compute='set_totales',
    )
    total_exento_calculado = fields.Monetary(
        string="Total Exento Calculado",
        store=True,
        compute='set_totales',
    )
    total_calculado = fields.Monetary(
        string="Monto Total Calculado",
        store=True,
        compute='set_totales',
    )
    total_boletas = fields.Integer(
        string="Total Boletas",
        store=True,
        compute='set_totales',
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.user.company_id.id,
    	readonly=True,
        states={'draft': [('readonly', False)]},
    )
    name = fields.Char(
        string="Detalle" ,
        required=True,
    	readonly=True,
        states={'draft': [('readonly', False)]},
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.user.company_id.currency_id,
        required=True,
        track_visibility='always',
    	readonly=True,
        states={'draft': [('readonly', False)]},
    )
    sii_result = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('NoEnviado', 'No Enviado'),
            ('Enviado', 'Enviado'),
            ('Aceptado', 'Aceptado'),
            ('Rechazado', 'Rechazado'),
            ('Reparo', 'Reparo'),
            ('Proceso', 'Proceso'),
            ('Reenviar', 'Reenviar'),
            ('Anulado', 'Anulado')
        ],
        related="state",
    )
    sequence_id = fields.Many2one(
        'ir.sequence',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    document_class_id = fields.Many2one(
        'sii.document_class',
        related="sequence_id.sii_document_class_id",
        string='Document Type',
        readonly=True,
    )
    folio_anular = fields.Integer(
        string="Folio que será anulado",
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    periodo = fields.Char(
        string='Periodo a generar',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        default=lambda *a: (datetime.now() - relativedelta.relativedelta(months=1)).strftime('%Y-%m'),
    )
    medios_de_pago = fields.Many2many(
        'account.journal',
        string="Medios de pago Electrónicos",
        readonly=True,
        states={'draft': [('readonly', False)]},
        default=lambda self: self.company_id.medios_de_pago_electronico.ids,
    )

    _order = 'fecha_emision desc'

    @api.onchange('company_id')
    def set_medios_pago_company(self):
        if self.company_id:
            self.medios_de_pago += self.company_id.medios_de_pago_electronico

    @api.onchange('periodo')
    def set_name(self):
        current = datetime.strptime(self.periodo + '-01', '%Y-%m-%d' )
        last_day = current + relativedelta.relativedelta(day=31)
        self.fecha_emision = str(last_day)

    def _get_moves(self):
        recs = []
        for r in self.move_ids:
            query = [
                ('sii_document_number', '=', r.sii_document_number),
                ('document_class_id', '=', r.document_class_id.id),
                ('type', '=', 'out_invoice'),
            ]
            ref = self.env['account.invoice'].search(query)
            recs.append(ref)
        return recs

    @api.onchange('move_ids')
    @api.depends('move_ids')
    def set_totales(self):
        for rec in self:
            monto_total = 0
            monto_neto = 0
            monto_iva = 0
            moves = rec._get_moves()
            for r in moves:
                monto_neto += (r.amount_total - r.amount_tax)
                monto_iva += r.amount_tax
                monto_total += r.amount_total
            rec.folio_anular = moves[-1].sii_document_number if moves else 0
            rec.total_neto_calculado = rec.total_neto = monto_neto
            rec.total_iva_calculado = rec.total_iva = monto_iva
            rec.total_calculado = rec.total = monto_total
            rec.total_boletas = len(moves)

    @api.onchange('periodo', 'company_id', 'medios_de_pago')
    def set_movimientos(self):
        if not self.medios_de_pago:
            return
        current = datetime.strptime( self.periodo + '-01', '%Y-%m-%d' )
        next_month = current + relativedelta.relativedelta(months=1)
        query = [
            ('sii_referencia_TpoDocRef.sii_code', 'in', [39, 41]),
            ('sii_referencia_CodRef', 'in', ['1', '3']),
            ('invoice_id.date_invoice' , '>=', current),
            ('invoice_id.date_invoice' , '<=', next_month),
            ('invoice_id.journal_id', 'in', self.medios_de_pago.ids),
            ('invoice_id.company_id', '=', self.company_id.id),
        ]
        ncs = self.env['account.invoice.referencias'].search(query)
        query = [
            ('reconciled_line_ids.company_id', '=', self.company_id.id),
            ('reconciled_line_ids.invoice_id.date_invoice' , '>=', current),
            ('reconciled_line_ids.invoice_id.date_invoice' , '<=', next_month),
            ('reconciled_line_ids.journal_id', 'in', self.medios_de_pago.ids),
            ('reconciled_line_ids.invoice_id.document_class_id.sii_code', 'in', [39, 41]),
            ('reconciled_line_ids.invoice_id.type', '=', 'out_invoice'),
        ]
        nc_invs = self.env['account.invoice']
        for nc in ncs:
            o = self.env['account.invoice.referencias'].search([
                ('sii_document_number', '=', nc.origen),
                ('document_class_id', '=', nc.sii_referencia_TpoDocRef.id),
            ])
            nc_invs += o
        if nc_invs:
            query.append(('reconciled_line_ids.invoice_id.id', 'not in', nc_invs.ids))
        moves = self.env['account.move']
        for r in self.env['account.full.reconcile'].search(query):
            for aml in r.reconciled_line_ids:
                if aml.debit > 0:
                    moves += aml.move_id
        self.move_ids = moves

    def pdf417bc(self, ted, columns=13, ratio=3):
        bc = pdf417gen.encode(
            ted,
            security_level=5,
            columns=columns,
            encoding='ISO-8859-1',
        )
        image = pdf417gen.render_image(
            bc,
            padding=15,
            scale=1,
            ratio=ratio,
        )
        return image

    def _acortar_str(self, texto, size=1):
        c = 0
        cadena = ""
        while c < size and c < len(texto):
            cadena += texto[c]
            c += 1
        return cadena

    def _actecos_emisor(self):
        actecos = []
        for a  in self.company_id.company_activities_ids[:4]:
            actecos.append(a.code)
        return actecos

    def _emisor(self):
        company_id = self.company_id
        Emisor = {}
        Emisor['RUTEmisor'] = company_id.document_number
        Emisor['RznSoc'] = company_id.partner_id.name
        Emisor['GiroEmis'] = company_id.activity_description.name
        if company_id.phone:
            Emisor['Telefono'] = company_id.phone
        Emisor['CorreoEmisor'] = company_id.dte_email_id.name_get()[0][1]
        Emisor['Actecos'] = self._actecos_emisor()
        Emisor['DirOrigen'] = company_id.street + ' ' + (company_id.street2 or '')
        if not company_id.city_id:
            raise UserError("Debe ingresar la Comuna de compañía emisora")
        Emisor['CmnaOrigen'] = company_id.city_id.name
        if not company_id.city:
            raise UserError("Debe ingresar la Ciudad de compañía emisora")
        Emisor['CiudadOrigen'] = company_id.city
        Emisor["Modo"] = "produccion" if company_id.dte_service_provider == 'SII'\
                  else 'certificacion'
        Emisor["NroResol"] = company_id.dte_resolution_number
        Emisor["FchResol"] = company_id.dte_resolution_date.strftime("%Y-%m-%d")
        return Emisor

    def _get_datos_empresa(self):
        signature_id = self.env.user.get_digital_signature(self.company_id)
        if not signature_id:
            raise UserError(_('''There are not a Signature Cert Available for this user, please upload your signature or tell to someelse.'''))
        emisor = self._emisor()
        return {
            "Emisor": emisor,
            "firma_electronica": signature_id.parametros_firma(),
        }

    def _receptor(self):
        Receptor = {}
        commercial_partner_id = self.company_id.partner_id.commercial_partner_id
        Receptor['RUTRecep'] = commercial_partner_id.rut()
        Receptor['RznSocRecep'] = self._acortar_str( commercial_partner_id.name, 100)
        GiroRecep = self.company_id.activity_description.name
        if not GiroRecep:
            raise UserError(_('Seleccione giro del partner'))
        Receptor['GiroRecep'] = self._acortar_str(GiroRecep, 40)
        if commercial_partner_id.phone:
            Receptor['Contacto'] = self._acortar_str(commercial_partner_id.phone, 80)
        if commercial_partner_id.email or commercial_partner_id.dte_email:
            Receptor['CorreoRecep'] = commercial_partner_id.email or commercial_partner_id.dte_email
        street_recep = (commercial_partner_id.street or '')
        if not street_recep:
        # or self.indicador_servicio in [1, 2]:
            raise UserError('Debe Ingresar dirección del cliente')
        street2_recep = (commercial_partner_id.street2 or '')
        if street_recep or street2_recep:
            Receptor['DirRecep'] = self._acortar_str(street_recep + (' ' + street2_recep if street2_recep else ''), 70)
        cmna_recep = commercial_partner_id.city_id.name
        if not cmna_recep:
            raise UserError('Debe Ingresar Comuna del cliente')
        Receptor['CmnaRecep'] = cmna_recep
        ciudad_recep = commercial_partner_id.city
        if ciudad_recep:
            Receptor['CiudadRecep'] = ciudad_recep
        return Receptor

    def get_folio(self):
        return self.sii_document_number

    def _id_doc(self):
        return {
            'TipoDTE': self.document_class_id.sii_code,
            'Folio': self.get_folio(),
            'FchEmis': self.fecha_emision.strftime("%Y-%m-%d"),
            'MntBruto': 1,
            'FmaPago': 1,
            'FchVenc': self.fecha_emision.strftime("%Y-%m-%d"),
        }

    def currency_base(self):
        return self.env.ref('base.CLP').with_context(date=self.fecha_emision)

    def currency_target(self):
        if self.currency_id != self.currency_base():
            return self.currency_id.with_context(date=self.fecha_emision)
        return False

    def _totales_normal(self, currency_id, MntExe, MntNeto, IVA,
                        MntTotal=0):
        Totales = {}
        if currency_id != self.currency_base():
            Totales['TpoMoneda'] = self._acortar_str(currency_id.abreviatura, 15)
        if MntNeto > 0:
            if currency_id != self.currency_id:
                    MntNeto = currency_id.compute(MntNeto, self.currency_id)
            Totales['MntNeto'] = currency_id.round(MntNeto)
        if MntExe:
            if currency_id != self.currency_id:
                MntExe = currency_id.compute(MntExe, self.currency_id)
            Totales['MntExe'] = currency_id.round(MntExe)
        Totales['TasaIVA'] = self.env['account.tax'].search([
            ('sii_code', '=', 14),
            ('type_tax_use', '=', 'sale')]).amount
        if currency_id != self.currency_id:
            IVA = currency_id.compute(IVA, self.currency_id)
        Totales['IVA'] = currency_id.round(IVA)
        if currency_id != self.currency_id:
            MntTotal = currency_id.compute(MntTotal, self.currency_id)
        Totales['MntTotal'] = currency_id.round(MntTotal)
        return Totales

    def _encabezado(self):
        Encabezado = {
            'IdDoc': self._id_doc(),
            'Receptor': self._receptor(),
        }
        currency_base = self.currency_base()
        another_currency_id = self.currency_target()
        MntExe = 0
        MntNeto = self.total_neto
        IVA = self.total_iva
        MntTotal = self.total
        Encabezado['Totales'] = self._totales_normal(currency_base, MntExe,
                                                     MntNeto, IVA, MntTotal)
        if another_currency_id:
            Encabezado['OtraMoneda'] = self._totales_otra_moneda(
                            another_currency_id, MntExe, MntNeto, IVA,
                            MntTotal)
        return Encabezado

    def _detalle_linea(self):
        prod = self.env['product.product'].search(
                [
                        ('product_tmpl_id', '=', self.env.ref('l10n_cl_fe.no_product').id),
                ]
            )
        return [
            {
                'NroLinDet': 1,
                'NmbItem': 'Anula Doucmento',
                'DscItem': 'Anula ventas con comprobante electrónico',
                'QtyItem': 1,
                'MontoItem': self.total,
            }
        ]


    def _linea_referencia(self):
        return [{
            'NroLinRef': 1,
            'TpoDocRef': 39,
            'FolioRef': self.folio_anular,
            'FchRef': self.fecha_emision.strftime("%Y-%m-%d"),
            'RazonRef': "Rebajo IVA ventas Boletas Voucher",
            'CodRef': 1,
        }]

    def _dte(self):
        return {
            'Encabezado': self._encabezado(),
            'Detalle': self._detalle_linea(),
            'Referencia': self._linea_referencia(),
            'moneda_decimales': self.currency_id.decimal_places,
        }

    def _timbrar(self):
        folio = self.get_folio()
        dte = self._get_datos_empresa()
        dte['Documento'] = [{
            'TipoDTE': self.document_class_id.sii_code,
            'caf_file': [self.sequence_id.get_caf_file(
                            folio, decoded=False).decode()],
            'documentos': [self._dte()]
            },
        ]
        result = fe.timbrar(dte)
        if result[0].get('error'):
            raise UserError(result[0].get('error'))
        self.write({
            'sii_xml_dte': result[0]['sii_xml_request'],
            'sii_barcode': result[0]['sii_barcode'],
        })

    def validar_boleta_voucher(self):
        if not self.sii_document_number:
            if not self.sequence_id:
                raise UserError("Debe seleccionar secuencia para de timbraje")
            if not self.document_class_id:
                raise UserError("La secuencia debe ser de tipo timbraje")
            self.sii_document_number = self.sequence_id.next_by_id()
        prefix = self.document_class_id.doc_code_prefix
        self.name = (prefix + str(self.sii_document_number)).replace(' ', '')
        self._timbrar()
        self.env['sii.cola_envio'].create({
                        'company_id': self.company_id.id,
                        'doc_ids': [self.id],
                        'model': 'account.move.boleta_voucher',
                        'user_id': self.env.uid,
                        'tipo_trabajo': 'envio',
                        'send_email': False,
                    })
        self.state = 'EnCola'

    def _crear_envio(self, RUTRecep="60803000-K"):
        if self.sii_result == "Rechazado" or not self.sii_xml_dte: #Retimbrar con número de atención y envío
            self._timbrar()
        if self.sii_result in ['Rechazado'] or self.sii_xml_request.state in ["", "draft", "NoEnviado"]:
            self.sii_xml_request.unlink()
            self.state = 'NoEnviado'
            self.sii_message = ''
        datos = self._get_datos_empresa()
        datos.update({
            "RutReceptor": RUTRecep,
            'Documento': [{
                    'TipoDTE': self.document_class_id.sii_code,
                    'documentos': [{
                        'NroDTE': 1,
                        'sii_xml_request': self.sii_xml_dte,
                        'Folio': self.get_folio(),
                        }],
                }]
        })
        return datos

    @api.multi
    def do_dte_send(self, n_atencion=None):
        datos = self._crear_envio()
        envio_id = self.sii_xml_request
        if not envio_id:
            envio_id = self.env["sii.xml.envio"].create({
                'name': 'temporal',
                'xml_envio': 'temporal',
                'boleta_voucher_ids': [[6,0, self.ids]],
            })
        datos["ID"] = "Env%s" %envio_id.id
        result = fe.timbrar_y_enviar(datos)
        envio = {
                'xml_envio': result.get('sii_xml_request', "temporal"),
                'name': result.get("sii_send_filename", "temporal"),
                'company_id': self.company_id.id,
                'user_id': self.env.uid,
                'sii_send_ident': result.get('sii_send_ident'),
                'sii_xml_response': result.get('sii_xml_response'),
                'state': result.get('status'),
            }
        envio_id.write(envio)
        return envio_id

    def _get_dte_status(self):
        datos = self[0]._get_datos_empresa()
        datos['Documento'] = []
        docs = {}
        if self.sii_xml_request.state not in ['Aceptado', 'Rechazado']:
            return
        for r in self:
            datos['Documento'].append({
                'TipoDTE': self.document_class_id.sii_code,
                'documentos': [self._dte()],
            })
        resultado = fe.consulta_estado_documento(datos)
        if not resultado:
            _logger.warning("En get_dte_status, no resultado")
            return
        for r in self:
            id = "T{}F{}".format(r.document_class_id.sii_code,
                                 r.get_folio())
            r.state = resultado[id]['status']
            if resultado[id].get('xml_resp'):
                r.sii_message = resultado[id].get('xml_resp')

    @api.multi
    def set_draft(self):
        if self.sii_result in ['Rechazado'] or self.sii_xml_request.state in ["", "draft", "NoEnviado"]:
            self.sii_xml_request.unlink()
            self.state = 'draft'
            self.sii_message = ''

    @api.multi
    def ask_for_dte_status(self):
        for r in self:
            if not r.sii_xml_request and not r.sii_xml_request.sii_send_ident:
                raise UserError('No se ha enviado aún el documento, aún está en cola de envío interna en odoo')
            if r.sii_xml_request.state not in ['Aceptado', 'Rechazado']:
                r.sii_xml_request.get_send_status(r.env.user)
        try:
            self._get_dte_status()
        except Exception as e:
            _logger.warning("Error al obtener DTE Status: %s" %str(e))
        for r in self:
            mess = False
            if r.sii_result == 'Rechazado':
                mess = {
                            'title': "Documento Rechazado",
                            'message': "%s" % r.name,
                            'type': 'dte_notif',
                        }
            if r.sii_result == 'Anulado':
                r.canceled = True
                try:
                    r.action_invoice_cancel()
                except:
                    _logger.warning("Error al cancelar Documento")
                mess = {
                            'title': "Documento Anulado",
                            'message': "%s" % r.name,
                            'type': 'dte_notif',
                        }
            if mess:
                self.env['bus.bus'].sendone((self._cr.dbname,
                                            'account.move.boleta_voucher',
                                            r.env.user.partner_id.id),
                                            mess)
