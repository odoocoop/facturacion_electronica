# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import logging
_logger = logging.getLogger(__name__)


class Bultos(models.Model):
    _name = 'account.invoice.bultos'
    _description = "Bultos de la exportación"

    invoice_id = fields.Many2one(
            'account.invoice',
        )
    tipo_bulto = fields.Many2one(
            'aduanas.tipos_bulto',
            string='Tipo de Bulto',
        )
    tipo_bulto_code = fields.Char(
            related="tipo_bulto.code"
        )
    cantidad_bultos = fields.Integer(
            string="Cantidad de Bultos",
        )
    marcas = fields.Char(
            string="Identificación de marcas",
        )
    id_container = fields.Char(
            string="Id Container"
        )
    sello = fields.Char(
            string="Sello"
        )
    emisor_sello = fields.Char(
            string="Emisor Sello"
        )
