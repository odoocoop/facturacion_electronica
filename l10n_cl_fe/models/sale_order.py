from odoo import api, fields, models
from odoo.tools.translate import _


class SO(models.Model):
    _inherit = 'sale.order'

    acteco_ids = fields.Many2many(
        'partner.activities',
        related="partner_invoice_id.acteco_ids",
    )
    acteco_id = fields.Many2one(
        'partner.activities',
        string='Partner Activity',
    )
    referencia_ids = fields.One2many(
        'sale.order.referencias',
        'so_id',
        string="Referencias de documento"
    )

    @api.multi
    def _prepare_invoice(self):
        vals = super(SO, self)._prepare_invoice()
        if self.acteco_id:
            vals['acteco_id'] = self.acteco_id.id
        if self.referencia_ids:
            vals['referencias'] = []
            for ref in self.referencia_ids:
                vals['referencias'].append(
                    (0, 0, {
                        'origen': ref.folio,
                        'sii_referencia_TpoDocRef': ref.sii_referencia_TpoDocRef.id,
                        'motivo': ref.motivo,
                        'fecha_documento': ref.fecha_documento,
                    })
                )
        return vals

