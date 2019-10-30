# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)


class ProcessMailsDocument(models.Model):
    _name = 'mail.message.dte.document'
    _description = "Pre Documento Recibido"
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
            created.extend(val.confirm(ret=True))
            r.state = 'accepted'
        xml_id = 'account.action_vendor_bill_template'
        result = self.env.ref('%s' % (xml_id)).read()[0]
        if created:
            domain = safe_eval(result.get('domain', '[]'))
            domain.append(('id', 'in', created))
            result['domain'] = domain
        return result

    @api.multi
    def reject_document(self):
        for r in self:
            r.state = 'rejected'

        wiz_accept = self.env['sii.dte.validar.wizard'].create(
            {
                'action': 'validate',
                'option': 'reject',
            }
        )
        wiz_accept.do_reject(self)


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