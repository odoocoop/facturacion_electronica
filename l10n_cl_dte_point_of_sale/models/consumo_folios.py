# -*- coding: utf-8 -*-
from odoo import fields, models, api, tools
from odoo.tools.translate import _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import dateutil.relativedelta as relativedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
import pytz
import logging

_logger = logging.getLogger(__name__)

class ConsumoFolios(models.Model):
    _inherit = "account.move.consumo_folios"

    order_ids = fields.Many2many(
        'pos.order',
        string="Order IDs",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    def _get_moves(self):
        recs = super(ConsumoFolios, self)._get_moves()
        for order in self.order_ids.filtered(lambda a: a.sii_document_number and a.document_class_id.es_boleta()):
            recs.append(order)
        return recs

    @api.onchange("move_ids", "anulaciones", "order_ids")
    def _resumenes(self):
        return super(ConsumoFolios, self)._resumenes()

    @api.onchange("fecha_inicio", "company_id", "fecha_final")
    def set_data(self):
        super(ConsumoFolios, self).set_data()
        self.order_ids = False
        tz = pytz.timezone('America/Santiago')
        fecha_inicio = datetime.strptime(self.fecha_inicio.strftime(DTF), DTF)
        tz_current = tz.localize(fecha_inicio).astimezone(pytz.utc)
        current = tz_current.strftime(DTF)
        next_day = tz.localize(fecha_inicio + relativedelta.relativedelta(
            days=1)).astimezone(pytz.utc)
        self.order_ids = self.env['pos.order'].search(
            [
             #('is_invoiced', '=', False),
             ('sii_document_number', 'not in', [False, '0']),
             ('document_class_id.sii_code', 'in', [39, 41, 61]),
             ('date_order','>=', current),
             ('date_order','<', next_day),
            ]
        ).with_context(lang='es_CL')
