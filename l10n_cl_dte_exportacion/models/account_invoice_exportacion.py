# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import logging
_logger = logging.getLogger(__name__)


class Exportacion(models.Model):
    _name = "account.invoice.exportacion"

    @api.onchange('bultos')
    @api.depends('bultos')
    def tot_bultos(self):
        for r in self:
            _logger.warning(r)
            tot_bultos = 0
            for b in r.bultos:
                tot_bultos += b.cantidad_bultos
            r.total_bultos = tot_bultos

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
            compute='tot_bultos',
        )
    bultos = fields.One2many(
        string="Bultos",
        comodel_name="account.invoice.exportacion.bultos",
        inverse_name="exportacion_id",
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

class Bultos(models.Model):
    _name = 'account.invoice.exportacion.bultos'

    tipo_bulto = fields.Many2one(
            'aduanas.tipos_bulto',
            string='Tipo de Bulto',
        )
    cantidad_bultos = fields.Integer(
            string="Cantidad de Bultos",
        )
    marcas = fields.Char(
        string="Identificación de marcas",
    )
    exportacion_id = fields.Many2one(
            'account.invoice.exportacion',
        )
