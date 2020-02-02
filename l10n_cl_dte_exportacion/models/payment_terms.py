# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class PaymenTerms(models.Model):
    _inherit = "account.payment.term"

    modalidad_venta = fields.Many2one(
            'aduanas.modalidades_venta',
            string="Modalidad Venta"
        )
    forma_pago_aduanas = fields.Many2one(
            'aduanas.formas_pago',
            string="Forma de Pago Aduanas",
        )
