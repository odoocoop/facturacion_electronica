# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import logging
_logger = logging.getLogger(__name__)


class Exportacion(models.Model):
    _name = "account.invoice.exportacion"
    _description = "Detalle Exportacion"

    pais_destino = fields.Many2one(
            'aduanas.paises',
            string='País de Destino',
        )
    puerto_embarque = fields.Many2one(
            'aduanas.puertos',
            string='Puerto Embarque',
        )
    puerto_desembarque = fields.Many2one(
            'aduanas.puertos',
            string='Puerto de Desembarque',
        )
    total_items = fields.Integer(
            string="Total Items",
        )
    total_bultos = fields.Integer(
            string="Total Bultos",
        )
    via = fields.Many2one(
            'aduanas.tipos_transporte',
            string='Vía',
        )
    carrier_id = fields.Many2one(
            'delivery.carrier',
            string="Transporte",
        )
    tara = fields.Integer(
            string="Tara",
        )
    uom_tara = fields.Many2one(
            'product.uom',
            string='Unidad Medida Tara',
        )
    peso_bruto = fields.Float(
            string="Peso Bruto",
        )
    uom_peso_bruto = fields.Many2one(
            'product.uom',
            string='Unidad Medida Peso Bruto',
        )
    peso_neto = fields.Float(
            string="Peso Neto",
        )
    uom_peso_neto = fields.Many2one(
            'product.uom',
            string='Unidad Medida Peso Neto',
        )
    monto_flete = fields.Monetary(
            string="Monto Flete",
        )
    monto_seguro = fields.Monetary(
            string="Monto Seguro",
        )
    pais_recepcion = fields.Many2one(
            'aduanas.paises',
            string='País de Recepción',
        )
    chofer_id = fields.Many2one(
            'res.partner',
            string="Chofer"
        )
    currency_id = fields.Many2one(
            'res.currency',
            string='Moneda'
        )

    @api.onchange('carrier_id')
    def set_chofer(self):
        if self.carrier_id and not self.chofer_id:
            self.chofer_id = self.carrier_id.partner_id

    @api.onchange('pais_destino')
    def set_recepcion(self):
        if not self.pais_recepcion:
            self.pais_recepcion = self.pais_destino
