# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class AduanasPaises(models.Model):
    _name = 'aduanas.paises'

    name = fields.Char(
            string= 'Nombre',
        )
    code = fields.Char(
            string="Código",
        )
    abreviatura = fields.Char(
            string="Abreviatura",
        )
