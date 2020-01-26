# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from lxml import etree
from lxml.etree import Element, SubElement
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
import pytz
import collections
import logging

_logger = logging.getLogger(__name__)

try:
    from facturacion_electronica import facturacion_electronica as fe
except Exception as e:
    _logger.warning("Problema al cargar Facturación Electrónica %s" % str(e))
try:
    from io import BytesIO
except:
    _logger.warning("no se ha cargado io")
try:
    from suds.client import Client
except:
    pass
try:
    import pdf417gen
except ImportError:
    _logger.info('Cannot import pdf417gen library')
try:
    import base64
except ImportError:
    _logger.info('Cannot import base64 library')

server_url = {'SIICERT': 'https://maullin.sii.cl/DTEWS/','SII':'https://palena.sii.cl/DTEWS/'}

connection_status = {
    '0': 'Upload OK',
    '1': 'El Sender no tiene permiso para enviar',
    '2': 'Error en tamaño del archivo (muy grande o muy chico)',
    '3': 'Archivo cortado (tamaño <> al parámetro size)',
    '5': 'No está autenticado',
    '6': 'Empresa no autorizada a enviar archivos',
    '7': 'Esquema Invalido',
    '8': 'Firma del Documento',
    '9': 'Sistema Bloqueado',
    'Otro': 'Error Interno.',
}


class POSL(models.Model):
    _inherit = 'pos.order.line'

    pos_order_line_id = fields.Integer(
            string="POS Line ID",
            readonly=True,
        )

    @api.depends('price_unit', 'tax_ids', 'qty', 'discount', 'product_id')
    def _compute_amount_line_all(self):
        for line in self:
            fpos = line.order_id.fiscal_position_id
            tax_ids_after_fiscal_position = fpos.map_tax(line.tax_ids, line.product_id, line.order_id.partner_id) if fpos else line.tax_ids
            taxes = tax_ids_after_fiscal_position.compute_all(line.price_unit, line.order_id.pricelist_id.currency_id, line.qty, product=line.product_id, partner=line.order_id.partner_id, discount=line.discount, uom_id=line.product_id.uom_id)
            line.update({
                'price_subtotal_incl': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })


