import logging
import re
from datetime import datetime, time

import dateutil.relativedelta as relativedelta
import pytz
from lxml import html

from odoo import api, models

from .currency import float_round_custom
from odoo.tools.float_utils import float_round as round

_logger = logging.getLogger(__name__)
try:
    import urllib3

    urllib3.disable_warnings()
    pool = urllib3.PoolManager()
except ImportError:
    _logger.warning("no se ha cargado urllib3")
try:
    import fitz
except Exception as e:
    _logger.warning("error en PyMUPDF: %s" % str(e))

meses = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


class SiiTax(models.Model):
    _inherit = "account.tax"

    def compute_factor(self, uom_id):
        amount_tax = self.amount or 0.0
        if self.uom_id and self.uom_id != uom_id:
            if self.env.context.get("date"):
                mepco = self._target_mepco(self.env.context.get("date"))
                amount_tax = mepco.amount
            factor = self.uom_id._compute_quantity(1, uom_id)
            amount_tax = amount_tax / factor
        return amount_tax

    def _fix_composed_included_tax(self, base, quantity, uom_id):
        composed_tax = {}
        price_included = False
        percent = 0.0
        rec = 0.0
        for tax in self.sorted(key=lambda r: r.sequence):
            if tax.price_include:
                price_included = True
            else:
                continue
            if tax.amount_type == "percent":
                percent += tax.amount
            else:
                amount_tax = tax.compute_factor(uom_id)
                rec += quantity * amount_tax
        if price_included:
            _base = base - rec
            common_base = _base / (1 + percent / 100.0)
            for tax in self.sorted(key=lambda r: r.sequence):
                if tax.amount_type == "percent":
                    composed_tax[tax.id] = common_base * (1 + tax.amount / 100)
        return composed_tax


    def compute_all(self, price_unit, currency=None, quantity=1.0, product=None, partner=None, is_refund=False, handle_price_include=True, discount=None, uom_id=None):
        """ Returns all information required to apply taxes (in self + their children in case of a tax group).
            We consider the sequence of the parent for group of taxes.
                Eg. considering letters as taxes and alphabetic order as sequence :
                [G, B([A, D, F]), E, C] will be computed as [A, D, F, C, E, G]

            'handle_price_include' is used when we need to ignore all tax included in price. If False, it means the
            amount passed to this method will be considered as the base of all computations.

        RETURN: {
            'total_excluded': 0.0,    # Total without taxes
            'total_included': 0.0,    # Total with taxes
            'total_void'    : 0.0,    # Total with those taxes, that don't have an account set
            'taxes': [{               # One dict for each tax in self and their children
                'id': int,
                'name': str,
                'amount': float,
                'sequence': int,
                'account_id': int,
                'refund_account_id': int,
                'analytic': boolean,
            }],
        } """
        if not self:
            company = self.env.company
        else:
            company = self[0].company_id

        # 1) Flatten the taxes.
        taxes, groups_map = self.flatten_taxes_hierarchy(create_map=True)

        # 2) Avoid mixing taxes having price_include=False && include_base_amount=True
        # with taxes having price_include=True. This use case is not supported as the
        # computation of the total_excluded would be impossible.
        base_excluded_flag = False  # price_include=False && include_base_amount=True
        included_flag = False  # price_include=True
        for tax in taxes:
            if tax.price_include:
                included_flag = True
            elif tax.include_base_amount:
                base_excluded_flag = True
            if base_excluded_flag and included_flag:
                raise UserError(_('Unable to mix any taxes being price included with taxes affecting the base amount but not included in price.'))

        # 3) Deal with the rounding methods
        if not currency:
            currency = company.currency_id
        # By default, for each tax, tax amount will first be computed
        # and rounded at the 'Account' decimal precision for each
        # PO/SO/invoice line and then these rounded amounts will be
        # summed, leading to the total amount for that tax. But, if the
        # company has tax_calculation_rounding_method = round_globally,
        # we still follow the same method, but we use a much larger
        # precision when we round the tax amount for each line (we use
        # the 'Account' decimal precision + 5), and that way it's like
        # rounding after the sum of the tax amounts of each line
        prec = currency.rounding

        # In some cases, it is necessary to force/prevent the rounding of the tax and the total
        # amounts. For example, in SO/PO line, we don't want to round the price unit at the
        # precision of the currency.
        # The context key 'round' allows to force the standard behavior.
        round_tax = False if company.tax_calculation_rounding_method == 'round_globally' else True
        if 'round' in self.env.context:
            round_tax = bool(self.env.context['round'])

        if not round_tax:
            prec *= 1e-5

        # 4) Iterate the taxes in the reversed sequence order to retrieve the initial base of the computation.
        #     tax  |  base  |  amount  |
        # /\ ----------------------------
        # || tax_1 |  XXXX  |          | <- we are looking for that, it's the total_excluded
        # || tax_2 |   ..   |          |
        # || tax_3 |   ..   |          |
        # ||  ...  |   ..   |    ..    |
        #    ----------------------------
        def recompute_base(base_amount, fixed_amount, percent_amount, division_amount):
            # Recompute the new base amount based on included fixed/percent amounts and the current base amount.
            # Example:
            #  tax  |  amount  |   type   |  price_include  |
            # -----------------------------------------------
            # tax_1 |   10%    | percent  |  t
            # tax_2 |   15     |   fix    |  t
            # tax_3 |   20%    | percent  |  t
            # tax_4 |   10%    | division |  t
            # -----------------------------------------------

            # if base_amount = 145, the new base is computed as:
            # (145 - 15) / (1.0 + 30%) * 90% = 130 / 1.3 * 90% = 90
            return (base_amount - fixed_amount) / (1.0 + percent_amount / 100.0) * (100 - division_amount) / 100

        # The first/last base must absolutely be rounded to work in round globally.
        # Indeed, the sum of all taxes ('taxes' key in the result dictionary) must be strictly equals to
        # 'price_included' - 'price_excluded' whatever the rounding method.
        #
        # Example using the global rounding without any decimals:
        # Suppose two invoice lines: 27000 and 10920, both having a 19% price included tax.
        #
        #                   Line 1                      Line 2
        # -----------------------------------------------------------------------
        # total_included:   27000                       10920
        # tax:              27000 / 1.19 = 4310.924     10920 / 1.19 = 1743.529
        # total_excluded:   22689.076                   9176.471
        #
        # If the rounding of the total_excluded isn't made at the end, it could lead to some rounding issues
        # when summing the tax amounts, e.g. on invoices.
        # In that case:
        #  - amount_untaxed will be 22689 + 9176 = 31865
        #  - amount_tax will be 4310.924 + 1743.529 = 6054.453 ~ 6054
        #  - amount_total will be 31865 + 6054 = 37919 != 37920 = 27000 + 10920
        #
        # By performing a rounding at the end to compute the price_excluded amount, the amount_tax will be strictly
        # equals to 'price_included' - 'price_excluded' after rounding and then:
        #   Line 1: sum(taxes) = 27000 - 22689 = 4311
        #   Line 2: sum(taxes) = 10920 - 2176 = 8744
        #   amount_tax = 4311 + 8744 = 13055
        #   amount_total = 31865 + 13055 = 37920
        base = currency.round(price_unit * quantity)

        # For the computation of move lines, we could have a negative base value.
        # In this case, compute all with positive values and negate them at the end.
        sign = 1
        if currency.is_zero(base):
            sign = self._context.get('force_sign', 1)
        elif base < 0:
            sign = -1
        if base < 0:
            base = -base

        # Store the totals to reach when using price_include taxes (only the last price included in row)
        total_included_checkpoints = {}
        i = len(taxes) - 1
        store_included_tax_total = True
        # Keep track of the accumulated included fixed/percent amount.
        incl_fixed_amount = incl_percent_amount = incl_division_amount = 0
        # Store the tax amounts we compute while searching for the total_excluded
        cached_tax_amounts = {}
        if handle_price_include:
            for tax in reversed(taxes):
                tax_repartition_lines = (
                    is_refund
                    and tax.refund_repartition_line_ids
                    or tax.invoice_repartition_line_ids
                ).filtered(lambda x: x.repartition_type == "tax")
                sum_repartition_factor = sum(tax_repartition_lines.mapped("factor"))

                if tax.include_base_amount:
                    base = recompute_base(base, incl_fixed_amount, incl_percent_amount, incl_division_amount)
                    incl_fixed_amount = incl_percent_amount = incl_division_amount = 0
                    store_included_tax_total = True
                if tax.price_include or self._context.get('force_price_include'):
                    if tax.amount_type == 'percent':
                        incl_percent_amount += tax.amount * sum_repartition_factor
                    elif tax.amount_type == 'division':
                        incl_division_amount += tax.amount * sum_repartition_factor
                    elif tax.amount_type == 'fixed':
                        incl_fixed_amount += quantity * tax.amount * sum_repartition_factor
                    else:
                        # tax.amount_type == other (python)
                        tax_amount = tax._compute_amount(base, sign * price_unit, quantity, product, partner) * sum_repartition_factor
                        incl_fixed_amount += tax_amount
                        # Avoid unecessary re-computation
                        cached_tax_amounts[i] = tax_amount
                    # In case of a zero tax, do not store the base amount since the tax amount will
                    # be zero anyway. Group and Python taxes have an amount of zero, so do not take
                    # them into account.
                    if store_included_tax_total and (
                        tax.amount or tax.amount_type not in ("percent", "division", "fixed")
                    ):
                        total_included_checkpoints[i] = base
                        store_included_tax_total = False
                i -= 1

        total_excluded = currency.round(recompute_base(base, incl_fixed_amount, incl_percent_amount, incl_division_amount))

        # 5) Iterate the taxes in the sequence order to compute missing tax amounts.
        # Start the computation of accumulated amounts at the total_excluded value.
        base = total_included = total_void = total_excluded

        taxes_vals = []
        i = 0
        cumulated_tax_included_amount = 0
        for tax in taxes:
            tax_repartition_lines = (is_refund and tax.refund_repartition_line_ids or tax.invoice_repartition_line_ids).filtered(lambda x: x.repartition_type == 'tax')
            sum_repartition_factor = sum(tax_repartition_lines.mapped('factor'))

            price_include = self._context.get('force_price_include', tax.price_include)

            #compute the tax_amount
            if price_include and total_included_checkpoints.get(i):
                # We know the total to reach for that tax, so we make a substraction to avoid any rounding issues
                tax_amount = total_included_checkpoints[i] - (base + cumulated_tax_included_amount)
                cumulated_tax_included_amount = 0
            else:
                tax_amount = tax.with_context(force_price_include=False)._compute_amount(
                    base, sign * price_unit, quantity, product, partner)

            # Round the tax_amount multiplied by the computed repartition lines factor.
            tax_amount = round(tax_amount, precision_rounding=prec)
            factorized_tax_amount = round(tax_amount * sum_repartition_factor, precision_rounding=prec)

            if price_include and not total_included_checkpoints.get(i):
                cumulated_tax_included_amount += factorized_tax_amount

            # If the tax affects the base of subsequent taxes, its tax move lines must
            # receive the base tags and tag_ids of these taxes, so that the tax report computes
            # the right total
            subsequent_taxes = self.env['account.tax']
            subsequent_tags = self.env['account.account.tag']
            tax_amount_retencion = 0
            if tax.sii_type in ["R", "RH"]:
                tax_amount_retencion = tax._compute_amount_ret(base, price_unit, quantity, product, partner, uom_id)
                tax_amount_retencion = round(tax_amount_retencion, precision_rounding=prec)
            if tax.include_base_amount:
                subsequent_taxes = taxes[i+1:]
                subsequent_tags = subsequent_taxes.get_tax_tags(is_refund, 'base')

            # Compute the tax line amounts by multiplying each factor with the tax amount.
            # Then, spread the tax rounding to ensure the consistency of each line independently with the factorized
            # amount. E.g:
            #
            # Suppose a tax having 4 x 50% repartition line applied on a tax amount of 0.03 with 2 decimal places.
            # The factorized_tax_amount will be 0.06 (200% x 0.03). However, each line taken independently will compute
            # 50% * 0.03 = 0.01 with rounding. It means there is 0.06 - 0.04 = 0.02 as total_rounding_error to dispatch
            # in lines as 2 x 0.01.
            repartition_line_amounts = [round(tax_amount * line.factor, precision_rounding=prec) for line in tax_repartition_lines]
            total_rounding_error = round(factorized_tax_amount - sum(repartition_line_amounts), precision_rounding=prec)
            nber_rounding_steps = int(abs(total_rounding_error / currency.rounding))
            rounding_error = round(nber_rounding_steps and total_rounding_error / nber_rounding_steps or 0.0, precision_rounding=prec)

            for repartition_line, line_amount in zip(tax_repartition_lines, repartition_line_amounts):

                if nber_rounding_steps:
                    line_amount += rounding_error
                    nber_rounding_steps -= 1

                taxes_vals.append({
                    'id': tax.id,
                    'name': partner and tax.with_context(lang=partner.lang).name or tax.name,
                    'amount': sign * line_amount,
                    'retencion': sign * tax_amount_retencion,
                    'base': round(sign * base, precision_rounding=prec),
                    'sequence': tax.sequence,
                    'account_id': tax.cash_basis_transition_account_id.id if tax.tax_exigibility == 'on_payment' else repartition_line.account_id.id,
                    'analytic': tax.analytic,
                    'price_include': price_include,
                    'tax_exigibility': tax.tax_exigibility,
                    'tax_repartition_line_id': repartition_line.id,
                    'group': groups_map.get(tax),
                    'tag_ids': (repartition_line.tag_ids + subsequent_tags).ids,
                    'tax_ids': subsequent_taxes.ids,
                })

                if not repartition_line.account_id:
                    total_void += line_amount

            # Affect subsequent taxes
            if tax.include_base_amount:
                base += factorized_tax_amount

            total_included += factorized_tax_amount - tax_amount_retencion
            i += 1

        return {
            'base_tags': taxes.mapped(is_refund and 'refund_repartition_line_ids' or 'invoice_repartition_line_ids').filtered(lambda x: x.repartition_type == 'base').mapped('tag_ids').ids,
            'taxes': taxes_vals,
            'total_excluded': sign * total_excluded,
            'total_included': sign * currency.round(total_included),
            'total_void': sign * currency.round(total_void),
        }

    def _compute_amount_ret(self, base_amount, price_unit, quantity=1.0, product=None, partner=None, uom_id=None):
        if self.amount_type == "percent" and self.price_include:
            neto = base_amount / (1 + self.retencion / 100)
            tax = base_amount - neto
            return tax
        if (self.amount_type == "percent" and not self.price_include) or (
            self.amount_type == "division" and self.price_include
        ):
            return base_amount * self.retencion / 100

    def _list_from_diario(self, day, year, month):
        date = datetime.strptime("{}-{}-{}".format(day, month, year), "%d-%m-%Y").astimezone(pytz.UTC)
        t = date - relativedelta.relativedelta(days=1)
        t_date = "date={}-{}-{}".format(t.strftime("%d"), t.strftime("%m"), t.strftime("%Y"))
        url = "https://www.diariooficial.interior.gob.cl/edicionelectronica/"
        resp = pool.request("GET", "{}select_edition.php?{}".format(url, t_date))
        target = 'a href="index.php[?]%s&edition=([0-9]*)&v=1"' % t_date
        url2 = re.findall(target, resp.data.decode("utf-8"))
        resp2 = pool.request("GET", "{}index.php?{}&edition={}".format(url, t_date, url2[0]))
        # target = 'Determina el componente variable para el cálculo del impuesto específico establecido en la ley N° 18.502 [a-zA-Z \r\n</>="_0-9]* href="([a-zA-Z 0-9/.:]*)"'
        target = '18.502[\\W]* [a-zA-Z \r\n<\\/>="_0-9]* href="([a-zA-Z 0-9\\/.:]*)"'
        url3 = re.findall(target, resp2.data.decode("utf-8"))
        if not url3:
            return {}
        return {date: url3[0].replace("http", "https")}

    def _get_from_diario(self, url):
        resp = pool.request("GET", url)
        doc = fitz.open(stream=resp.data, filetype="pdf")
        target = "Gasolina Automotriz de[\n ]93 octanos[\n ]\\(*en UTM\\/m[\\w]\\)"
        if self.mepco == "gasolina_97":
            target = "Gasolina Automotriz de[\n ]97 octanos[\n ]\\(en UTM\\/m[\\w]\\)"
        elif self.mepco == "diesel":
            target = "Petr[\\w]leo Di[\\w]sel[\n ]\\(en UTM\\/m[\\w]\\)"
        elif self.mepco == "gas_licuado":
            target = "Gas Licuado del Petróleo de Consumo[\n ]Vehicular[\n ]\\(en UTM\\/m[\\w]\\)"
        elif self.mepco == "gas_natural":
            target = "Gas Natural Comprimido de Consumo Vehicular"
        val = re.findall("%s\n[0-9.,-]*\n[0-9.,-]*\n([0-9.,-]*)" % target, doc.loadPage(1).getText())
        return val[0].replace(".", "").replace(",", ".")

    def _connect_sii(self, year, month):
        month = meses[int(month)].lower()
        url = "http://www.sii.cl/valores_y_fechas/mepco/mepco%s.htm" % year
        resp = pool.request("GET", url)
        sii = html.fromstring(resp.data)
        return sii.findall('.//div[@id="pp_%s"]/div/table' % (month))

    def _list_from_sii(self, year, month):
        tables = self._connect_sii(year, month)
        rangos = {}
        i = 0
        for r in tables:
            sub = r.find("tr/th")
            res = re.search(r"\d{1,2}\-\d{1,2}\-\d{4}", sub.text.lower())
            rangos[datetime.strptime(res[0], "%d-%m-%Y").astimezone(pytz.UTC)] = i
            i += 1
        return rangos

    def _get_from_sii(self, year, month, target):
        tables = self._connect_sii(year, month)
        line = 1
        if self.mepco == "gasolina_97":
            line = 3
        elif self.mepco == "diesel":
            line = 5
        val = tables[target[1]].findall("tr")[line].findall("td")[4].text.replace(".", "").replace(",", ".")
        return val

    def prepare_mepco(self, date, currency_id=False):
        tz = pytz.timezone("America/Santiago")
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
        if not rangos or target[0] > date:
            return self.prepare_mepco((date - relativedelta.relativedelta(days=1)), currency_id)
        val = self._get_from_diario(target[1])
        utm = self.env["res.currency"].sudo().search([("name", "=", "UTM")])
        amount = utm._convert(float(val), currency_id, self.company_id, date)
        return {
            "amount": amount,
            "date": target[0].strftime("%Y-%m-%d"),
            "name": target[0].strftime("%Y-%m-%d"),
            "type": self.mepco,
            "sequence": len(rangos),
            "company_id": self.company_id.id,
            "currency_id": currency_id.id,
            "factor": float(val),
        }


    def actualizar_mepco(self):
        self.verify_mepco(date_target=False, currency_id=False, force=True)

    def _target_mepco(self, date_target=False, currency_id=False, force=False):
        if not currency_id:
            currency_id = self.env["res.currency"].sudo().search([("name", "=", self.env.get("currency", "CLP"))])
        tz = pytz.timezone("America/Santiago")
        if date_target:
            user_zone = pytz.timezone(self._context.get("tz") or "UTC")
            date = date_target
            if not hasattr(date, "tzinfo"):
                date = datetime.combine(date, time.min)
            if tz != user_zone:
                date = date.astimezone(tz)
        else:
            date = datetime.now(tz)
        query = [
            ("date", "<=", date.strftime("%Y-%m-%d")),
            ("company_id", "=", self.company_id.id),
            ("type", "=", self.mepco),
        ]
        mepco = self.env["account.tax.mepco"].sudo().search(query, limit=1)
        if mepco:
            diff = date.date() - mepco.date
            if diff.days > 6:
                mepco = False
        if not mepco:
            mepco_data = self.prepare_mepco(date, currency_id)
            query = [
                ("date", "=", mepco_data["date"]),
                ("company_id", "=", mepco_data["company_id"]),
                ("type", "=", mepco_data["type"]),
            ]
            mepco = self.env["account.tax.mepco"].sudo().search(query, limit=1)
            if not mepco:
                mepco = self.env["account.tax.mepco"].sudo().create(mepco_data)
        elif force:
            mepco_data = self.prepare_mepco(date, currency_id)
            mepco.sudo().write(mepco_data)
        return mepco

    def verify_mepco(self, date_target=False, currency_id=False, force=False):
        mepco = self._target_mepco(date_target, currency_id, force)
        self.amount = mepco.amount
