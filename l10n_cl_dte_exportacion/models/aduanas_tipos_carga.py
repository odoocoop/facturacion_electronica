# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class AduansTiposCarga(models.Model):
    _name = 'aduanas.tipos_carga'

    name = fields.Char(
            string= 'Nombre',
        )
    code = fields.Char(
            string="Código",
        )
    descripcion = fields.Char(
            string="Descripción",
        )
