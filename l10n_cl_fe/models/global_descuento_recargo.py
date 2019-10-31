# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class GlobalDescuentoRecargo(models.Model):
    _name = "account.invoice.gdr"
    _description = 'Línea de descuento / Recargo Global DTE'

    type = fields.Selection(
            [
                ('D', 'Descuento'),
                ('R', 'Recargo'),
            ],
           string="Seleccione Descuento/Recargo Global",
           default='D',
           required=True,
       )
    valor = fields.Float(
            string="Descuento/Recargo Global",
            default=0.00,
            required=True,
        )
    gdr_type = fields.Selection(
            [
                    ('amount','Monto'),
                    ('percent','Porcentaje'),
            ],
            string="Tipo de descuento",
            default="percent",
            required=True,
        )
    gdr_detail = fields.Char(
            string="Razón del descuento",
        )
    amount_untaxed_global_dr = fields.Float(
            string="Descuento/Recargo Global",
            default=0.00,
            compute='_untaxed_gdr',
        )
    aplicacion = fields.Selection(
            [
                ('flete', 'Flete'),
                ('seguro', 'Seguro'),
            ],
            string="Aplicación del Desc/Rec",
        )
    invoice_id = fields.Many2one(
            'account.invoice',
            string="Factura",
        )

    def _get_afecto(self):
        afecto = 0.00
        for line in self[0].invoice_id.invoice_line_ids:
            for tl in line.invoice_line_tax_ids:
                if tl.amount > 0:
                    afecto += line.price_subtotal
        return afecto

    @api.depends('gdr_type', 'valor', 'type')
    def _untaxed_gdr(self):
        groups = {}
        for gdr in self:
            if gdr.invoice_id.id not in groups:
                groups[gdr.invoice_id.id] = dict(
                    afecto=gdr._get_afecto(),
                    des=0,
                    rec=0,
                )
            groups[gdr.invoice_id.id]['dr'] = gdr.valor
            if gdr.gdr_type in ['percent']:
                if groups[gdr.invoice_id.id]['afecto'] == 0.00:
                    continue
                #exento = 0 #@TODO Descuento Global para exentos
                if groups[gdr.invoice_id.id]['afecto'] > 0:
                    groups[gdr.invoice_id.id]['dr'] = gdr.invoice_id.currency_id.round((groups[gdr.invoice_id.id]['afecto'] *  (groups[gdr.invoice_id.id]['dr'] / 100.0) ))
            if gdr.type == 'D':
                groups[gdr.invoice_id.id]['des'] += groups[gdr.invoice_id.id]['dr']
            else:
                groups[gdr.invoice_id.id]['rec'] += groups[gdr.invoice_id.id]['dr']
            gdr.amount_untaxed_global_dr = groups[gdr.invoice_id.id]['dr']
        for key, dr in groups.items():
            if dr['des'] >= (dr['afecto'] + dr['rec']):
                raise UserError('El descuento no puede ser mayor o igual a la suma de los recargos + neto (f: %s)' %(key))

    def get_agrupados(self):
        result = {'D': 0.00, 'R': 0.00}
        for gdr in self:
            result[gdr.type] += gdr.amount_untaxed_global_dr
        return result

    def get_monto_aplicar(self):
        grouped = self.get_agrupados()
        monto = 0
        for key, value in grouped.items():
            valor = value
            if key == 'D':
                valor = float(value) * (-1)
            monto += valor
        return monto

    @api.model
    def default_get(self, fields_list):
        ctx = self.env.context.copy()
        # FIX: la accion de Notas de credito pasa por contexto default_type: 'out_refund'
        # pero al existir en esta clase de descuentos un campo llamado type
        # el ORM lo interpreta como un valor para ese campo,
        # pero el valor no esta dentro de las opciones del selection, por ello sale error
        # asi que si no esta en los valores soportados, eliminarlo del contexto
        if 'default_type' in ctx and ctx.get('default_type') not in ('D', 'R'):
            ctx.pop('default_type')
        values = super(GlobalDescuentoRecargo, self.with_context(ctx)).default_get(fields_list)
        return values
