import logging
import re
from datetime import datetime, time

import dateutil.relativedelta as relativedelta
import pytz
from lxml import html

from odoo import api, models

from .currency import float_round_custom

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

    @api.multi
    def compute_all(
        self, price_unit, currency=None, quantity=1.0, product=None, partner=None, discount=None, uom_id=None
    ):
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

        # In some cases, it is necessary to force/prevent the rounding of the tax and the total
        # amounts. For example, in SO/PO line, we don't want to round the price unit at the
        # precision of the currency.
        # The context key 'round' allows to force the standard behavior.
        round_tax = False if company_id.tax_calculation_rounding_method == "round_globally" else True
        round_total = True
        if "round" in self.env.context:
            round_tax = bool(self.env.context["round"])
            round_total = bool(self.env.context["round"])

        if not round_tax:
            prec += 5

        base_values = self.env.context.get("base_values")
        if not base_values:
            if prec == 5:
                base = float_round_custom(price_unit * quantity, precision_digits=2)
                base = float_round_custom(base, precision_digits=0)
                disc = base * ((discount or 0.0) / 100.0)
                tot_discount = float_round_custom(disc, precision_digits=0)
                base -= tot_discount
            else:
                price_unit = price_unit * (1 - (discount or 0.0) / 100.0)
                base = round(price_unit * quantity, prec)
            total_excluded = base
            total_included = base
        else:
            total_excluded, total_included, base = base_values

        composed_tax = {}
        if len(self) > 1:
            composed_tax = self._fix_composed_included_tax(base, quantity, uom_id)
        # Sorting key is mandatory in this case. When no key is provided, sorted() will perform a
        # search. However, the search method is overridden in account.tax in order to add a domain
        # depending on the context. This domain might filter out some taxes from self, e.g. in the
        # case of group taxes.
        for tax in self.sorted(key=lambda r: r.sequence):
            # Allow forcing price_include/include_base_amount through the context for the reconciliation widget.
            # See task 24014.
            price_include = self._context.get("force_price_include", tax.price_include)

            if tax.amount_type == "group":
                children = tax.children_tax_ids.with_context(base_values=(total_excluded, total_included, base))
                ret = children.compute_all(price_unit, currency, quantity, product, partner, discount, uom_id)
                total_excluded = ret["total_excluded"]
                base = ret["base"] if tax.include_base_amount else base
                total_included = ret["total_included"]
                tax_amount_retencion = ret["retencion"]
                tax_amount = total_included - total_excluded + tax_amount_retencion
                taxes += ret["taxes"]
                continue
            _base = composed_tax.get(tax.id, base)
            tax_amount = tax._compute_amount(_base, price_unit, quantity, product, partner, uom_id)
            if not round_tax:
                tax_amount = round(tax_amount, prec)
            else:
                tax_amount = currency.round(tax_amount)
            tax_amount_retencion = 0
            if tax.sii_type in ["R"]:
                tax_amount_retencion = tax._compute_amount_ret(_base, price_unit, quantity, product, partner, uom_id)
                if not round_tax:
                    tax_amount_retencion = round(tax_amount_retencion, prec)
            if price_include:
                total_excluded -= tax_amount - tax_amount_retencion
                total_included -= tax_amount_retencion
                _base -= tax_amount - tax_amount_retencion
            else:
                total_included += currency.round(tax_amount - tax_amount_retencion)

            # Keep base amount used for the current tax
            tax_base = _base

            if tax.include_base_amount:
                base += tax_amount

            taxes.append(
                {
                    "id": tax.id,
                    "name": tax.with_context(**{"lang": partner.lang} if partner else {}).name,
                    "amount": tax_amount,
                    "retencion": tax_amount_retencion,
                    "base": tax_base,
                    "sequence": tax.sequence,
                    "account_id": tax.account_id.id,
                    "refund_account_id": tax.refund_account_id.id,
                    "analytic": tax.analytic,
                    "price_include": tax.price_include,
                    "tax_exigibility": tax.tax_exigibility,
                }
            )

        return {
            "taxes": sorted(taxes, key=lambda k: k["sequence"]),
            "total_excluded": currency.round(total_excluded) if round_total else total_excluded,
            "total_included": currency.round(total_included) if round_total else total_included,
            "base": base,
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

    @api.multi
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
