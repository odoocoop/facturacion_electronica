# -*- coding: utf-8 -*-
from openerp import fields, models, api, _
from openerp.exceptions import UserError
import collections
import logging
_logger = logging.getLogger(__name__)

class DiscBase(models.Model):
    _inherit = 'account.invoice.tax'

    def _compute_base_amount(self):
        super(DiscBase,self)._compute_base_amount()
        for tax in self:
            base = 0.0
            if tax.invoice_id.global_discount_type in ['percent']:
                tax.base = round(tax.base * (1 - ((tax.invoice_id.global_discount / 100.0) or 0.0)))
            else:
                tax.base -= tax.invoice_id.global_discount


class GlobalDiscount(models.Model):
    _inherit = "account.invoice"

    #global_discount = fields.Many2one('discounts', string="Seleccione Descuento Global")
    global_discount = fields.Float(string="Descuento Global", default=0.00, readonly=True, states={'draft': [('readonly', False)]})
    global_discount_type = fields.Selection([('amount','Monto'),('percent','Porcentaje')], string="Tipo de descuento", readonly=True, states={'draft': [('readonly', False)]})
    global_discount_detail = fields.Char(string="Razón del descuento", readonly=True, states={'draft': [('readonly', False)]})
    amount_untaxed_global_discount = fields.Float(string="Global Discount Amount", store=True, default=0.00, compute='_compute_amount')

    @api.multi
    def get_taxes_values(self):
        tax_grouped = super(GlobalDiscount,self).get_taxes_values()
        if self.global_discount > 0:
            discount = self.global_discount
            if self.global_discount_type in ['amount']:
                discount = 0
                afecto = 0
                for line in self.invoice_line_ids:
                    for tl in line.invoice_line_tax_ids:
                        if tl.amount > 0:
                            afecto += line.price_subtotal
                if afecto > 0:
                    discount = ((self.global_discount * 100) / afecto )
            taxes = tax_grouped
            tax_grouped = {}
            for id, t in taxes.iteritems():
                tax = self.env['account.tax'].browse(t['tax_id'])
                if tax.amount > 0 and discount > 0:
                    base = round(round(t['base']) * (1 - ((discount / 100.0) or 0.0)))
                    t['amount'] = tax._compute_amount(base, base, 1)
                tax_grouped[id] = t
        return tax_grouped

    @api.onchange('global_discount','global_discount_type')
    def _compute_amount(self):
        for inv in self:
            if inv.global_discount > 0  and inv.global_discount_type:
                taxes_grouped = inv.get_taxes_values()
                tax_lines = inv.tax_line_ids.browse([])
                for tax in taxes_grouped.values():
                    tax_lines += tax_lines.new(tax)
                inv.tax_line_ids = tax_lines
                discount = inv.global_discount
                amount_untaxed = round(sum(line.price_subtotal for line in inv.invoice_line_ids))
                afecto = 0
                for line in inv.invoice_line_ids:
                    for t in line.invoice_line_tax_ids:
                        if t.amount > 0:
                            afecto += line.price_subtotal
                if inv.global_discount_type in ['amount'] and afecto > 0:
                    discount = ((inv.global_discount * 100) / afecto )
                inv.amount_untaxed = amount_untaxed
                if afecto > 0 and discount > 0:
                    inv.amount_untaxed_global_discount = (afecto * (discount / 100))
                amount_untaxed -= round(inv.amount_untaxed_global_discount)
                amount_tax = sum(line.amount for line in inv.tax_line_ids)
                amount_retencion = sum(line.amount_retencion for line in inv.tax_line_ids)
                inv.amount_tax = amount_tax
                inv.amount_retencion = amount_retencion
                amount_total = amount_untaxed + amount_tax - amount_retencion
                amount_total_company_signed = amount_total
                inv.amount_total = amount_total
                amount_untaxed_signed = amount_untaxed
                if inv.currency_id and inv.currency_id != inv.company_id.currency_id:
                    amount_total_company_signed = inv.currency_id.compute(amount_total, inv.company_id.currency_id)
                    amount_untaxed_signed = inv.currency_id.compute(amount_untaxed, inv.company_id.currency_id)
                sign = inv.type in ['in_refund', 'out_refund'] and -1 or 1
                inv.amount_total_company_signed = amount_total_company_signed * sign
                inv.amount_total_signed = amount_total * sign
                inv.amount_untaxed_signed = amount_untaxed_signed * sign
            else:
                super(GlobalDiscount,inv)._compute_amount()

    def finalize_invoice_move_lines(self, move_lines):
        if not self.global_discount > 0:
            return super(GlobalDiscount,self).finalize_invoice_move_lines( move_lines)
        new_lines = []
        discount = self.global_discount
        if self.global_discount_type == 'amount':
            afecto = 0
            for line in self.invoice_line_ids:
                for t in line.invoice_line_tax_ids:
                    if t.amount > 0:
                        afecto += line.price_subtotal
            discount = ((self.global_discount * 100) / afecto )
        hold = False
        total = 0
        for line in move_lines:
            if line[2]['tax_ids'] and not line[2]['tax_line_id']:#iva ya viene con descuento
                if line[2]['tax_ids']:
                    for t in line[2]['tax_ids']:
                        imp = self.env['account.tax'].browse(t[1])
                        if imp.amount > 0  and line[2]['debit'] > 0:
                            line[2]['debit'] -= int(round((line[2]['debit'] * (discount / 100))))
                            total += line[2]['debit']
                        elif imp.amount > 0:
                            line[2]['credit'] -= int(round((line[2]['credit'] * (discount /100))))
                            total += line[2]['credit']
                        elif line[2]['debit'] > 0:
                            total += line[2]['debit']
                        else:
                            total += line[2]['credit']
            elif line[2]['tax_line_id']:
                if line[2]['debit'] > 0:
                    total += line[2]['debit']
                else:
                    total += line[2]['credit']
            if line[2]['name'] != '/':
                new_lines.extend([line])
            else:
                hold = line
        if hold and hold[2]['debit'] > 0:
            hold[2]['debit'] = total
        else:
            hold[2]['credit'] = total
        new_lines.extend([hold])

        new_lines = super(GlobalDiscount,self).finalize_invoice_move_lines( new_lines)
        return new_lines

    def _dte(self, n_atencion=None):
        dte = super(GlobalDiscount,self)._dte(n_atencion)
        if not self.global_discount > 0:
            return dte
        result = collections.OrderedDict()
        lin_dr = 1
        dr_line = {}
        dr_line = collections.OrderedDict()
        dr_line['NroLinDR'] = lin_dr
        dr_line['TpoMov'] = 'D'
        if self.global_discount_detail:
            dr_line['GlosaDR'] = self.global_discount_detail
        disc_type = "%"
        if self.global_discount_type == "amount":
            disc_type = "$"
        dr_line['TpoValor'] = disc_type
        dr_line['ValorDR'] = round(self.global_discount,2)
        if self.sii_document_class_id.sii_code in [34] and (self.referencias and self.referencias[0].sii_referencia_TpoDocRef.sii_code == '34'):#solamente si es exento
            dr_line['IndExeDR'] = 1
        dr_lines= [{'DscRcgGlobal':dr_line}]
        for key, value in dte.iteritems():
            if key == 'reflines':
                result['drlines'] = dr_lines
            result[key] = value
        return result

    def _dte_to_xml(self, dte, tpo_dte="Documento"):
        xml = super(GlobalDiscount, self)._dte_to_xml(dte, tpo_dte)
        xml = xml.replace('<drlines>','').replace('</drlines>','')
        return xml
