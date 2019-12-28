# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)


class ProcessMailsDocument(models.Model):
    _name = 'mail.message.dte.document'
    _description = "Pre Document"
    _inherit = ['mail.thread']

    dte_id = fields.Many2one(
        'mail.message.dte',
        string="DTE",
        readonly=True,
        ondelete='cascade',
    )
    new_partner = fields.Char(
        string="Proveedor Nuevo",
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        domain=[('supplier', '=', True)],
    )
    date = fields.Date(
        string="Fecha Emsisión",
        readonly=True,
    )
    number = fields.Char(
        string='Folio',
        readonly=True,
    )
    document_class_id = fields.Many2one(
        'sii.document_class',
        string="Tipo de Documento",
        readonly=True,
        oldname="sii_document_class_id",
    )
    amount = fields.Monetary(
        string="Monto",
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string="Moneda",
        readonly=True,
        default=lambda self: self.env.user.company_id.currency_id,
    )
    invoice_line_ids = fields.One2many(
        'mail.message.dte.document.line',
        'document_id',
        string="Líneas del Documento",
    )
    company_id = fields.Many2one(
        'res.company',
        string="Compañía",
        readonly=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Recibido'),
            ('accepted', 'Aceptado'),
            ('rejected', 'Rechazado'),
        ],
        default='draft',
    )
    invoice_id = fields.Many2one(
        'account.invoice',
        string="Factura",
        readonly=True,
    )
    xml = fields.Text(
        string="XML Documento",
        readonly=True,
    )
    purchase_to_done = fields.Many2many(
        'purchase.order',
        string="Ordenes de Compra a validar",
        domain=[('state', 'not in', ['accepted', 'rejected'])],
    )
    claim = fields.Selection(
        [
            ('N/D', "No definido"),
            ('ACD', 'Acepta Contenido del Documento'),
            ('RCD', 'Reclamo al  Contenido del Documento '),
            ('ERM', ' Otorga  Recibo  de  Mercaderías  o Servicios'),
            ('RFP', 'Reclamo por Falta Parcial de Mercaderías'),
            ('RFT', 'Reclamo por Falta Total de Mercaderías'),
        ],
        string="Reclamo",
        copy=False,
        default="N/D",
    )
    claim_description = fields.Char(
        string="Detalle Reclamo",
        readonly=True,
    )

    _order = 'create_date DESC'

    @api.model
    def auto_accept_documents(self):
        self.env.cr.execute(
            """
            select
                id
            from
                mail_message_dte_document
            where
                create_date + interval '8 days' < now()
                and
                state = 'draft'
            """
        )
        for d in self.browse([line.get('id') for line in \
                              self.env.cr.dictfetchall()]):
            d.accept_document()

    @api.multi
    def accept_document(self):
        created = []
        for r in self:
            vals = {
                'xml_file': r.xml.encode('ISO-8859-1'),
                'filename': r.dte_id.name,
                'pre_process': False,
                'document_id': r.id,
                'option': 'accept'
            }
            val = self.env['sii.dte.upload_xml.wizard'].create(vals)
            resp = val.confirm(ret=True)
            created.extend(resp)
            r.get_dte_claim()
            for i in self.env['account.invoice'].browse(resp):
                if i.claim in ['ACD', 'ERM']:
                    r.state = 'accepted'
        xml_id = 'account.action_invoice_tree2'
        result = self.env.ref('%s' % (xml_id)).read()[0]
        if created:
            domain = safe_eval(result.get('domain', '[]'))
            domain.append(('id', 'in', created))
            result['domain'] = domain
        return result

    @api.multi
    def reject_document(self):
        for r in self:
            r.set_dte_claim(claim='RCD')
            if r.claim in ['RCD']:
                r.state = 'rejected'

    def set_dte_claim(self, claim):
        if self.document_class_id.sii_code not in [33, 34, 43]:
            self.claim = claim
            return
        if not self.partner_id:
            rut_emisor = self.new_partner.split(' ')[0]
        else:
            rut_emisor = self.env['account.invoice'].format_vat(
                    self.partner_id.vat)
        token = self.env['sii.xml.envio'].get_token(self.env.user, self.company_id)
        url = claim_url[self.company_id.dte_service_provider] + '?wsdl'
        _server = Client(
            url,
            headers= {
                'Cookie': 'TOKEN=' + token,
                },
        )
        try:
            respuesta = _server.service.ingresarAceptacionReclamoDoc(
                rut_emisor[:-2],
                rut_emisor[-1],
                str(self.document_class_id.sii_code),
                str(self.number),
                claim,
            )
        except Exception as e:
                msg = "Error al ingresar Reclamo DTE"
                _logger.warning("%s: %s" % (msg, str(e)))
                if e.args[0][0] == 503:
                    raise UserError('%s: Conexión al SII caída/rechazada o el SII está temporalmente fuera de línea, reintente la acción' % (msg))
                raise UserError(("%s: %s" % (msg, str(e))))
        self.claim_description = respuesta
        if respuesta.codResp in [0, 7]:
            self.claim = claim

    @api.multi
    def get_dte_claim(self):
        if not self.partner_id:
            rut_emisor = self.new_partner.split(' ')[0]
        else:
            rut_emisor = self.env['account.invoice'].format_vat(
                    self.partner_id.vat)
        token = self.env['sii.xml.envio'].get_token(self.env.user, self.company_id)
        url = claim_url[self.company_id.dte_service_provider] + '?wsdl'
        _server = Client(
            url,
            headers= {
                'Cookie': 'TOKEN=' + token,
                },
        )
        try:
            respuesta = _server.service.listarEventosHistDoc(
                rut_emisor[:-2],
                rut_emisor[-1],
                str(self.document_class_id.sii_code),
                str(self.number),
            )
            self.claim_description = respuesta
        except Exception as e:
            _logger.warning("Error al obtener aceptación %s" %(str(e)))
            if self.company_id.dte_service_provider == 'SII':
                raise UserError("Error al obtener aceptación: %s" % str(e))


class ProcessMailsDocumentLines(models.Model):
    _name = 'mail.message.dte.document.line'
    _description = "Pre Document Line"
    _order = 'sequence, id'

    document_id = fields.Many2one(
        'mail.message.dte.document',
        string="Documento",
        ondelete='cascade',
    )
    sequence = fields.Integer(
        string="Número de línea",
        default=1
    )
    product_id = fields.Many2one(
        'product.product',
        string="Producto",
    )
    new_product = fields.Char(
        string='Nuevo Producto',
        readonly=True,
    )
    description = fields.Char(
        string='Descripción',
        readonly=True,
    )
    product_description = fields.Char(
        string='Descripción Producto',
        readonly=True,
    )
    quantity = fields.Float(
        string="Cantidad",
        readonly=True,
    )
    price_unit = fields.Monetary(
        string="Precio Unitario",
        readonly=True,
    )
    price_subtotal = fields.Monetary(
        string="Total",
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string="Moneda",
        readonly=True,
        default=lambda self: self.env.user.company_id.currency_id,
    )
