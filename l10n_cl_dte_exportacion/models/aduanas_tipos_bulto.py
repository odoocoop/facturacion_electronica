# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class AduanasTiposBulto(models.Model):
    _name = 'aduanas.tipos_bulto'

    name = fields.Char(
            string= 'Nombre',
        )
    code = fields.Char(
            string="Código",
        )
    sigla = fields.Char(
            string="Sigla",
        )
