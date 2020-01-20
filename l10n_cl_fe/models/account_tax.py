# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.tools.translate import _
from datetime import datetime
import pytz
import logging
import locale
import decimal
_logger = logging.getLogger(__name__)
try:
    import urllib3
    urllib3.disable_warnings()
    pool = urllib3.PoolManager()
except:
    _logger.warning("no se ha cargado urllib3")


class SiiTax(models.Model):
    _inherit = 'account.tax'

    @api.multi
    def compute_all(self, price_unit, currency=None, quantity=1.0, product=None, partner=None, discount=None):
        """ Returns all information required to apply taxes (in self + their children in case of a tax goup).
            We consider the sequence of the parent for group of taxes.
                Eg. considering letters as taxes and alphabetic order as sequence :
                [G, B([A, D, F]), E, C] will be computed as [A, D, F, C, E, G]
        RETURN: {
            'total_excluded': 0.0,    # Total without taxes
            'total_included': 0.0,    # Total with taxes
            'taxes': [{               # One dict for each tax in self and their children
                'id': int,
                'name': str,
                'amount': float,
                'sequence': int,
                'account_id': int,
                'refund_account_id': int,
                'analytic': boolean,
            }]
        } """
        if len(self) == 0:
            company_id = self.env.user.company_id
        else:
            company_id = self[0].company_id
        if not currency:
            currency = company_id.currency_id
        taxes = []
        # By default, for each tax, tax amount will first be computed
        # and rounded at the 'Account' decimal precision for each
        # PO/SO/invoice line and then these rounded amounts will be
        # summed, leading to the total amount for that tax. But, if the
        # company has tax_calculation_rounding_method = round_globally,
        # we still follow the same method, but we use a much larger
        # precision when we round the tax amount for each line (we use
        # the 'Account' decimal precision + 5), and that way it's like
        # rounding after the sum of the tax amounts of each line
        prec = currency.decimal_places
        base = round(price_unit * quantity, prec+2)
        base = round(base, prec)
        disc = (base * ((discount or 0.0) /100.0))
        decimal.getcontext().rounding = decimal.ROUND_HALF_UP
        tot_discount = int(decimal.Decimal(disc).to_integral_value())
        base -= tot_discount
        total_excluded = base
        total_included = base

        if company_id.tax_calculation_rounding_method == 'round_globally' or not bool(self.env.context.get("round", True)):
            prec += 5

        # Sorting key is mandatory in this case. When no key is provided, sorted() will perform a
        # search. However, the search method is overridden in account.tax in order to add a domain
        # depending on the context. This domain might filter out some taxes from self, e.g. in the
        # case of group taxes.
        for tax in self.sorted(key=lambda r: r.sequence):
            if tax.amount_type == 'group':
                ret = tax.children_tax_ids.compute_all(price_unit, currency, quantity, product, partner)
                total_excluded = ret['total_excluded']
                base = ret['base']
                total_included = ret['total_included']
                tax_amount_retencion = ret['retencion']
                tax_amount = total_included - total_excluded + tax_amount_retencion
                taxes += ret['taxes']
                continue

            tax_amount = tax._compute_amount(base, price_unit, quantity, product, partner)
            if company_id.tax_calculation_rounding_method == 'round_globally' or not bool(self.env.context.get("round", True)):
                tax_amount = round(tax_amount, prec)
            else:
                tax_amount = currency.round(tax_amount)
            tax_amount_retencion = 0
            if tax.sii_type in ['R']:
                tax_amount_retencion = tax._compute_amount_ret(base, price_unit, quantity, product, partner)
                if company_id.tax_calculation_rounding_method == 'round_globally' or not bool(self.env.context.get("round", True)):
                    tax_amount_retencion = round(tax_amount_retencion, prec)
                if tax.price_include:
                    total_excluded -= (tax_amount - tax_amount_retencion )
                    total_included -= (tax_amount_retencion)
                    base -= (tax_amount - tax_amount_retencion )
                else:
                    total_included += (tax_amount - tax_amount_retencion)
            else:
                if tax.price_include:
                    total_excluded -= tax_amount
                    base -= tax_amount
                else:
                    total_included += tax_amount
            # Keep base amount used for the current tax
            tax_base = base

            if tax.include_base_amount:
                base += tax_amount

            taxes.append({
                'id': tax.id,
                'name': tax.with_context(**{'lang': partner.lang} if partner else {}).name,
                'amount': tax_amount,
                'retencion': tax_amount_retencion,
                'base': tax_base,
                'sequence': tax.sequence,
                'account_id': tax.account_id.id,
                'refund_account_id': tax.refund_account_id.id,
                'analytic': tax.analytic,
            })
        return {
            'taxes': sorted(taxes, key=lambda k: k['sequence']),
            'total_excluded': currency.round(total_excluded) if bool(self.env.context.get("round", True)) else total_excluded,
            'total_included': currency.round(total_included) if bool(self.env.context.get("round", True)) else total_included,
            'base': base,
            }

    def _compute_amount_ret(self, base_amount, price_unit, quantity=1.0, product=None, partner=None):
        if self.amount_type == 'percent' and self.price_include:
            neto = base_amount / (1 + self.retencion / 100)
            tax = base_amount - neto
            return tax
        if (self.amount_type == 'percent' and not self.price_include) or (self.amount_type == 'division' and self.price_include):
            return base_amount * self.retencion / 100


    def prepare_mepco(self, date):
        locale.setlocale(locale.LC_TIME, 'es_CL')
        year = date.strftime("%Y")
        month = date.strftime("%B").lower()
        url = "http://www.sii.cl/valores_y_fechas/mepco/mepco%s.htm" % year
        resp = pool.request('GET', url)
        sii = html.fromstring(resp.data)
        line = 1
        if self.mepco == 'gasolina_97':
            line = 3
        elif self.mepco == 'diesel':
            line = 5
        rangos = {}
        i = 0
        for r in sii.xpath('//div[@id="pp_%s"]/table/tr/th[0]' % (month, line)):
            rangos[datetime.strptime(r.text, "Vigencia desde: %A %d-%m-%Y")] = i
            i += 1
        tz = pytz.timezone('America/Santiago')
        ant = datetime.now(tz)
        target = (ant, 0)
        for k, v in rangos.items():
            if k >= date < ant:
                target = (k, v)
                break
            ant = k
        val = sii.xpath('//div[@id="pp_%s"]/table[%s]/tr[%s]/tr[4]' % (month, target[1], line)).text
        return {
            'amount': int(val),
            'date': target[0].strftime("%Y-%m-%d"),
            'name': target[0].strftime("%Y-%m-%d"),
            'type': self.mepco,
            'sequence': len(rangos),
            'company_id': self.company_id.id,
        }

    def verify_mepco(self, date_target=False):
        tz = pytz.timezone('America/Santiago')
        if date_target:
            fields_model = self.env['ir.fields.converter']
            ''' @TODO crearlo como utilidad python'''
            tz = pytz.timezone('America/Santiago')
            user_zone = fields_model._input_tz()
            date  = datetime.strptime(date_target, "%Y-%m-%d")
            if tz != user_zone:
                if not date.tzinfo:
                    date = user_zone.localize(date)
                date = date.astimezone(tz)
        else:
            date = datetime.now(tz)
        mepco = self.env['account.tax.mepco'].sudo().search([
            ('date', '>=', date.strftime("%Y-%m-%d")),
            ('company_id', '=', self.company_id.id),
            ('type', '=', self.mepco),
        ],
        limit=1)
        if not mepco:
            mepco_data = self.prepare_mepco(date)
            mepco = self.env['account.tax.mepco'].sudo().create(mepco)
        self.amount = mepco.amount
