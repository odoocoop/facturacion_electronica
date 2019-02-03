# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from datetime import datetime, timedelta
import dateutil.relativedelta as relativedelta
import pytz
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
import logging
_logger = logging.getLogger(__name__)

class PickingToInvoiceD(models.Model):
    _inherit = 'account.invoice'

    @api.depends('partner_id')
    @api.onchange('partner_id')
    def _get_pending_pickings(self ):
        for inv in self:
            if not inv.partner_id or inv.type in ['out_refund', 'in_refund', 'in_invoice']:
                continue
            if inv.type in ['out_invoice']:
                mes_antes = 0
                if inv.date_invoice:
                    date_invoice = datetime.strptime( inv.date_invoice, '%Y-%m-%d' )
                    fecha_inicio = "%s-%s-01 00:00:00" % (date_invoice.year, date_invoice.month)
                    fecha_final = "%s-%s-11 00:00:00" % (date_invoice.year, date_invoice.month)
                    if date_invoice.day == 10:
                        mes_antes -=1
                else:
                    now = datetime.now()
                    fecha_inicio = "%s-%s-01 00:00:00" % (now.year, now.month)
                    next_month = now + relativedelta.relativedelta(months=1)
                    fecha_final = "%s-%s-11 00:00:00" % (next_month.year, next_month.month)
                    if now.day == 10:
                        mes_antes -=1
                tz = pytz.timezone('America/Santiago')
                tz_current = (tz.localize(datetime.strptime(fecha_inicio, DTF)).astimezone(pytz.utc) + relativedelta.relativedelta(months=mes_antes))
                tz_next = tz.localize(datetime.strptime(fecha_final, DTF)).astimezone(pytz.utc)
                pickings = self.env['stock.picking'].search(
                    [
                        ('invoiced', '=', False),
                        ('sii_result', 'in', ['Proceso', 'Reparo']),
                        ('partner_id.commercial_partner_id', '=', inv.commercial_partner_id.id),
                        ('date','>=', tz_current.strftime(DTF)),
                        ('date','<', tz_next.strftime(DTF)),
                    ]
                )
                inv.update({
                        'has_pending_pickings': len(pickings.ids),
                        'picking_pending_ids': pickings.ids,
                        })

    has_pending_pickings = fields.Integer(
        string="Pending Pickings",
        compute='_get_pending_pickings',
        default=0,
    )
    picking_pending_ids = fields.Many2many(
            "stock.picking",
            string='Invoices',
            compute="_get_pending_pickings",
            readonly=True,
            copy=False,
        )

    @api.multi
    def invoice_validate(self):
        result  = super(PickingToInvoiceD, self).invoice_validate()
        for inv in self:
            sp = False
            if inv.move_id:
                for ref in inv.referencias:
                    if ref.sii_referencia_TpoDocRef.sii_code in [ 56 ]:
                        sp = self.env['stock_picking'].search([('sii_document_number', '=', ref.origen)])
                if sp:
                    if inv.type in ['out_invoice']:
                        sp.invoiced = True
                    else:
                        sp.invoiced = False
        return result

    @api.multi
    def action_view_pickings(self):
        picking_pending_ids = self.mapped('picking_pending_ids')
        action = self.env.ref('stock.action_picking_tree_all').read()[0]#cambiar por wizard seleccionable
        action['domain'] = [('id', 'in', picking_pending_ids.ids)]
        return action
