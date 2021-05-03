# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
import decimal



class AccountInvoiceLine(models.Model):
    _inherit = "account.move.line"

    sequence = fields.Integer(string="Sequence", default=-1,)
    discount_amount = fields.Float(string="Monto Descuento", default=0.00,)
    is_gd_line = fields.Boolean(
        string="Es Línea descuento Global"
    )
    is_gr_line = fields.Boolean(
        string="Es Línea Recargo Global"
    )

    @api.onchange("discount", "price_unit", "quantity")
    def set_discount_amount(self):
        total = self.currency_id.round(self.quantity * self.price_unit)
        decimal.getcontext().rounding = decimal.ROUND_HALF_UP
        self.discount_amount = int(decimal.Decimal(total * ((self.discount or 0.0) / 100.0)).to_integral_value())


    @api.depends(
        "price_unit",
        "discount",
        "tax_ids",
        "quantity",
        "product_id",
        "move_id.partner_id",
        "move_id.currency_id",
        "move_id.company_id",
        "move_id.date",
        "move_id.date",
    )
    def _compute_price(self):
        super(AccountInvoiceLine, self)._compute_price()
        for line in self:
            line.set_discount_amount()
            continue
            currency = line.move_id and line.move_id.currency_id or None
            taxes = False
            total = 0
            included = False
            #@dar soporte a mepco con nueva estructura
            #for t in line.tax_ids:
            #    if t.product_uom_id and t.product_uom_id.category_id != line.product_uom_id.category_id:
            #        raise UserError("Con este tipo de impuesto, solamente deben ir unidades de medida de la categoría %s" %t.product_uom_id.category_id.name)
            #    if t.mepco:
            #        t.verify_mepco(line.move_id.date, line.move_id.currency_id)
            #    if taxes and (t.price_include != included):
            #        raise UserError('No se puede hacer timbrado mixto, todos los impuestos en este pedido deben ser uno de estos dos:  1.- precio incluído, 2.-  precio sin incluir')
            #    included = t.price_include
            #    taxes = True
            taxes = line.tax_ids.compute_all(
                line.price_unit,
                currency,
                line.quantity,
                product=line.product_id,
                partner=line.move_id.partner_id,
                discount=line.discount, uom_id=line.product_uom_id)
            if taxes:
                line.price_subtotal = price_subtotal_signed = taxes['total_excluded']
            else:
                total = line.currency_id.round((line.quantity * line.price_unit))
                decimal.getcontext().rounding = decimal.ROUND_HALF_UP
                total = line.currency_id.round((line.quantity * line.price_unit)) - line.discount_amount
                line.price_subtotal = price_subtotal_signed = int(decimal.Decimal(total).to_integral_value())
            if self.move_id.currency_id and self.move_id.currency_id != self.move_id.company_id.currency_id:
                currency = self.move_id.currency_id
                date = self.move_id._get_currency_rate_date()
                price_subtotal_signed = currency._convert(
                    price_subtotal_signed,
                    self.move_id.company_id.currency_id,
                    self.company_id or self.env.user.company_id,
                    date or fields.Date.today(),
                )
            sign = line.move_id.type in ["in_refund", "out_refund"] and -1 or 1
            line.price_subtotal_signed = price_subtotal_signed * sign
            line.price_total = taxes["total_included"] if (taxes and taxes["total_included"] > total) else total


    def get_tax_detail(self):
        boleta = self.move_id.document_class_id.es_boleta()
        nc_boleta = self.move_id._nc_boleta()
        amount_total = 0
        details = dict(
            impuestos=[],
            taxInclude=False,
            MntExe=0,
            price_unit=self.price_unit,
        )
        currency_base = self.move_id.currency_base()
        for t in self.tax_ids:
            if not boleta and not nc_boleta:
                if t.sii_code in [26, 27, 28, 35, 271]:#@Agregar todos los adicionales
                    details['cod_imp_adic'] = t.sii_code
            details['taxInclude'] = t.price_include
            if t.amount == 0 or t.sii_code in [0]:#@TODO mejor manera de identificar exento de afecto
                details['IndExe'] = 1#line.product_id.ind_exe or 1
                details['MntExe'] += currency_base.round(self.price_subtotal)
            else:
                if boleta or nc_boleta:
                    amount_total += self.price_total
                amount = t.amount
                if t.sii_code in [28, 35]:
                    amount = t.compute_factor(self.product_uom_id)
                details['impuestos'].append({
                            "CodImp": t.sii_code,
                            'price_include': details['taxInclude'],
                            'TasaImp': amount,
                        }
                )
        if amount_total > 0:
            details['impuestos'].append({
                    'name': t.description,
                    "CodImp": t.sii_code,
                    'price_include': boleta or nc_boleta or details['taxInclude'],
                    'TasaImp': amount,
                }
            )
            if not details['taxInclude'] and (boleta or nc_boleta):
                taxes_res = self._get_price_total_and_subtotal_model(
                    self.price_unit,
                    1,
                    self.discount,
                    self.move_id.currency_id,
                    self.product_id,
                    self.move_id.partner_id,
                    self.tax_ids,
                    self.move_id.move_type)
                details['price_unit'] = taxes_res.get('price_total', 0.0)
        if boleta or nc_boleta:
             details['taxInclude'] = True
        return details
