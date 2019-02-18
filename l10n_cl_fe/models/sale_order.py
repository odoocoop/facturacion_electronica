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

    @api.multi
    def _prepare_invoice(self):
        vals = super(SO, self)._prepare_invoice()
        if self.acteco_id:
            vals['acteco_id'] = self.acteco_id.id
        return vals

