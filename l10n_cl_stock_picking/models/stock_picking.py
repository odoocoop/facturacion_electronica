# -*- coding: utf-8 -*-
from odoo import osv, models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import except_orm, UserError
import odoo.addons.decimal_precision as dp
from odoo.tools.float_utils import float_compare, float_round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import logging
_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.onchange('currency_id', 'move_lines', 'move_reason')
    def _compute_amount(self):
        for rec in self:
            amount_untaxed = 0
            amount_tax = 0
            if rec.move_reason not in ['5']:
                taxes = {}
                if rec.move_lines:
                    for move in rec.move_lines:
                        if move.move_line_tax_ids:
                            for t in move.move_line_tax_ids:
                                taxes.setdefault(t, 0)
                                taxes[t] += move.subtotal
                if taxes:
                    for t, value in taxes.items():
                        amount_tax += t.compute_all(value, rec.currency_id, 1)['taxes'][0]['amount']
                        amount_untaxed += t.compute_all(value, rec.currency_id, 1)['total_excluded']
                rec.amount_tax = amount_tax
                rec.amount_untaxed = amount_untaxed
            rec.amount_total = amount_untaxed + amount_tax

    def set_use_document(self):
        return (self.picking_type_id and self.picking_type_id.code != 'incoming')

    amount_untaxed = fields.Monetary(
            compute='_compute_amount',
            digits=dp.get_precision('Account'),
            string='Untaxed Amount',
        )
    amount_tax = fields.Monetary(
            compute='_compute_amount',
            digits=dp.get_precision('Account'),
            string='Taxes',
        )
    amount_total = fields.Monetary(
            compute='_compute_amount',
            digits=dp.get_precision('Account'),
            string='Total',
        )
    currency_id = fields.Many2one(
            'res.currency',
            string='Currency',
            required=True,
            states={'draft': [('readonly', False)]},
            default=lambda self: self.env.user.company_id.currency_id.id,
            track_visibility='always',
        )
    sii_batch_number = fields.Integer(
            copy=False,
            string='Batch Number',
            readonly=True,
            help='Batch number for processing multiple invoices together',
        )
    activity_description = fields.Many2one(
            'sii.activity.description',
            string='Giro',
            related="partner_id.commercial_partner_id.activity_description",
            readonly=True, states={'assigned':[('readonly',False)],'draft':[('readonly',False)]},
        )
    sii_document_number = fields.Char(
            string='Document Number',
            copy=False,
            readonly=True,
        )
    responsability_id = fields.Many2one(
            'sii.responsability',
            string='Responsability',
            related='partner_id.commercial_partner_id.responsability_id',
            store=True,
        )
    next_number = fields.Integer(
            related='picking_type_id.sequence_id.number_next_actual',
            string='Next Document Number',
            readonly=True,
        )
    use_documents = fields.Boolean(
            string='Use Documents?',
            default=set_use_document,
        )
    reference = fields.One2many(
            'stock.picking.referencias',
            'stock_picking_id',
            readonly=False,
            states={'done':[('readonly',True)]},
        )
    transport_type = fields.Selection(
            [
                ('2', 'Despacho por cuenta de empresa'),
                ('1', 'Despacho por cuenta del cliente'),
                ('3', 'Despacho Externo'),
                ('0', 'Sin Definir')
            ],
            string="Tipo de Despacho",
            default="2",
            readonly=False, states={'done':[('readonly',True)]},
        )
    move_reason = fields.Selection(
            [
                    ('1', 'Operación constituye venta'),
                    ('2', 'Ventas por efectuar'),
                    ('3', 'Consignaciones'),
                    ('4', 'Entrega Gratuita'),
                    ('5', 'Traslados Internos'),
                    ('6', 'Otros traslados no venta'),
                    ('7', 'Guía de Devolución'),
                    ('8', 'Traslado para exportación'),
                    ('9', 'Ventas para exportación')
            ],
            string='Razón del traslado',
            default="1",
            readonly=False, states={'done':[('readonly',True)]},
        )
    vehicle = fields.Many2one(
            'fleet.vehicle',
            string="Vehículo",
            readonly=False,
            states={'done': [('readonly', True)]},
        )
    chofer = fields.Many2one(
            'res.partner',
            string="Chofer",
            readonly=False,
            states={'done': [('readonly', True)]},
        )
    patente = fields.Char(
            string="Patente",
            readonly=False,
            states={'done': [('readonly', True)]},
        )
    contact_id = fields.Many2one(
            'res.partner',
            string="Contacto",
            readonly=False,
            states={'done': [('readonly', True)]},
        )
    invoiced = fields.Boolean(
            string='Invoiced?',
            readonly=True,
    )

    @api.onchange('picking_type_id')
    def onchange_picking_type(self,):
        if self.picking_type_id:
            self.use_documents = self.picking_type_id.code not in ["incoming"]

    @api.onchange('company_id')
    def _refreshData(self):
        if self.move_lines:
            for m in self.move_lines:
                m.company_id = self.company_id.id

    @api.onchange('vehicle')
    def _setChofer(self):
        self.chofer = self.vehicle.driver_id
        self.patente = self.vehicle.license_plate


