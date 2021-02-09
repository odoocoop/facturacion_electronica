# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import dateutil.relativedelta as relativedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
import pytz
import logging
_logger = logging.getLogger(__name__)


class SIIResumenBoletaVoucher(models.Model):
    _inherit = 'account.move.boleta_voucher'

    order_ids = fields.Many2many(
        'pos.order',
        readonly=True,
        states={'draft': [('readonly', False)]},
    )

    def _get_moves(self):
        recs = super(SIIResumenBoletaVoucher, self)._get_moves()
        for r in self.order_ids:
            recs.append(r)
        return recs

    @api.onchange('move_ids', 'order_ids')
    def set_totales(self):
        super(SIIResumenBoletaVoucher, self).set_totales()

    @api.onchange('periodo', 'company_id', 'medios_de_pago')
    def set_movimientos(self):
        super(SIIResumenBoletaVoucher, self).set_movimientos()
        if not self.medios_de_pago:
            return
        periodo = self.periodo + '-01 00:00:00'
        tz = pytz.timezone('America/Santiago')
        tz_current = tz.localize(datetime.strptime(periodo, DTF)).astimezone(pytz.utc)
        current = tz_current.strftime(DTF)
        next_month = (tz_current + relativedelta.relativedelta(months=1)).strftime(DTF)
        query = [
            ('sii_referencia_TpoDocRef.sii_code', 'in', [39, 41]),
            ('sii_referencia_CodRef', 'in', ['1', '3']),
            ('order_id.date_order', '>=', current),
            ('order_id.date_order', '<=', next_month),
            ('order_id.statement_ids.statement_id.journal_id', 'in', self.medios_de_pago.ids),
            ('order_id.statement_ids.company_id', '=', self.company_id.id),
        ]
        ncs = self.env['pos.order.referencias'].search(query)
        query = [
            ('sii_document_number', 'not in', [False, '0']),
            ('document_class_id.sii_code', 'in', [39, 41]),
            ('date_order', '>=', current),
            ('date_order', '<=', next_month),
            ('statement_ids.journal_id', 'in', self.medios_de_pago.ids),
            ('company_id', '=', self.company_id.id),
        ]
        nc_orders = self.env['pos.order']
        for nc in ncs:
            o = self.env['pos.order.referencias'].search([
                ('sii_document_number', '=', nc.origen),
                ('document_class_id', '=', nc.sii_referencia_TpoDocRef.id),
            ])
            nc_orders += o
        if nc_orders:
            query.append(('id', 'not in', nc_orders.ids))
        self.order_ids = self.env['pos.order'].search(query)
