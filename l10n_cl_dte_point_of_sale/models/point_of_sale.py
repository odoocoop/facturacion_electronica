# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero
from datetime import datetime, timedelta
from lxml import etree
from lxml.etree import Element, SubElement
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
import pytz
import collections
import math
import logging

_logger = logging.getLogger(__name__)

try:
    from facturacion_electronica import facturacion_electronica as fe
    from facturacion_electronica import clase_util as util
except Exception as e:
    _logger.warning("Problema al cargar Facturación Electrónica %s" % str(e))
try:
    from io import BytesIO
except:
    _logger.warning("no se ha cargado io")
try:
    import pdf417gen
except ImportError:
    _logger.info('Cannot import pdf417gen library')
try:
    import base64
except ImportError:
    _logger.info('Cannot import base64 library')


class POSL(models.Model):
    _inherit = 'pos.order.line'

    pos_order_line_id = fields.Integer(
            string="POS Line ID",
            readonly=True,
        )

    @api.depends('price_unit', 'tax_ids', 'qty', 'discount', 'product_id')
    def _compute_amount_line_all(self):
        for line in self:
            cur_company = line.company_id.currency_id
            fpos = line.order_id.fiscal_position_id
            tax_ids_after_fiscal_position = fpos.map_tax(line.tax_ids, line.product_id, line.order_id.partner_id) if fpos else line.tax_ids
            taxes = tax_ids_after_fiscal_position.with_context(
                date=self.order_id.date_order,
                currency=cur_company.code).compute_all(
                    line.price_unit,
                    line.order_id.pricelist_id.currency_id,
                    line.qty,
                    product=line.product_id,
                    partner=line.order_id.partner_id,
                    discount=line.discount,
                    uom_id=line.product_id.uom_id)
            line.update({
                'price_subtotal_incl': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.onchange('qty', 'discount', 'price_unit', 'tax_ids')
    def _onchange_qty(self):
        if self.product_id:
            if not self.order_id.pricelist_id:
                raise UserError(_('You have to select a pricelist in the sale form !'))
            price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
            self.price_subtotal = self.price_subtotal_incl = price * self.qty
            if (self.product_id.taxes_id):
                taxes = self.product_id.taxes_id.compute_all(self.price_unit, self.order_id.pricelist_id.currency_id, self.qty, product=self.product_id, partner=False, discount=self.discount, uom_id=self.product_id.uom_id)
                self.price_subtotal = taxes['total_excluded']
                self.price_subtotal_incl = taxes['total_included']


class POS(models.Model):
    _inherit = 'pos.order'

    def _get_available_sequence(self):
        ids = [39, 41]
        if self.sequence_id and self.sequence_id.sii_code == 61:
            ids = [61]
        return [('document_class_id.sii_code', 'in', ids)]

    def _get_barcode_img(self):
        for r in self:
            r.sii_barcode_img = False
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
            readonly=True,
            copy=True,
            domain=lambda self: self._get_available_sequence(),
        )
    document_class_id = fields.Many2one(
            'sii.document_class',
            string='Document Type',
            states={'draft': [('readonly', False)]},
            readonly=True,
            copy=True,
        )
    sii_code = fields.Integer(
            related="document_class_id.sii_code",
        )
    sii_batch_number = fields.Integer(
            copy=False,
            string='Batch Number',
            states={'draft': [('readonly', False)]},
            readonly=True,
            help='Batch number for processing multiple invoices together',
        )
    sii_barcode = fields.Char(
            copy=False,
            string='SII Barcode',
            states={'draft': [('readonly', False)]},
            readonly=True,
            help='SII Barcode Name',
        )
    sii_barcode_img = fields.Binary(
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
                    ('draft', 'Borrador'),
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
            states={'draft': [('readonly', False)]},
            readonly=True,
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
    timestamp_timbre = fields.Char(
        string="TimeStamp Timbre",
        states={'draft': [('readonly', False)]},
        readonly=True,
        copy=False,
    )

    @api.model
    def _amount_line_tax(self, line, fiscal_position_id):
        taxes = line.tax_ids.filtered(lambda t: t.company_id.id == line.order_id.company_id.id)
        if fiscal_position_id:
            taxes = fiscal_position_id.map_tax(taxes, line.product_id, line.order_id.partner_id)
        cur = line.order_id.pricelist_id.currency_id
        cur_company = line.order_id.company_id.currency_id
        taxes = taxes.with_context(date=line.order_id.date_order, currency=cur_company.code).compute_all(line.price_unit, cur, line.qty, product=line.product_id, partner=line.order_id.partner_id or False, discount=line.discount, uom_id=line.product_id.uom_id)['taxes']
        return taxes

    def crear_intercambio(self):
        partner_id = self.partner_id.commercial_partner_id
        envio = self._crear_envio(RUTRecep=partner_id.rut())
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
                        url=url_path,
                        res_model='pos.order',
                        res_id=self.id,
                        type='binary',
                        datas=data,
                    )
        att = self.env['ir.attachment'].sudo().create(values)
        return att


    def get_xml_file(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/download/xml/boleta/%s' % (self.id),
            'target': 'self',
        }

    def get_folio(self):
        return int(self.sii_document_number)

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
    def _order_fields(self, ui_order):
        result = super(POS, self)._order_fields(ui_order)
        result.update({
            'document_class_id': ui_order.get('document_class_id', False),
            'sequence_id': ui_order.get('sequence_id', False),
            'sii_document_number': ui_order.get('sii_document_number', 0),
            'signature': ui_order.get('signature', ''),
            'timestamp_timbre': ui_order.get('timestamp_timbre', ''),
        })
        return result

    @api.model
    def _process_order(self, order, draft, existing_order):
        for l in order['data']['lines']:
            l[2]['pos_order_line_id'] = int(l[2]['id'])
        #if order_id.amount_total != float(order['data']['amount_total']):
        #    raise UserError("Diferencia de cálculo, verificar. En el caso de que el cálculo use Mepco, debe intentar cerrar la caja porque el valor a cambiado")
        sequence_id = False
        if order.get('data', {}).get('sequence_id'):
            sequence_id = self.env['ir.sequence'].sudo().browse(order['data']['sequence_id'])
            order['data']['document_class_id'] = sequence_id.sii_document_class_id.id
        if sequence_id and  sequence_id.sii_document_class_id.es_boleta():
            session_id = self.env['pos.session'].sudo().browse(order['data']['pos_session_id'])
            if sequence_id.sii_document_class_id.sii_code == 39 and order['data']['orden_numero'] > session_id.numero_ordenes:
                session_id.numero_ordenes = order['data']['orden_numero']
            elif sequence_id.sii_document_class_id.sii_code == 41 and order['data']['orden_numero'] > session_id.numero_ordenes_exentas:
                session_id.numero_ordenes_exentas = order['data']['orden_numero']
            if (session_id.caf_files or session_id.caf_files_exentas):
                timbre = etree.fromstring(order['data']['signature'])
                order['data']['timestamp_timbre'] = timbre.find('DD/TSTED').text
            sequence_id.next_by_id()
        return super(POS, self)._process_order(order, draft, existing_order)

    def _prepare_invoice(self):
        result = super(POS, self)._prepare_invoice()
        if not self.sequence_id:
            return result
        self.document_class_id= self.sequence_id.sii_document_class_id.id
        sale_journal = self.session_id.config_id.invoice_journal_id
        journal_document_class_id = self.env['account.journal.sii_document_class'].search(
                [
                    ('journal_id', '=', sale_journal.id),
                    ('sii_document_class_id', '=', self.document_class_id.id),
                ],
            )
        if not journal_document_class_id:
            raise UserError("Por favor defina Secuencia de %s para el Journal %s" % (self.document_class_id.name, sale_journal.name))
        result.update({
            'activity_description': self.partner_id.activity_description.id,
            'ticket':  self.session_id.config_id.ticket,
            'document_class_id': self.document_class_id.id,
            'journal_document_class_id': journal_document_class_id.id,
            'responsable_envio': self.env.uid,
            'use_documents': True,
        })
        return result


    def do_validate(self):
        ids = []
        for order in self:
            if order.session_id.config_id.restore_mode or not order.sequence_id or \
            (not order.document_class_id.es_boleta() and order.document_class_id.sii_code not in [61]):
                continue
            order._timbrar()
            order.sii_result = 'EnCola'
            ids.append(order.id)
        if ids:
            tiempo_pasivo = (datetime.now() + timedelta(hours=int(self.env['ir.config_parameter'].sudo().get_param('account.auto_send_dte', default=12))))
            self.env['sii.cola_envio'].sudo().create({
                'company_id': self[0].company_id.id,
                'doc_ids': ids,
                'model': 'pos.order',
                'user_id': self.env.uid,
                'tipo_trabajo': 'pasivo',
                'date_time': tiempo_pasivo,
                'send_email': False if self[0].company_id.dte_service_provider=='SIICERT' or not self.env['ir.config_parameter'].sudo().get_param('account.auto_send_email', default=True) else True,
            })


    def do_dte_send_order(self):
        ids = []
        for order in self:
            if not order.to_invoice and order.document_class_id.sii_code in [61, 39, 41]:
                if order.sii_xml_request.sii_send_ident not in [False, 'BE'] and order.sii_result not in [False, '', 'NoEnviado', 'Rechazado']:
                    raise UserError("El documento %s ya ha sido enviado o está en cola de envío" % order.sii_document_number)
                if order.sii_result in ["Rechazado"] or order.sii_xml_request.sii_send_ident == 'BE':
                    order._timbrar()
                    if len(order.sii_xml_request.order_ids) == 1:
                        order.sii_xml_request.unlink()
                    else:
                        order.sii_xml_request = False
                    order.sii_message = ''
                order.sii_result = 'EnCola'
                ids.append(order.id)
        if ids:
            self.env['sii.cola_envio'].sudo().create({
                'company_id': self[0].company_id.id,
                'doc_ids': ids,
                'model': 'pos.order',
                'user_id': self.env.uid,
                'tipo_trabajo': 'envio',
                'send_email': False if self[0].company_id.dte_service_provider=='SIICERT' or not self.env['ir.config_parameter'].sudo().get_param('account.auto_send_email', default=True) else True,
                "set_pruebas": self._context.get("set_pruebas", False),
            })

    def _giros_emisor(self):
        giros_emisor = []
        for ac in self.session_id.config_id.acteco_ids:
            giros_emisor.append(ac.code)
        return giros_emisor

    def _id_doc(self, taxInclude=False, MntExe=0):
        util_model = self.env['cl.utils']
        fields_model = self.env['ir.fields.converter']
        from_zone = pytz.UTC
        to_zone = pytz.timezone('America/Santiago')
        date_order = util_model._change_time_zone(self.date_order, from_zone, to_zone).strftime(DTF)
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
        Emisor['RUTEmisor'] = self.company_id.partner_id.rut()
        if self.document_class_id.es_boleta():
            Emisor['RznSocEmisor'] = self.company_id.partner_id.name
            Emisor['GiroEmisor'] = self._acortar_str(self.company_id.activity_description.name, 80)
        else:
            Emisor['RznSoc'] = self.company_id.partner_id.name
            Emisor['GiroEmis'] = self._acortar_str(self.company_id.activity_description.name, 80)
            Emisor['Telefono'] = self.company_id.phone or ''
            Emisor['CorreoEmisor'] = self.company_id.dte_email_id.name_get()[0][1]
            Emisor['Actecos'] = self._giros_emisor()
        dir_origen = self.company_id
        if self.config_id.sucursal_id:
            Emisor['Sucursal'] = self.config_id.sucursal_id.name
            Emisor['CdgSIISucur'] = self.config_id.sucursal_id.sii_code
            dir_origen = self.config_id.sucursal_id.partner_id
        Emisor['DirOrigen'] = dir_origen.street + ' ' +(dir_origen.street2 or '')
        Emisor['CmnaOrigen'] = dir_origen.city_id.name or ''
        Emisor['CiudadOrigen'] = dir_origen.city or ''
        Emisor["Modo"] = "produccion" if self.company_id.dte_service_provider == 'SII'\
                  else 'certificacion'
        Emisor["NroResol"] = self.company_id.dte_resolution_number
        Emisor["FchResol"] = self.company_id.dte_resolution_date.strftime('%Y-%m-%d')
        Emisor["ValorIva"] = 19
        return Emisor

    def _receptor(self):
        Receptor = {}
        #Receptor['CdgIntRecep']
        Receptor['RUTRecep'] = self.partner_id.commercial_partner_id.rut()
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
            if Neto > 0:
                for l in self.lines:
                    for t in l.tax_ids:
                        if t.sii_code in [14, 15]:
                            IVA = True
                            IVAAmount = round(t.amount,2)
                if IVA:
                    Totales['MntNeto'] = currency.round(Neto)
            if MntExe > 0:
                Totales['MntExe'] = currency.round(MntExe)
            if IVA:
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
            taxInclude = self.document_class_id.es_boleta()
            if not taxInclude:
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
                lines['DescuentoPct'] = round(line.discount, 2)
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
        if self._context.get("set_pruebas", False):
            RazonRef = "CASO-" + str(self.sii_batch_number)
            ref_line = {}
            ref_line['NroLinRef'] = lin_ref
            ref_line['CodRef'] = "SET"
            ref_line['RazonRef'] = RazonRef
            lin_ref = 2
            ref_lines.append(ref_line)
        for ref in self.referencias:
            ref_line = {}
            ref_line['NroLinRef'] = lin_ref
            self._valida_referencia(ref)
            if not self.document_class_id.es_boleta():
                if ref.sii_referencia_TpoDocRef:
                    ref_line['TpoDocRef'] = ref.sii_referencia_TpoDocRef.sii_code
                    ref_line['FolioRef'] = ref.origen
                ref_line['FchRef'] = ref.fecha_documento.strftime("%Y-%m-%d") or datetime.strftime(datetime.now(), '%Y-%m-%d')
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

    def _crear_envio(self, RUTRecep="60803000-K"):
        grupos = {}
        batch = 0
        api = False
        for r in self.with_context(lang='es_CL'):
            if not r.document_class_id or not r.sii_document_number:
                continue
            batch += 1
            if not r.sii_batch_number or r.sii_batch_number == 0:
                r.sii_batch_number = batch
            if r.document_class_id.es_boleta():
                api = True
            if (
                self._context.get("set_pruebas", False) or r.sii_result == "Rechazado" or not r.sii_xml_dte
            ):
                r.timestamp_timbre = False
                r._timbrar()
            #@TODO Mejarorar esto en lo posible
            grupos.setdefault(r.document_class_id.sii_code, [])
            grupos[r.document_class_id.sii_code].append({
                'NroDTE': r.sii_batch_number,
                'sii_xml_request': r.sii_xml_dte,
                'Folio': r.get_folio(),
            })
            if r.sii_result in ["Rechazado"] or (
                self._context.get("set_pruebas", False) and r.sii_xml_request.state in ["", "draft", "NoEnviado"]
            ):
                if r.sii_xml_request:
                    if len(r.sii_xml_request.order_ids) == 1:
                        r.sii_xml_request.unlink()
                    else:
                        r.sii_xml_request = False
                r.sii_message = ''
        envio = self[0]._get_datos_empresa(self[0].company_id)
        if self._context.get("set_pruebas", False):
            api = False
        envio.update({
            'api': api,
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


    def do_dte_send(self, n_atencion=None):
        datos = self._crear_envio()
        envio_id = self[0].sii_xml_request
        if not envio_id:
            envio_id = self.env["sii.xml.envio"].create({
                'name': 'temporal',
                'xml_envio': 'temporal',
                'order_ids': [[6,0, self.ids]],
            })
        datos["ID"] = "Env%s" %envio_id.id
        result = fe.timbrar_y_enviar(datos)
        envio = {
                'xml_envio': result.get('sii_xml_request', 'temporal'),
                'name': result.get("sii_send_filename", "temporal"),
                'company_id': self[0].company_id.id,
                'user_id': self.env.uid,
                'sii_send_ident': result.get('sii_send_ident'),
                'sii_xml_response': result.get('sii_xml_response'),
                'state': result.get('status'),
            }
        envio_id.write(envio)
        return envio_id

    def _get_dte_status(self):
        datos = self[0]._get_datos_empresa(self[0].company_id)
        datos['Documento'] = []
        docs = {}
        for r in self:
            if r.sii_xml_request.state not in ['Aceptado', 'Rechazado']:
                continue
            docs.setdefault(r.document_class_id.sii_code, [])
            docs[r.document_class_id.sii_code].append(r._dte())
        if not docs:
            return
        for k, v in docs.items():
            datos['Documento'].append ({
                'TipoDTE': k,
                'documentos': v
            })
        resultado = fe.consulta_estado_documento(datos)
        if not resultado:
            _logger.warning("no resultado en pos")
            return
        for r in self:
            id = "T{}F{}".format(r.document_class_id.sii_code,
                                 r.sii_document_number)
            r.sii_result = resultado[id]['status']
            if resultado[id].get('xml_resp'):
                r.sii_message = resultado[id].get('xml_resp')


    def ask_for_dte_status(self):
        for r in self:
            if not r.sii_xml_request and not r.sii_xml_request.sii_send_ident:
                raise UserError('No se ha enviado aún el documento, aún está en cola de envío interna en odoo')
            if r.sii_xml_request.state not in ['Aceptado', 'Rechazado']:
                r.sii_xml_request.with_context(
                    set_pruebas=self._context.get("set_pruebas", False)).get_send_status(r.env.user)
        try:
            self._get_dte_status()
        except Exception as e:
            _logger.warning("Error al obtener DTE Status: %s" %str(e))

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

    def action_pos_order_paid(self):
        result = super(POS, self).action_pos_order_paid()
        if self.sequence_id and not self.sii_xml_request and self.document_class_id.sii_code not in [33, 34]:
            if (not self.sii_document_number or self.sii_document_number == 0):
                self.sii_document_number = self.sequence_id.next_by_id()
            self.do_validate()
        return result

    @api.onchange('statement_ids', 'lines', 'document_class_id')
    def _onchange_amount_all(self):
        for order in self:
            order.amount_paid = order.amount_return = order.amount_tax = 0.0
            currency = order.pricelist_id.currency_id
            order.amount_paid = sum(payment.amount for payment in order.statement_ids)
            order.amount_return = sum(payment.amount < 0 and payment.amount or 0 for payment in order.statement_ids)
            taxes = {}
            iva = False
            amount_taxed = 0
            amount_total = 0
            for line in order.lines:
                line_taxes = self._amount_line_tax(line, order.fiscal_position_id)
                for t in line_taxes:
                    tax = self.env['account.tax'].browse(t['id'])
                    if order.document_class_id.sii_code in [39] and tax.sii_code in [14, 15]:
                        iva = tax
                        amount_taxed += line.price_subtotal_incl
                        continue
                    taxes.setdefault(t['id'], 0)
                    taxes[t['id']] += t.get('amount', 0.0)
                amount_total += line.price_subtotal_incl
            if order.document_class_id.sii_code in [39]:
                amount_tax = currency.round((amount_taxed /(1+(iva.amount/100.0))) * (iva.amount/100.0))
            else:
                amount_tax = sum(currency.round(t) for k, t in taxes.items())
            order.amount_tax = amount_tax
            order.amount_total = currency.round(amount_total)


    def exento(self):
        exento = 0
        for l in self.lines:
            if l.tax_ids_after_fiscal_position.amount == 0:
                exento += l.price_subtotal
        return exento if exento > 0 else (exento * -1)


    def print_nc(self):
        """ Print NC
        """
        return self.env.ref('l10n_cl_dte_point_of_sale.action_report_pos_boleta_ticket').report_action(self)


    def _get_printed_report_name(self):
        self.ensure_one()
        report_string = "%s %s" % (self.document_class_id.name, self.sii_document_number)
        return report_string


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


class ReportSaleDetails(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, configs=False):
        """ Serialise the orders of the day information

        params: date_start, date_stop string representing the datetime of order
        """
        if not configs:
            configs = self.env['pos.config'].search([])

        user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        today = user_tz.localize(fields.Datetime.from_string(fields.Date.context_today(self)))
        today = today.astimezone(pytz.timezone('UTC'))
        if date_start:
            date_start = fields.Datetime.from_string(date_start)
        else:
            # start by default today 00:00:00
            date_start = today

        if date_stop:
            # set time to 23:59:59
            date_stop = fields.Datetime.from_string(date_stop)
        else:
            # stop by default today 23:59:59
            date_stop = today + timedelta(days=1, seconds=-1)

        # avoid a date_stop smaller than date_start
        date_stop = max(date_stop, date_start)

        date_start = fields.Datetime.to_string(date_start)
        date_stop = fields.Datetime.to_string(date_stop)

        orders = self.env['pos.order'].search([
            ('date_order', '>=', date_start),
            ('date_order', '<=', date_stop),
            ('state', 'in', ['paid','invoiced','done']),
            ('config_id', 'in', configs.ids)])

        user_currency = self.env.user.company_id.currency_id

        total = 0.0
        products_sold = {}
        taxes = {}
        for order in orders:
            if user_currency != order.pricelist_id.currency_id:
                total += order.pricelist_id.currency_id.compute(order.amount_total, user_currency)
            else:
                total += order.amount_total
            currency = order.session_id.currency_id

            for line in order.lines:
                key = (line.product_id, line.price_unit, line.discount)
                products_sold.setdefault(key, 0.0)
                products_sold[key] += line.qty

                if line.tax_ids_after_fiscal_position:
                    line_taxes = line.tax_ids_after_fiscal_position.with_context(date=order.date_order, currency=currency).compute_all(line.price_unit, currency, line.qty, product=line.product_id, partner=line.order_id.partner_id or False, discount=line.discount, uom_id=line.product_id.uom_id)
                    for tax in line_taxes['taxes']:
                        taxes.setdefault(tax['id'], {'name': tax['name'], 'tax_amount':0.0, 'base_amount':0.0})
                        taxes[tax['id']]['tax_amount'] += tax['amount']
                        taxes[tax['id']]['base_amount'] += tax['base']
                else:
                    taxes.setdefault(0, {'name': _('No Taxes'), 'tax_amount':0.0, 'base_amount':0.0})
                    taxes[0]['base_amount'] += line.price_subtotal_incl

        st_line_ids = self.env["account.bank.statement.line"].search([('pos_statement_id', 'in', orders.ids)]).ids
        if st_line_ids:
            self.env.cr.execute("""
                SELECT aj.name, sum(amount) total
                FROM account_bank_statement_line AS absl,
                     account_bank_statement AS abs,
                     account_journal AS aj
                WHERE absl.statement_id = abs.id
                    AND abs.journal_id = aj.id
                    AND absl.id IN %s
                GROUP BY aj.name
            """, (tuple(st_line_ids),))
            payments = self.env.cr.dictfetchall()
        else:
            payments = []

        return {
            'currency_precision': user_currency.decimal_places,
            'total_paid': user_currency.round(total),
            'payments': payments,
            'company_name': self.env.user.company_id.name,
            'taxes': list(taxes.values()),
            'products': sorted([{
                'product_id': product.id,
                'product_name': product.name,
                'code': product.default_code,
                'quantity': qty,
                'price_unit': price_unit,
                'discount': discount,
                'uom': product.uom_id.name
            } for (product, price_unit, discount), qty in products_sold.items()], key=lambda l: l['product_name'])
        }
