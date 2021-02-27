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
    @api.depends('currency_id', 'move_lines', 'move_reason')
    def _compute_amount(self):
        for rec in self:
            amount_untaxed = 0
            amount_tax = 0
            if rec.move_reason not in ['5']:
                taxes = rec.get_taxes_values()
                for k, v in taxes.items():
                    amount_tax += v['amount']
                rec.amount_tax = rec.currency_id.round(amount_tax)
                for line in self.move_lines:
                    amount_untaxed += line.price_untaxed
                rec.amount_untaxed = amount_untaxed
            rec.amount_total = amount_untaxed + amount_tax

    def _prepare_tax_line_vals(self, line, tax):
        """ Prepare values to create an account.move.tax line

        The line parameter is an account.move.line, and the
        tax parameter is the output of account.tax.compute_all().
        """
        t = self.env['account.tax'].browse(tax['id'])
        vals = {
            'picking_id': self.id,
            'description': t.with_context(**{'lang': self.partner_id.lang} if self.partner_id else {}).description,
            'tax_id': tax['id'],
            'amount': tax['amount'] if tax['amount'] > 0 else (tax['amount'] * -1),
            'base': tax['base'],
            'manual': False,
            'sequence': tax['sequence'],
            'amount_retencion': tax['retencion']
        }
        return vals

    def get_grouping_key(self, vals):
        return str(vals['tax_id'])

    def _get_grouped_taxes(self, line, taxes, tax_grouped={}):
        for tax in taxes:
            val = self._prepare_tax_line_vals(line, tax)
            key = self.get_grouping_key(val)
            if key not in tax_grouped:
                tax_grouped[key] = val
                tax_grouped[key]['base'] = self.currency_id.round(val['base'])
            else:
                tax_grouped[key]['amount'] += val['amount']
                tax_grouped[key]['amount_retencion'] += val['amount_retencion']
                tax_grouped[key]['base'] += self.currency_id.round(val['base'])
        return tax_grouped

    
    def get_taxes_values(self):
        tax_grouped = {}
        totales = {}
        included = False
        for line in self.move_lines:
            qty = line.quantity_done
            if qty <= 0:
                qty = line.product_uom_qty
            if (line.move_line_tax_ids and line.move_line_tax_ids[0].price_include) :# se asume todos losproductos vienen con precio incluido o no ( no hay mixes)
                if included or not tax_grouped:#genero error en caso de contenido mixto, en caso primer impusto no incluido segundo impuesto incluido
                    for t in line.move_line_tax_ids:
                        if t not in totales:
                            totales[t] = 0
                        amount_line = (self.currency_id.round(line.precio_unitario *qty))
                        totales[t] += (amount_line * (1 - (line.discount / 100)))
                included = True
            else:
                included = False
            if (totales and not included) or (included and not totales):
                raise UserError('No se puede hacer timbrado mixto, todos los impuestos en este pedido deben ser uno de estos dos:  1.- precio incluído, 2.-  precio sin incluir')
            taxes = line.move_line_tax_ids.with_context(
                date=self.scheduled_date,
                currency=self.currency_id.code).compute_all(line.precio_unitario, self.currency_id, qty, line.product_id, self.partner_id, discount=line.discount, uom_id=line.product_uom)['taxes']
            tax_grouped = self._get_grouped_taxes(line, taxes, tax_grouped)
        #if totales:
        #    tax_grouped = {}
        #    for line in self.invoice_line_ids:
        #        for t in line.invoice_line_tax_ids:
        #            taxes = t.compute_all(totales[t], self.currency_id, 1)['taxes']
        #            tax_grouped = self._get_grouped_taxes(line, taxes, tax_grouped)
        #_logger.warning(tax_grouped)
        '''
        @TODO GDR para guías
        if not self.global_descuentos_recargos:
            return tax_grouped
        gdr, gdr_exe = self.porcentaje_dr()
        '''
        for t, group in tax_grouped.items():
            group['base'] = self.currency_id.round(group['base'])
            group['amount'] = self.currency_id.round(group['amount'])
        return tax_grouped

    def set_use_document(self):
        return (self.picking_type_id and self.picking_type_id.code != 'incoming')

    amount_untaxed = fields.Monetary(
            compute='_compute_amount',
            digits=dp.get_precision('Account'),
            string='Untaxed Amount',
        )
    amount_tax = fields.Monetary(
            compute='_compute_amount',
            string='Taxes',
        )
    amount_total = fields.Monetary(
            compute='_compute_amount',
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
    respuesta_ids = fields.Many2many(
            'sii.respuesta.cliente',
            string="Recepción del Cliente",
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
                    il = self.env['account.move'].search(
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
            taxes = rec.move_line_tax_ids.compute_all(rec.precio_unitario, rec.currency_id, qty, product=rec.product_id, partner=rec.picking_id.partner_id, discount=rec.discount, uom_id=rec.product_uom)
            rec.price_untaxed = taxes['total_excluded']
            rec.subtotal = taxes['total_included']

    name = fields.Char(
            string="Nombre",
        )
    subtotal = fields.Monetary(
            compute='_compute_amount',
            string='Subtotal',
            store=True,
        )
    precio_unitario = fields.Float(
            string='Precio Unitario',
            digits=dp.get_precision('Product Price'),
        )
    price_untaxed = fields.Monetary(
            string='Price Untaxed',
            compute='_compute_amount',
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
