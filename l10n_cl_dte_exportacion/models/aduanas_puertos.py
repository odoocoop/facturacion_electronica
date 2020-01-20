# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class AduanasPuertos(models.Model):
    _name = 'aduanas.puertos'

    name = fields.Char(
            string= 'Nombre',
        )
    code = fields.Char(
            string="Código",
        )
    country_id = fields.Many2one(
            'res.country',
            string='País',
        )