class Referencias(models.Model):
    _name = 'stock.picking.referencias'

    origen = fields.Char(
            string="Origin",
        )
    sii_referencia_TpoDocRef = fields.Many2one(
            'sii.document_class',
            string="SII Reference Document Type",
        )
    date = fields.Date(
            string="Fecha de la referencia",
        )
    stock_picking_id = fields.Many2one(
            'stock.picking',
            ondelete='cascade',
            index=True,
            copy=False,
            string="Documento",
        )


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model
    def create(self, vals):
        if 'picking_id' in vals:
            picking = self.env['stock.picking'].browse(vals['picking_id'])
            if picking and picking.company_id:
                vals['company_id'] = picking.company_id.id
        return super(StockMove, self).create(vals)

    def _set_price_from(self):
        if self.picking_id.reference:
            for ref in self.picking_id.reference:
                if ref.sii_referencia_TpoDocRef.sii_code in [33]:
                    il = self.env['account.invoice'].search(
                            [
                                    ('sii_document_number', '=', ref.origen),
                                    ('sii_document_class_id.sii_code', '=', ref.sii_referencia_TpoDocRef.sii_code),
                                    ('product_id', '=', self.product_id.id),
                            ]
                        )
                    if il:
                        self.precio_unitario = il.price_unit
                        self.subtotal = il.subtotal
                        self.discount = il.discount
                        self.move_line_tax_ids = il.invoice_line_tax_ids

    @api.onchange('name')
    def _sale_prices(self):
        for rec in self:
            if rec.precio_unitario <= 0:
                rec._set_price_from()
            if rec.precio_unitario <= 0:
                rec.precio_unitario = rec.product_id.lst_price
                rec.move_line_tax_ids = rec.product_id.taxes_id # @TODO mejorar asignación
            if not rec.name:
                rec.name = rec.product_id.name

    @api.onchange('name', 'product_id', 'move_line_tax_ids', 'product_uom_qty', 'precio_unitario', 'quantity_done')
    @api.depends('name', 'product_id', 'move_line_tax_ids', 'product_uom_qty', 'precio_unitario', 'quantity_done')
    def _compute_amount(self):
        for rec in self:
            qty = rec.quantity_done
            if qty <= 0:
                qty = rec.product_uom_qty
            subtotal = qty * rec.precio_unitario
            rec.subtotal = (subtotal * (1 - (rec.discount or 0.0) / 100.0))

    name = fields.Char(
            string="Nombre",
        )
    subtotal = fields.Monetary(
            compute='_compute_amount',
            string='Subtotal',
            store=True,
        )
    precio_unitario = fields.Monetary(
            string='Precio Unitario',
        )
    price_untaxed = fields.Monetary(
            string='Price Untaxed',
        )
    move_line_tax_ids = fields.Many2many(
            'account.tax',
            'move_line_tax_ids',
            'move_line_id',
            'tax_id',
            string='Taxes',
            domain=[('type_tax_use', '!=', 'none'), '|', ('active', '=', False), ('active', '=', True)],
        )
    discount = fields.Monetary(
            digits=dp.get_precision('Discount'),
            string='Discount (%)',
        )
    currency_id = fields.Many2one(
            'res.currency',
            string='Currency',
            required=True,
            states={'draft': [('readonly', False)]},
            default=lambda self: self.env.user.company_id.currency_id.id,
            track_visibility='always',
        )
