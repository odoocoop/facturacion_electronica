# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class AduanasUnidadesMedida(models.Model):
    _inherit = 'uom.uom'

    code = fields.Char(
            string="Código Aduanas",
        )
