# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.tools.translate import _
from odoo.exceptions import Warning
import logging
_logger = logging.getLogger(__name__)

class SOL(models.Model):
    _inherit = 'sale.order.line'

    @api.multi
    def _prepare_procurement_values(self, group_id=False):
        result = super(SOL, self)._prepare_procurement_values(group_id)
        self.ensure_one()
        result.update({
                'precio_unitario': self.price_unit,
                'discount': self.discount,
                'move_line_tax_ids': self.tax_id.ids,
                'currency_id': self.currency_id.id,
            })
        return result