class POS(models.Model):
    _inherit = 'pos.order'

    def _get_available_sequence(self):
        ids = [39, 41]
        if self.sequence_id and self.sequence_id.sii_code == 61:
            ids = [61]
        return [('document_class_id.sii_code', 'in', ids)]

    def _get_barcode_img(self):
        for r in self:
            if r.sii_barcode:
                barcodefile = BytesIO()
                image = self.pdf417bc(r.sii_barcode)
                image.save(barcodefile, 'PNG')
                data = barcodefile.getvalue()
                r.sii_barcode_img = base64.b64encode(data)

    signature = fields.Char(
            string="Signature",
        )
    sequence_id = fields.Many2one(
            'ir.sequence',
            string='Sequencia de Boleta',
            states={'draft': [('readonly', False)]},
            domain=lambda self: self._get_available_sequence(),
        )
    document_class_id = fields.Many2one(
            'sii.document_class',
            string='Document Type',
            copy=False,
        )
    sii_batch_number = fields.Integer(
            copy=False,
            string='Batch Number',
            readonly=True,
            help='Batch number for processing multiple invoices together',
        )
    sii_barcode = fields.Char(
            copy=False,
            string='SII Barcode',
            readonly=True,
            help='SII Barcode Name',
        )
    sii_barcode_img = fields.Binary(
            copy=False,
            string=_('SII Barcode Image'),
            help='SII Barcode Image in PDF417 format',
            compute='_get_barcode_img',
        )
    sii_xml_request = fields.Many2one(
            'sii.xml.envio',
            string='SII XML Request',
            copy=False,
        )
    sii_result = fields.Selection(
            [
                    ('', 'n/a'),
                    ('NoEnviado', 'No Enviado'),
                    ('EnCola', 'En cola de envío'),
                    ('Enviado', 'Enviado'),
                    ('Aceptado', 'Aceptado'),
                    ('Rechazado', 'Rechazado'),
                    ('Reparo', 'Reparo'),
                    ('Proceso', 'Proceso'),
                    ('Reenviar', 'Reenviar'),
                    ('Anulado', 'Anulado')
            ],
            string='Resultado',
            readonly=True,
            states={'draft': [('readonly', False)]},
            copy=False,
            help="SII request result",
            default='',
        )
    canceled = fields.Boolean(
            string="Canceled?",
        )
    responsable_envio = fields.Many2one(
            'res.users',
        )
    sii_document_number = fields.Integer(
            string="Folio de documento",
            copy=False,
        )
    referencias = fields.One2many(
            'pos.order.referencias',
            'order_id',
            string="References",
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    sii_xml_dte = fields.Text(
            string='SII XML DTE',
            copy=False,
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    sii_message = fields.Text(
            string='SII Message',
            copy=False,
        )
    respuesta_ids = fields.Many2many(
            'sii.respuesta.cliente',
            string="Recepción del Cliente",
            readonly=True,
        )

    @api.model
    def _amount_line_tax(self, line, fiscal_position_id):
        taxes = line.tax_ids.filtered(lambda t: t.company_id.id == line.order_id.company_id.id)
        if fiscal_position_id:
            taxes = fiscal_position_id.map_tax(taxes, line.product_id, line.order_id.partner_id)
        cur = line.order_id.pricelist_id.currency_id
        taxes = taxes.compute_all(line.price_unit, cur, line.qty, product=line.product_id, partner=line.order_id.partner_id or False, discount=line.discount, uom_id=line.product_id.uom_id)['taxes']
        return sum(tax.get('amount', 0.0) for tax in taxes)

    def crear_intercambio(self):
        envio = self._crear_envio(RUTRecep=rut)
        result = fe.xml_envio(envio)
        return result['sii_xml_request'].encode('ISO-8859-1')

    def _create_attachment(self,):
        url_path = '/download/xml/boleta/%s' % (self.id)
        filename = ('%s%s.xml' % (self.document_class_id.doc_code_prefix, self.sii_document_number)).replace(' ', '_')
        att = self.env['ir.attachment'].search(
                [
                    ('name', '=', filename),
                    ('res_id', '=', self.id),
                    ('res_model', '=', 'pos.order')
                ],
                limit=1,
            )
        if att:
            return att
        xml_intercambio = self.crear_intercambio()
        data = base64.b64encode(xml_intercambio)
        values = dict(
                        name=filename,
                        datas_fname=filename,
                        url=url_path,
                        res_model='pos.order',
                        res_id=self.id,
                        type='binary',
                        datas=data,
                    )
        att = self.env['ir.attachment'].sudo().create(values)
        return att

    @api.multi
    def get_xml_file(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/download/xml/boleta/%s' % (self.id),
            'target': 'self',
        }

    def get_folio(self):
        return int(self.sii_document_number)

    def format_vat(self, value):
        if not value or value == '' or value == 0:
            value = "CL666666666"
        rut = value[:10] + '-' + value[10:]
        rut = rut.replace('CL0', '').replace('CL', '')
        return rut

    def pdf417bc(self, ted):
        bc = pdf417gen.encode(
            ted,
            security_level=5,
            columns=13,
            encoding='ISO-8859-1',
        )
        image = pdf417gen.render_image(
            bc,
            padding=15,
            scale=1,
        )
        return image

    def _acortar_str(self, texto, size=1):
        c = 0
        cadena = ""
        while c < size and c < len(texto):
            cadena += texto[c]
            c += 1
        return cadena

    @api.model
    def _process_order(self, order):
        lines = []
        for l in order['lines']:
            l[2]['pos_order_line_id'] = int(l[2]['id'])
            lines.append(l)
        order['lines'] = lines
        order_id = super(POS, self)._process_order(order)
        order_id.sequence_number = order['sequence_number'] #FIX odoo bug
        if order.get('orden_numero', False) and order.get('sequence_id', False):
            order_id.sequence_id = order['sequence_id'].get('id', False)
            order_id.document_class_id = order_id.sequence_id.sii_document_class_id.id
            if order_id.sequence_id and order_id.document_class_id.sii_code == 39 and order['orden_numero'] > order_id.session_id.numero_ordenes:
                order_id.session_id.numero_ordenes = order['orden_numero']
            elif order_id.sequence_id and order_id.document_class_id.sii_code == 41 and order['orden_numero'] > order_id.session_id.numero_ordenes_exentas:
                order_id.session_id.numero_ordenes_exentas = order['orden_numero']
            order_id.sii_document_number = order['sii_document_number']
            sign = self.env.user.get_digital_signature(self.env.user.company_id)
            if (order_id.session_id.caf_files or order_id.session_id.caf_files_exentas) and sign:
                order_id.signature = order['signature']
                order_id._timbrar()
                order_id.sequence_id.next_by_id()#consumo Folio
        elif order.get('to_invoice'):
            query = []
            if order['exenta']:
                query.append(('sii_code', '=', 34))
            else:
                query.append(('sii_code', '=', 33))
            dc = self.env['sii.document_class'].sudo().search(query)
            order_id.document_class_id = dc.id
        return order_id

    def _prepare_invoice(self):
        result = super(POS, self)._prepare_invoice()
        sale_journal = self.session_id.config_id.invoice_journal_id
        journal_document_class_id = self.env['account.journal.sii_document_class'].search(
                [
                    ('journal_id', '=', sale_journal.id),
                    ('sii_document_class_id', '=', self.document_class_id.id),
                ],
            )
        if not journal_document_class_id:
            raise UserError("Por favor defina Secuencia de Facturas para el Journal %s" % sale_journal.name)
        result.update({
            'activity_description': self.partner_id.activity_description.id,
            'ticket':  self.session_id.config_id.ticket,
            'document_class_id': journal_document_class_id.sii_document_class_id.id,
            'journal_document_class_id': journal_document_class_id.id,
            'responsable_envio': self.env.uid,
        })
        return result

    @api.multi
    def do_validate(self):
        ids = []
        for order in self:
            if order.session_id.config_id.restore_mode and order.invoice_id:
                continue
            order._timbrar()
            if order.document_class_id.sii_code in [61]:
                ids.append(order.id)
        if ids:
            order.sii_result = 'EnCola'
            tiempo_pasivo = (datetime.now() + timedelta(hours=int(self.env['ir.config_parameter'].sudo().get_param('account.auto_send_dte', default=12))))
            self.env['sii.cola_envio'].create({
                'company_id': self[0].company_id.id,
                'doc_ids': ids,
                'model': 'pos.order',
                'user_id': self.env.uid,
                'tipo_trabajo': 'pasivo',
                'date_time': tiempo_pasivo,
                'send_email': False if self[0].company_id.dte_service_provider=='SIICERT' or not self.env['ir.config_parameter'].sudo().get_param('account.auto_send_email', default=True) else True,
            })

    @api.multi
    def do_dte_send_order(self):
        ids = []
        for order in self:
            if not order.invoice_id:
                if order.sii_result not in [False, '', 'NoEnviado', 'Rechazado']:
                    raise UserError("El documento %s ya ha sido enviado o está en cola de envío" % order.sii_document_number)
                if order.document_class_id.sii_code in [61]:
                    ids.append(order.id)
        if ids:
            self.env['sii.cola_envio'].create({
                'company_id': self[0].company_id.id,
                'doc_ids': ids,
                'model': 'pos.order',
                'user_id': self.env.uid,
                'tipo_trabajo': 'envio',
                'send_email': False if self[0].company_id.dte_service_provider=='SIICERT' or not self.env['ir.config_parameter'].sudo().get_param('account.auto_send_email', default=True) else True,
            })
        self.do_dte_send()

    def _giros_emisor(self):
        giros_emisor = []
        for turn in self.company_id.company_activities_ids:
            giros_emisor.append({'Acteco': turn.code})
        return giros_emisor

    def _id_doc(self, taxInclude=False, MntExe=0):
        util_model = self.env['cl.utils']
        fields_model = self.env['ir.fields.converter']
        from_zone = pytz.UTC
        to_zone = pytz.timezone('America/Santiago')
        date_order = util_model._change_time_zone(datetime.strptime(self.date_order, DTF), from_zone, to_zone).strftime(DTF)
        IdDoc = {}
        IdDoc['TipoDTE'] = self.document_class_id.sii_code
        IdDoc['Folio'] = self.get_folio()
        IdDoc['FchEmis'] = date_order[:10]
        if self.document_class_id.es_boleta():
            IdDoc['IndServicio'] = 3 #@TODO agregar las otras opciones a la fichade producto servicio
        else:
            IdDoc['TpoImpresion'] = "T"
            IdDoc['MntBruto'] = 1
            IdDoc['FmaPago'] = 1
        #if self.tipo_servicio:
        #    Encabezado['IdDoc']['IndServicio'] = 1,2,3,4
        # todo: forma de pago y fecha de vencimiento - opcional
        if not taxInclude and self.document_class_id.es_boleta():
            IdDoc['IndMntNeto'] = 2
        #if self.document_class_id.es_boleta():
            #Servicios periódicos
        #    IdDoc['PeriodoDesde'] =
        #    IdDoc['PeriodoHasta'] =
        return IdDoc

    def _emisor(self):
        Emisor = {}
        Emisor['RUTEmisor'] = self.format_vat(self.company_id.vat)
        if self.document_class_id.es_boleta():
            Emisor['RznSocEmisor'] = self.company_id.partner_id.name
            Emisor['GiroEmisor'] = self._acortar_str(self.company_id.activity_description.name, 80)
        else:
            Emisor['RznSoc'] = self.company_id.partner_id.name
            Emisor['GiroEmis'] = self._acortar_str(self.company_id.activity_description.name, 80)
            Emisor['Telefono'] = self.company_id.phone or ''
            Emisor['CorreoEmisor'] = self.company_id.dte_email_id.name_get()[0][1]
            Emisor['GiroEmisor'] = self._giros_emisor()
        if self.sale_journal.sucursal_id:
            Emisor['Sucursal'] = self.sale_journal.sucursal_id.name
            Emisor['CdgSIISucur'] = self.sale_journal.sucursal_id.sii_code
        Emisor['DirOrigen'] = self.company_id.street + ' ' +(self.company_id.street2 or '')
        Emisor['CmnaOrigen'] = self.company_id.city_id.name or ''
        Emisor['CiudadOrigen'] = self.company_id.city or ''
        Emisor["Modo"] = "produccion" if self.company_id.dte_service_provider == 'SII'\
                  else 'certificacion'
        Emisor["NroResol"] = self.company_id.dte_resolution_number
        Emisor["FchResol"] = self.company_id.dte_resolution_date
        Emisor["ValorIva"] = 19
        return Emisor

    def _receptor(self):
        Receptor = {}
        #Receptor['CdgIntRecep']
        Receptor['RUTRecep'] = self.format_vat(self.partner_id.vat)
        Receptor['RznSocRecep'] = self._acortar_str(self.partner_id.name or "Usuario Anonimo", 100)
        if self.partner_id.phone:
            Receptor['Contacto'] = self.partner_id.phone
        if self.partner_id.dte_email and not self.document_class_id.es_boleta():
            Receptor['CorreoRecep'] = self.partner_id.dte_email
        if self.partner_id.street:
            Receptor['DirRecep'] = self.partner_id.street+ ' ' + (self.partner_id.street2 or '')
        if self.partner_id.city_id:
            Receptor['CmnaRecep'] = self.partner_id.city_id.name
        if self.partner_id.city:
            Receptor['CiudadRecep'] = self.partner_id.city
        return Receptor

    def _totales(self, MntExe=0, no_product=False, taxInclude=False):
        currency = self.pricelist_id.currency_id
        Totales = {}
        amount_total = currency.round(self.amount_total)
        if amount_total < 0:
            amount_total *= -1
        if no_product:
            amount_total = 0
        else:
            if self.document_class_id.sii_code in [34, 41] and self.amount_tax > 0:
                raise UserError("NO pueden ir productos afectos en documentos exentos")
            amount_untaxed = self.amount_total - self.amount_tax
            if amount_untaxed < 0:
                amount_untaxed *= -1
            if MntExe < 0:
                MntExe *= -1
            if self.amount_tax == 0 and self.document_class_id.sii_code in [39]:
                raise UserError("Debe ir almenos un Producto Afecto")
            Neto = amount_untaxed - MntExe
            IVA = False
            if Neto > 0 and (not self.document_class_id.es_boleta() or self._context.get('tax_detail')):
                for l in self.lines:
                    for t in l.tax_ids:
                        if t.sii_code in [14, 15]:
                            IVA = True
                            IVAAmount = round(t.amount,2)
                if IVA:
                    Totales['MntNeto'] = currency.round(Neto)
            if MntExe > 0:
                Totales['MntExe'] = currency.round(MntExe)
            if IVA and not self.document_class_id.es_boleta() or self._context.get('tax_detail'):
                Totales['TasaIVA'] = IVAAmount
                iva = currency.round(self.amount_tax)
                if iva < 0:
                    iva *= -1
                Totales['IVA'] = iva
            #if IVA and IVA.tax_id.sii_code in [15]:
            #    Totales['ImptoReten'] = collections.OrderedDict()
            #    Totales['ImptoReten']['TpoImp'] = IVA.tax_id.sii_code
            #    Totales['ImptoReten']['TasaImp'] = round(IVA.tax_id.amount,2)
            #    Totales['ImptoReten']['MontoImp'] = int(round(IVA.amount))
        Totales['MntTotal'] = amount_total

        #Totales['MontoNF']
        #Totales['TotalPeriodo']
        #Totales['SaldoAnterior']
        #Totales['VlrPagar']
        return Totales

    def _encabezado(self, MntExe=0, no_product=False, taxInclude=False):
        Encabezado = {}
        Encabezado['IdDoc'] = self._id_doc(taxInclude, MntExe)
        Encabezado['Emisor'] = self._emisor()
        Encabezado['Receptor'] = self._receptor()
        Encabezado['Totales'] = self._totales(MntExe, no_product, taxInclude)
        return Encabezado

    def _invoice_lines(self):
        currency = self.pricelist_id.currency_id
        line_number = 1
        invoice_lines = []
        no_product = False
        MntExe = 0
        for line in self.with_context(lang="es_CL").lines:
            if line.product_id.default_code == 'NO_PRODUCT':
                no_product = True
            lines = {}
            lines['NroLinDet'] = line_number
            if line.product_id.default_code and not no_product:
                lines['CdgItem'] = {}
                lines['CdgItem']['TpoCodigo'] = 'INT1'
                lines['CdgItem']['VlrCodigo'] = line.product_id.default_code
            taxInclude = True
            for t in line.tax_ids:
                if t.amount == 0 or t.sii_code in [0]:#@TODO mejor manera de identificar exento de afecto
                    lines['IndExe'] = 1
                    MntExe += currency.round(line.price_subtotal_incl)
                else:
                    taxInclude = t.price_include
            #if line.product_id.type == 'events':
            #   lines['ItemEspectaculo'] =
#            if self.document_class_id.es_boleta():
#                lines['RUTMandante']
            lines['NmbItem'] = self._acortar_str(line.product_id.name,80) #
            lines['DscItem'] = self._acortar_str(line.name, 1000) #descripción más extenza
            if line.product_id.default_code:
                lines['NmbItem'] = self._acortar_str(line.product_id.name.replace('['+line.product_id.default_code+'] ',''),80)
            #lines['InfoTicket']
            qty = round(line.qty, 4)
            if qty < 0:
                qty *= -1
            if not no_product:
                lines['QtyItem'] = qty
            if qty == 0 and not no_product:
                lines['QtyItem'] = 1
                #raise UserError("NO puede ser menor que 0")
            if not no_product:
                lines['UnmdItem'] = line.product_id.uom_id.name[:4]
                lines['PrcItem'] = round(line.price_unit, 4)
            if line.discount > 0:
                lines['DescuentoPct'] = line.discount
                lines['DescuentoMonto'] = currency.round((((line.discount / 100) * lines['PrcItem'])* qty))
            if not no_product and not taxInclude:
                price = currency.round(line.price_subtotal)
            elif not no_product:
                price = currency.round(line.price_subtotal_incl)
            if price < 0:
                price *= -1
            lines['MontoItem'] = price
            if no_product:
                lines['MontoItem'] = 0
            line_number += 1
            if lines.get('PrcItem', 1) == 0:
                del(lines['PrcItem'])
            invoice_lines.append(lines)
        return {
                'Detalle': invoice_lines,
                'MntExe': MntExe,
                'no_product': no_product,
                'tax_include': taxInclude,
                }

    def _valida_referencia(self, ref):
        if ref.origen in [False, '', 0]:
            raise UserError("Debe incluir Folio de Referencia válido")

    def _dte(self):
        dte = {}
        invoice_lines = self._invoice_lines()
        dte['Encabezado'] = self._encabezado(
            invoice_lines['MntExe'],
            invoice_lines['no_product'],
            invoice_lines['tax_include'],
        )
        lin_ref = 1
        ref_lines = []
        for ref in self.referencias:
            ref_line = {}
            ref_line['NroLinRef'] = lin_ref
            self._valida_referencia(ref)
            if not self.document_class_id.es_boleta():
                if ref.sii_referencia_TpoDocRef:
                    ref_line['TpoDocRef'] = ref.sii_referencia_TpoDocRef.sii_code
                    ref_line['FolioRef'] = ref.origen
                ref_line['FchRef'] = ref.fecha_documento or datetime.strftime(datetime.now(), '%Y-%m-%d')
            if ref.sii_referencia_CodRef not in ['', 'none', False]:
                ref_line['CodRef'] = ref.sii_referencia_CodRef
            ref_line['RazonRef'] = ref.motivo
            if self.document_class_id.es_boleta():
                ref_line['CodVndor'] = self.user_id.id
                ref_line['CodCaja'] = self.location_id.name
            ref_lines.append(ref_line)
            lin_ref += 1
        dte['Detalle'] = invoice_lines['Detalle']
        dte['Referencia'] = ref_lines
        return dte

    def _get_datos_empresa(self, company_id):
        signature_id = self.env.user.get_digital_signature(company_id)
        if not signature_id:
            raise UserError(_('''There are not a Signature Cert Available for this user, please upload your signature or tell to someelse.'''))
        emisor = self._emisor()
        return {
            "Emisor": emisor,
            "firma_electronica": signature_id.parametros_firma(),
        }

    def _timbrar(self):
        folio = self.get_folio()
        doc_id_number = "F{}T{}".format(folio, self.document_class_id.sii_code)
        doc_id = '<Documento ID="{}">'.format(doc_id_number)
        dte = self._get_datos_empresa(self.company_id)
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
        return

    def _crear_envio(self, RUTRecep="60803000-K"):
        grupos = {}
        batch = 0
        for r in self.with_context(lang='es_CL'):
            batch += 1
            if r.sii_result in ['Rechazado']:
                r._timbrar()
            #@TODO Mejarorar esto en lo posible
            grupos.setdefault(r.document_class_id.sii_code, [])
            grupos[r.document_class_id.sii_code].append({
                'NroDTE': r.sii_batch_number,
                'sii_xml_request': r.sii_xml_dte,
                'Folio': r.get_folio(),
            })
        envio = self[0]._get_datos_empresa(self[0].company_id)
        envio.update({
            'RutReceptor': RUTRecep,
            'Documento': []
        })
        for k, v in grupos.items():
            envio['Documento'].append(
                {
                    'TipoDTE': k,
                    'documentos': v,
                }
            )
        return envio

    @api.multi
    def do_dte_send(self, n_atencion=None):
        datos = self._crear_envio()
        result = fe.timbrar_y_enviar(datos)
        envio_id = self[0].sii_xml_request
        envio = {
                'xml_envio': result['sii_xml_request'],
                'name': result['sii_send_filename'],
                'company_id': self[0].company_id.id,
                'user_id': self.env.uid,
                'sii_send_ident': result.get('sii_send_ident'),
                'sii_xml_response': result.get('sii_xml_response'),
                'state': result.get('sii_result'),
            }
        if not envio_id:
            envio_id = self.env['sii.xml.envio'].create(envio)
            for i in self:
                i.sii_xml_request = envio_id.id
                i.sii_result = 'Enviado'
        else:
            envio_id.write(envio)
        return envio_id

    @api.onchange('sii_message')
    def get_sii_result(self):
        for r in self:
            if r.sii_message:
                r.sii_result = self.env['account.invoice'].process_response_xml(r.sii_message)
                continue
            if r.sii_xml_request.state == 'NoEnviado':
                r.sii_result = 'EnCola'
                continue
            r.sii_result = r.sii_xml_request.state

    def _get_dte_status(self):
        for r in self:
            if r.sii_xml_request and r.sii_xml_request.state not in ['Aceptado', 'Rechazado']:
                continue
            token = r.sii_xml_request.get_token(self.env.user, r.company_id)
            url = server_url[r.company_id.dte_service_provider] + 'QueryEstDte.jws?WSDL'
            _server = Client(url)
            receptor = r.format_vat(r.partner_id.vat)
            util_model = self.env['cl.utils']
            fields_model = self.env['ir.fields.converter']
            from_zone = pytz.UTC
            to_zone = pytz.timezone('America/Santiago')
            date_order = util_model._change_time_zone(datetime.strptime(r.date_order, DTF), from_zone, to_zone).strftime("%d-%m-%Y")
            signature_id = self.env.user.get_digital_signature(r.company_id)
            rut = signature_id.subject_serial_number
            amount_total = r.amount_total if r.amount_total >= 0 else r.amount_total*-1
            try:
                respuesta = _server.service.getEstDte(
                    rut[:8].replace('-', ''),
                    str(rut[-1]),
                    r.company_id.vat[2:-1],
                    r.company_id.vat[-1],
                    receptor[:8],
                    receptor[-1],
                    str(r.document_class_id.sii_code),
                    str(r.sii_document_number),
                    date_order,
                    str(int(amount_total)),
                    token,
                )
            except Exception as e:
                msg = "Error al obtener Estado DTE"
                _logger.warning("%s: %s" % (msg, str(e)))
                if e.args[0][0] == 503:
                    raise UserError('%s: Conexión al SII caída/rechazada o el SII está temporalmente fuera de línea, reintente la acción' % (msg))
                raise UserError(("%s: %s" % (msg, str(e))))
            r.sii_message = respuesta

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
        self.get_sii_result()

    def send_exchange(self):
        att = self._create_attachment()
        body = 'XML de Intercambio DTE: %s%s' % (self.document_class_id.doc_code_prefix, self.sii_document_number)
        subject = 'XML de Intercambio DTE: %s%s' % (self.document_class_id.doc_code_prefix, self.sii_document_number)
        dte_email_id = self.company_id.dte_email_id or self.env.user.company_id.dte_email_id
        dte_receptors = self.partner_id.commercial_partner_id.child_ids + self.partner_id.commercial_partner_id
        email_to = ''
        for dte_email in dte_receptors:
            if not dte_email.send_dte:
                continue
            email_to += dte_email.name+','
        values = {
                'res_id': self.id,
                'email_from': dte_email_id.name_get()[0][1],
                'email_to': email_to[:-1],
                'auto_delete': False,
                'model': 'pos.order',
                'body': body,
                'subject': subject,
                'attachment_ids': [[6, 0, att.ids]],
            }
        send_mail = self.env['mail.mail'].sudo().create(values)
        send_mail.send()

    def _create_account_move_line(self, session=None, move=None):
        # Tricky, via the workflow, we only have one id in the ids variable
        """Create a account move line of order grouped by products or not."""
        IrProperty = self.env['ir.property']
        ResPartner = self.env['res.partner']

        if session and not all(session.id == order.session_id.id for order in self):
            raise UserError(_('Selected orders do not have the same session!'))

        grouped_data = {}
        have_to_group_by = session and session.config_id.group_by or False
        rounding_method = session and session.config_id.company_id.tax_calculation_rounding_method
        document_class_id = False
        for order in self.filtered(lambda o: not o.account_move or o.state == 'paid'):
            if order.document_class_id:
                document_class_id = order.document_class_id

            current_company = order.sale_journal.company_id
            account_def = IrProperty.get(
                'property_account_receivable_id', 'res.partner')
            order_account = order.partner_id.property_account_receivable_id.id or account_def and account_def.id
            partner_id = ResPartner._find_accounting_partner(order.partner_id).id or False
            if move is None:
                # Create an entry for the sale
                journal_id = self.env['ir.config_parameter'].sudo().get_param(
                    'pos.closing.journal_id_%s' % current_company.id, default=order.sale_journal.id)
                move = self._create_account_move(
                    order.session_id.start_at, order.name, int(journal_id), order.company_id.id)

            def insert_data(data_type, values):
                # if have_to_group_by:

                # 'quantity': line.qty,
                # 'product_id': line.product_id.id,
                values.update({
                    'partner_id': partner_id,
                    'move_id': move.id,
                })
                key = self._get_account_move_line_group_data_type_key(data_type, values)
                if not key:
                    return

                grouped_data.setdefault(key, [])

                if have_to_group_by:
                    if not grouped_data[key]:
                        grouped_data[key].append(values)
                    else:
                        current_value = grouped_data[key][0]
                        current_value['quantity'] = current_value.get('quantity', 0.0) + values.get('quantity', 0.0)
                        current_value['credit'] = current_value.get('credit', 0.0) + values.get('credit', 0.0)
                        current_value['debit'] = current_value.get('debit', 0.0) + values.get('debit', 0.0)
                else:
                    grouped_data[key].append(values)

            # because of the weird way the pos order is written, we need to make sure there is at least one line,
            # because just after the 'for' loop there are references to 'line' and 'income_account' variables (that
            # are set inside the for loop)
            # TOFIX: a deep refactoring of this method (and class!) is needed
            # in order to get rid of this stupid hack
            assert order.lines, _('The POS order must have lines when calling this method')
            # Create an move for each order line
            cur = order.pricelist_id.currency_id
            # Create an move for each order line
            taxes = {}
            cur = order.pricelist_id.currency_id
            Afecto = 0
            Exento = 0
            Taxes = 0
            for line in order.lines:
                amount = line.price_subtotal
                # Search for the income account
                if line.product_id.property_account_income_id.id:
                    income_account = line.product_id.property_account_income_id.id
                elif line.product_id.categ_id.property_account_income_categ_id.id:
                    income_account = line.product_id.categ_id.property_account_income_categ_id.id
                else:
                    raise UserError(_('Please define income '
                                      'account for this product: "%s" (id:%d).')
                                    % (line.product_id.name, line.product_id.id))

                name = line.product_id.name
                if line.notice:
                    # add discount reason in move
                    name = name + ' (' + line.notice + ')'

                # Create a move for the line for the order line
                insert_data('product', {
                    'name': name,
                    'quantity': line.qty,
                    'product_id': line.product_id.id,
                    'account_id': income_account,
                    'analytic_account_id': self._prepare_analytic_account(line),
                    'credit': ((amount > 0) and amount) or 0.0,
                    'debit': ((amount < 0) and -amount) or 0.0,
                    'tax_ids': [(6, 0, line.tax_ids_after_fiscal_position.ids)],
                    'partner_id': partner_id
                })

                # Create the tax lines
                line_taxes = line.tax_ids_after_fiscal_position.filtered(lambda t: t.company_id.id == current_company.id)
                line_amount = line.price_unit * (100.0-line.discount) / 100.0
                line_amount *= line.qty
                line_amount = int(round(line_amount))
                if not line_taxes:
                    Exento += line_amount
                    continue
                for t in line_taxes:
                    taxes.setdefault(t, 0)
                    taxes[t] += line_amount
                    if t.amount > 0:
                        Afecto += amount
                    else:
                        Exento += amount
                pending_line = line
            #el Cálculo se hace sumando todos los valores redondeados, luego se cimprueba si hay descuadre de $1 y se agrega como línea de ajuste
            for t, value in taxes.items():
                tax = t.compute_all(value , cur, 1, uom_id=line.product_id.uom_id)['taxes'][0]
                insert_data('tax', {
                    'name': _('Tax') + ' ' + tax['name'],
                    'product_id': line.product_id.id,
                    'quantity': line.qty,
                    'account_id': tax['account_id'] or income_account,
                    'credit': int(round(((tax['amount']>0) and tax['amount']) or 0.0)),
                    'debit': int(round(((tax['amount']<0) and -tax['amount']) or 0.0)),
                    'tax_line_id': tax['id'],
                    'partner_id': partner_id
                })
                if t.amount > 0:
                    t_amount = int(round(tax['amount']))
                    Taxes += t_amount
            dif = ( order.amount_total - (Exento + Afecto + Taxes))
            if dif != 0:
                insert_data('product', {
                    'name': name,
                    'quantity': (1 * dif),
                    'product_id': pending_line.product_id.id,
                    'account_id': income_account,
                    'analytic_account_id': self._prepare_analytic_account(line),
                    'credit': ((dif>0) and dif) or 0.0,
                    'debit': ((dif<0) and -dif) or 0.0,
                    'tax_ids': [(6, 0, pending_line.tax_ids_after_fiscal_position.ids)],
                    'partner_id': partner_id
                })

            #@TODO testear si esto ya repara los problemas de redondeo original de odoo
            # round tax lines per order
            #if rounding_method == 'round_globally':
            #    for group_key, group_value in grouped_data.items():
            #        if group_key[0] == 'tax':
            #            for line in group_value:
            #                line['credit'] = cur.round(line['credit'])
            #                line['debit'] = cur.round(line['debit'])

            # counterpart
            insert_data('counter_part', {
                'name': _("Trade Receivables"),  # order.name,
                'account_id': order_account,
                'credit': ((order.amount_total < 0) and -order.amount_total) or 0.0,
                'debit': ((order.amount_total > 0) and order.amount_total) or 0.0,
                'partner_id': partner_id
            })

            order.write({'state': 'done', 'account_move': move.id})

        all_lines = []
        for group_key, group_data in grouped_data.items():
            for value in group_data:
                all_lines.append((0, 0, value),)
        if move:  # In case no order was changed
            move.sudo().write(
                    {
                            'line_ids': all_lines,
                            'document_class_id':  (document_class_id.id if document_class_id else False ),
                    }
                )
            move.sudo().post()
        return True

    @api.multi
    def action_pos_order_paid(self):
        if self.test_paid():
            if self.sequence_id and not self.sii_xml_request:
                if (not self.sii_document_number or self.sii_document_number == 0) and not self.signature:
                    self.sii_document_number = self.sequence_id.next_by_id()
                self.do_validate()
        return super(POS, self).action_pos_order_paid()

    @api.depends('statement_ids', 'lines.price_subtotal_incl', 'lines.discount')
    def _compute_amount_all(self):
        for order in self:
            order.amount_paid = order.amount_return = order.amount_tax = 0.0
            currency = order.pricelist_id.currency_id
            order.amount_paid = sum(payment.amount for payment in order.statement_ids)
            order.amount_return = sum(payment.amount < 0 and payment.amount or 0 for payment in order.statement_ids)
            order.amount_tax = currency.round(sum(self._amount_line_tax(line, order.fiscal_position_id) for line in order.lines))
            amount_total = currency.round(sum(line.price_subtotal_incl for line in order.lines))
            order.amount_total = amount_total

    @api.multi
    def exento(self):
        exento = 0
        for l in self.lines:
            if l.tax_ids_after_fiscal_position.amount == 0:
                exento += l.price_subtotal
        return exento if exento > 0 else (exento * -1)

    @api.multi
    def print_nc(self):
        """ Print NC
        """
        return self.env.ref('l10n_cl_dte_point_of_sale.action_report_pos_boleta_ticket').report_action(self)

    @api.multi
    def _get_printed_report_name(self):
        self.ensure_one()
        report_string = "%s %s" % (self.document_class_id.name, self.sii_document_number)
        return report_string

    @api.multi
    def get_invoice(self):
        return self.invoice_id


class Referencias(models.Model):
    _name = 'pos.order.referencias'
    _description = 'Referencias de Orden'

    origen = fields.Char(
            string="Origin",
        )
    sii_referencia_TpoDocRef = fields.Many2one(
            'sii.document_class',
            string="SII Reference Document Type",
        )
    sii_referencia_CodRef = fields.Selection(
            [
                    ('1', 'Anula Documento de Referencia'),
                    ('2', 'Corrige texto Documento Referencia'),
                    ('3', 'Corrige montos')
            ],
            string="SII Reference Code",
        )
    motivo = fields.Char(
            string="Motivo",
        )
    order_id = fields.Many2one(
            'pos.order',
            ondelete='cascade',
            index=True,
            copy=False,
            string="Documento",
        )
    fecha_documento = fields.Date(
            string="Fecha Documento",
            required=True,
        )
