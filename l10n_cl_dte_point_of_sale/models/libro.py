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


class Libro(models.Model):
    _inherit = "account.move.book"

    order_ids = fields.Many2many("pos.order", readonly=True, states={"draft": [("readonly", False)]})

    def _get_date(self, rec):
        if 'date_order' not in rec:
            return super(Libro, self)._get_date(rec)
        util_model = self.env['cl.utils']
        fields_model = self.env['ir.fields.converter']
        from_zone = pytz.UTC
        to_zone = pytz.timezone('America/Santiago')
        date_order = util_model._change_time_zone(datetime.strptime(rec.date_order, DTF), from_zone, to_zone).strftime(DTF)
        til_model = self.env['cl.utils']
        fields_model = self.env['ir.fields.converter']
        from_zone = pytz.UTC
        to_zone = pytz.timezone('America/Santiago')
        date_order = util_model._change_time_zone(datetime.strptime(rec.date_order, DTF), from_zone, to_zone).strftime(DTF)
        return {
            'FchEmiDoc': date_order[:10],
            'FchVencDoc': date_order[:10]
        }

    def _get_datos(self, rec):
        if 'line_ids' in rec:
            return super(Libro, self)._get_datos(rec)
        TaxMnt =  rec.amount_tax
        Neto = rec.pricelist_id.currency_id.round(sum(line.price_subtotal for line in rec.lines))
        MntExe = rec.exento()
        TasaIVA = self.env['pos.order.line'].search([('order_id', '=', rec.id), ('tax_ids.amount', '>', 0)], limit=1).tax_ids.amount
        Neto -= MntExe
        return Neto, MntExe, TaxMnt, TasaIVA

    def _get_moves(self):
        recs = super(Libro, self)._get_moves()
        if self.tipo_operacion != 'BOLETA':
            return recs
        for rec in self.with_context(lang='es_CL').order_ids:
            if rec.documet_class_id and not rec.sii_document_number:
                orders = sorted(self.env['pos.order'].search(
                        [('account_move', '=', rec.id),
                         ('invoice_id' , '=', False),
                         ('sii_document_number', 'not in', [False, '0']),
                         ('document_class_id.sii_code', 'in', [39, 41]),
                        ]).with_context(lang='es_CL'), key=lambda r: r.sii_document_number)
                for r in orders:
                    recs.append(r)
        return recs

    @api.onchange("move_ids", 'order_ids')
    def set_resumen(self):
        for book in self:
            for o in book.order_ids:
                book.total_afecto += o.amount_total - o.amount_tax- o.exento()
                book.total_exento += o.exento()
                book.total_iva += o.amount_tax
                book.total += o.amount_total
        return super(Libro, self).set_resumen()

    @api.onchange("move_ids", "order_ids")
    def compute_taxes(self):
        return super(Libro, self).compute_taxes()

    def _get_imps(self):
        imp = {}
        for move in self.order_ids:
            move_imps = move._get_move_imps()
            for key, i in move_imps.items():
                if key not in imp:
                    imp[key] = i
                else:
                    imp[key]["credit"] += i["credit"]
                    imp[key]["debit"] += i["debit"]
        return imp
