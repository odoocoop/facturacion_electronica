# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api,fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_compare

from itertools import groupby

class StockPicking(models.Model):
    _inherit='stock.picking'

    @api.model
    def _create_picking_from_pos_order_lines(self, location_dest_id, lines, picking_type, partner=False):
        """We'll create some picking based on order_lines"""

        pickings = self.env['stock.picking']
        stockable_lines = lines.filtered(lambda l: l.product_id.type in ['product', 'consu'] and not float_is_zero(l.qty, precision_rounding=l.product_id.uom_id.rounding))
        if not stockable_lines:
            return pickings
        positive_lines = stockable_lines.filtered(lambda l: l.qty > 0)
        negative_lines = stockable_lines - positive_lines

        if positive_lines:
            location_id = picking_type.default_location_src_id.id
            picking_vals = self._prepare_picking_vals(partner, picking_type, location_id, location_dest_id)
            if positive_lines:
                order = positive_lines[0].order_id
                if order.config_id.dte_picking:
                    if order.config_id.dte_picking_option == 'all' or (not order.document_class_id and order.config_id.dte_picking_option == 'no_tributarios'):
                        picking_vals.update({
                            'use_documents': True,
                            'move_reason': order.config_id.dte_picking_move_type,
                            'transport_type': order.config_id.dte_picking_transport_type,
                            'dte_ticket': order.config_id.dte_picking_ticket,
                        })
            positive_picking = self.env['stock.picking'].create(picking_vals)

            positive_picking._create_move_from_pos_order_lines(positive_lines)
            try:
                with self.env.cr.savepoint():
                    positive_picking._action_done()
            except (UserError, ValidationError):
                pass

            pickings |= positive_picking
        if negative_lines:
            if picking_type.return_picking_type_id:
                return_picking_type = picking_type.return_picking_type_id
                return_location_id = return_picking_type.default_location_dest_id.id
            else:
                return_picking_type = picking_type
                return_location_id = picking_type.default_location_src_id.id

            negative_picking = self.env['stock.picking'].create(
                self._prepare_picking_vals(partner, return_picking_type, location_dest_id, return_location_id)
            )
            negative_picking._create_move_from_pos_order_lines(negative_lines)
            try:
                with self.env.cr.savepoint():
                    negative_picking._action_done()
            except (UserError, ValidationError):
                pass
            pickings |= negative_picking
        return pickings


    def _prepare_stock_move_vals(self, first_line, order_lines):
        result = super(StockPicking, self)._prepare_stock_move_vals(first_line, order_lines)
        if self.env['ir.module.module'].sudo().search([('name', '=', 'l10n_cl_stock_picking'), ('state', 'in', ['installed', 'to upgrade'])]):
            if result:
                result.update({
                    'precio_unitario': first_line.price_unit,
                    'move_line_tax_ids': [(6,0, first_line.tax_ids_after_fiscal_position.filtered(lambda t: t.company_id.id == first_line.order_id.company_id.id).ids)],
                })
        return result
