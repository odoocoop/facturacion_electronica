# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
import decimal



class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    sequence = fields.Integer(string="Sequence", default=-1,)
    discount_amount = fields.Float(string="Monto Descuento", default=0.00,)

    @api.onchange("discount", "price_unit", "quantity")
    def set_discount_amount(self):
        total = self.currency_id.round(self.quantity * self.price_unit)
        decimal.getcontext().rounding = decimal.ROUND_HALF_UP
        self.discount_amount = int(decimal.Decimal(total * ((self.discount or 0.0) / 100.0)).to_integral_value())

    @api.one
    @api.depends(
        "price_unit",
        "discount",
        "invoice_line_tax_ids",
        "quantity",
        "product_id",
        "invoice_id.partner_id",
        "invoice_id.currency_id",
        "invoice_id.company_id",
        "invoice_id.date_invoice",
        "invoice_id.date",
    )
    def _compute_price(self):
        for line in self:
            line.set_discount_amount()
            currency = line.invoice_id and line.invoice_id.currency_id or None
            taxes = False
            total = 0
            included = False
            for t in line.invoice_line_tax_ids:
                if t.uom_id and t.uom_id.category_id != line.uom_id.category_id:
                    raise UserError("Con este tipo de impuesto, solamente deben ir unidades de medida de la categoría %s" %t.uom_id.category_id.name)
                if t.mepco:
                    t.verify_mepco(line.invoice_id.date_invoice, line.invoice_id.currency_id)
                if taxes and (t.price_include != included):
                    raise UserError('No se puede hacer timbrado mixto, todos los impuestos en este pedido deben ser uno de estos dos:  1.- precio incluído, 2.-  precio sin incluir')
                included = t.price_include
                taxes = True
            taxes = line.invoice_line_tax_ids.compute_all(
                line.price_unit,
                currency,
                line.quantity,
                product=line.product_id,
                partner=line.invoice_id.partner_id,
                discount=line.discount, uom_id=line.uom_id)
            if taxes:
                line.price_subtotal = price_subtotal_signed = taxes['total_excluded']
            else:
                total = line.currency_id.round((line.quantity * line.price_unit))
                decimal.getcontext().rounding = decimal.ROUND_HALF_UP
                total = line.currency_id.round((line.quantity * line.price_unit)) - line.discount_amount
                line.price_subtotal = price_subtotal_signed = int(decimal.Decimal(total).to_integral_value())
            if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
                currency = self.invoice_id.currency_id
                date = self.invoice_id._get_currency_rate_date()
                price_subtotal_signed = currency._convert(
                    price_subtotal_signed,
                    self.invoice_id.company_id.currency_id,
                    self.company_id or self.env.user.company_id,
                    date or fields.Date.today(),
                )
            sign = line.invoice_id.type in ["in_refund", "out_refund"] and -1 or 1
            line.price_subtotal_signed = price_subtotal_signed * sign
            line.price_total = taxes["total_included"] if (taxes and taxes["total_included"] > total) else total

    @api.multi
    def get_tax_detail(self):
        boleta = self.invoice_id.document_class_id.es_boleta()
        nc_boleta = self.invoice_id._nc_boleta()
        amount_total = 0
        details = dict(
            impuestos=[],
            taxInclude=False,
            MntExe=0
        )
        currency_base = self.invoice_id.currency_base()
        for t in self.invoice_line_tax_ids:
            if not boleta and not nc_boleta:
                if t.sii_code in [26, 27, 28, 35, 271]:#@Agregar todos los adicionales
                    details['cod_imp_adic'] = t.sii_code
            details['taxInclude'] = t.price_include or ( (boleta or nc_boleta) and not t.sii_detailed )
            if t.amount == 0 or t.sii_code in [0]:#@TODO mejor manera de identificar exento de afecto
                details['IndExe'] = 1#line.product_id.ind_exe or 1
                details['MntExe'] += currency_base.round(self.price_subtotal)
            else:
                if boleta or nc_boleta:
                    amount_total += self.price_total
                amount = t.amount
                if t.sii_code in [28, 35]:
                    amount = t.compute_factor(self.uom_id)
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
                    'price_include': details['taxInclude'],
                    'TasaImp': amount,
                }
            )
        return details
