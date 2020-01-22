# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class ResCountry(models.Model):
    _inherit = 'res.country'

    aduanas_id = fields.Many2one(
            'aduanas.paises',
            string="Código Aduanas",
        )
