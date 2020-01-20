# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class AduanasModalidadesVenta(models.Model):
    _name = 'aduanas.modalidades_venta'

    name = fields.Char(
            string= 'Nombre',
        )
    code = fields.Char(
            string="Código",
        )
    sigla = fields.Char(
            string="Sigla",
        )
