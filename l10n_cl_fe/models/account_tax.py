# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.tools.translate import _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
from datetime import datetime
import dateutil.relativedelta as relativedelta
import pytz
import logging
import decimal
from lxml import html
import re
_logger = logging.getLogger(__name__)
try:
    import urllib3
    urllib3.disable_warnings()
    pool = urllib3.PoolManager()
except:
    _logger.warning("no se ha cargado urllib3")
try:
    import fitz
except Exception as e:
    _logger.warning("error en PyMUPDF: %s" % str(e))

meses = {1: 'Enero',2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}


class SiiTax(models.Model):
    _inherit = 'account.tax'

    @api.multi
    def compute_all(self, price_unit, currency=None, quantity=1.0, product=None, partner=None, discount=None, uom_id=None):
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
                ret = tax.children_tax_ids.compute_all(price_unit, currency, quantity, product, partner, discount, uom_id)
                total_excluded = ret['total_excluded']
                base = ret['base']
                total_included = ret['total_included']
                tax_amount_retencion = ret['retencion']
                tax_amount = total_included - total_excluded + tax_amount_retencion
                taxes += ret['taxes']
                continue

            tax_amount = tax._compute_amount(base, price_unit, quantity, product, partner, uom_id)
            if company_id.tax_calculation_rounding_method == 'round_globally' or not bool(self.env.context.get("round", True)):
                tax_amount = round(tax_amount, prec)
            else:
                tax_amount = currency.round(tax_amount)
            tax_amount_retencion = 0
            if tax.sii_type in ['R']:
                tax_amount_retencion = tax._compute_amount_ret(base, price_unit, quantity, product, partner, uom_id)
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

    def _compute_amount_ret(self, base_amount, price_unit, quantity=1.0, product=None, partner=None, uom_id=None):
        if self.amount_type == 'percent' and self.price_include:
            neto = base_amount / (1 + self.retencion / 100)
            tax = base_amount - neto
            return tax
        if (self.amount_type == 'percent' and not self.price_include) or (self.amount_type == 'division' and self.price_include):
            return base_amount * self.retencion / 100

    def _list_from_diario(self, day, year, month):
        date = datetime.strptime("%s-%s-%s" %(day, month, year), "%d-%m-%Y").astimezone(pytz.UTC)
        t = (date - relativedelta.relativedelta(days=1))
        t_date = "date=%s-%s-%s" %(
            t.strftime('%d'),
            t.strftime('%m'),
            t.strftime('%Y'),
        )
        url = "https://www.diariooficial.interior.gob.cl/edicionelectronica/"
        resp = pool.request('GET', "%sselect_edition.php?%s" % (url, t_date))
        target = 'a href="index.php[?]%s&edition=([0-9]*)&v=1"' % t_date
        url2 = re.findall(target, resp.data.decode('utf-8'))
        resp2 = pool.request('GET', "%sindex.php?%s&edition=%s" %(url, t_date, url2[0]))
        target = 'Determina el componente variable para el cálculo del impuesto específico establecido en la ley N° 18.502 [a-zA-Z \r\n</>="_0-9]* href="([a-zA-Z 0-9/.:]*)"'
        url3 = re.findall(target, resp2.data.decode('utf-8'))
        return {date: url3[0].replace('http', 'https')}

    def _get_from_diario(self, url):
        resp = pool.request('GET', url)
        doc = fitz.open(stream=resp.data, filetype="pdf")
        target = 'Gasolina Automotriz de 93 octanos\n\(en UTM\/m[\w]\)'
        if self.mepco == 'gasolina_97':
            target = 'Gasolina Automotriz de 97 octanos\n\(en UTM\/m[\w]\)'
        elif self.mepco == 'diesel':
            target = 'Petróleo Diésel \(en UTM\/m[\w]\)'
        elif self.mepco == 'gas_licuado':
            target = 'Gas Licuado del Petróleo de Consumo\nVehicular \(en UTM\/m[\w]\)'
        elif self.mepco == 'gas_natural':
            target = 'Gas Natural Comprimido de Consumo Vehicular'
        val = re.findall('%s\n[0-9.,]*\n[0-9.,]*\n([0-9.,]*)' % target, doc.loadPage(1).getText())
        return val[0].replace('.', '').replace(',', '.')

    def _connect_sii(self, year, month):
        month = meses[int(month)].lower()
        url = "http://www.sii.cl/valores_y_fechas/mepco/mepco%s.htm" % year
        resp = pool.request('GET', url)
        sii = html.fromstring(resp.data)
        return sii.findall('.//div[@id="pp_%s"]/div/table' % (month))

    def _list_from_sii(self, year, month):
        tables = self._connect_sii(year, month)
        rangos = {}
        i = 0
        for r in tables:
            sub = r.find('tr/th')
            res = re.search('\d{1,2}\-\d{1,2}\-\d{4}', sub.text.lower())
            rangos[datetime.strptime(res[0], "%d-%m-%Y").astimezone(pytz.UTC)] = i
            i += 1
        return rangos

    def _get_from_sii(self, year, month, target):
        tables = self._connect_sii(year, month)
        line = 1
        if self.mepco == 'gasolina_97':
            line = 3
        elif self.mepco == 'diesel':
            line = 5
        val = tables[target[1]].findall('tr')[line].findall('td')[4].text.replace('.', '').replace(',', '.')
        return val

    def prepare_mepco(self, date, currency_id=False):
        tz = pytz.timezone('America/Santiago')
        year = date.strftime("%Y")
        month = date.strftime("%m")
        day = date.strftime("%d")
        rangos = self._list_from_diario(day, year, month)
        ant = datetime.now(tz)
        target = (ant, 0)
        for k, v in rangos.items():
            if k <= date < ant:
                target = (k, v)
                break
            ant = k
        if target[0] > date:
            return self.prepare_mepco((date - relativedelta.relativedelta(days=1)), currency_id)
        val = self._get_from_diario(target[1])
        utm = self.env['res.currency'].sudo().search([('name', '=', 'UTM')])
        amount = utm._convert(float(val), currency_id, self.company_id, date)
        return {
            'amount': amount,
            'date': target[0].strftime("%Y-%m-%d"),
            'name': target[0].strftime("%Y-%m-%d"),
            'type': self.mepco,
            'sequence': len(rangos),
            'company_id': self.company_id.id,
            'currency_id': currency_id.id,
            'factor': float(val),
        }

    @api.multi
    def actualizar_mepco(self):
        self.verify_mepco(date_target=False, currency_id=False, force=True)

    def _target_mepco(self, date_target=False, currency_id=False, force=False):
        if not currency_id:
            currency_id = self.env['res.currency'].sudo().search([
                ('name', '=', self.env.get('currency', 'CLP'))
            ])
        tz = pytz.timezone('America/Santiago')
        if date_target:
            fields_model = self.env['ir.fields.converter']
            ''' @TODO crearlo como utilidad python'''
            user_zone = fields_model._input_tz()
            date = datetime.strptime(date_target, "%Y-%m-%d")
            if tz != user_zone:
                if not date.tzinfo:
                    date = user_zone.localize(date_target)
                date = date.astimezone(tz)
        else:
            date = datetime.now(tz)
        query = [
            ('date', '<=', date.strftime("%Y-%m-%d")),
            ('company_id', '=', self.company_id.id),
            ('type', '=', self.mepco),
        ]
        mepco = self.env['account.tax.mepco'].sudo().search(query, limit=1)
        if mepco:
            diff = (date.date() - datetime.strptime(mepco.date, "%Y-%m-%d"))
            if diff.days > 6:
                mepco = False
        if not mepco:
            mepco_data = self.prepare_mepco(date, currency_id)
            query = [
                ('date', '=', mepco_data['date']),
                ('company_id', '=', mepco_data['company_id']),
                ('type', '=', mepco_data['type']),
            ]
            mepco = self.env['account.tax.mepco'].sudo().search(query, limit=1)
            if not mepco:
                mepco = self.env['account.tax.mepco'].sudo().create(mepco_data)
        elif force:
            mepco_data = self.prepare_mepco(date, currency_id)
            mepco.sudo().write(mepco_data)
        return mepco

    def verify_mepco(self, date_target=False, currency_id=False, force=False):
        mepco = self._target_mepco(date_target, currency_id, force)
        self.amount = mepco.amount
