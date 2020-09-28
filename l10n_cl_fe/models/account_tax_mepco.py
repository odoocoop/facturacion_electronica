import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class Mepco(models.Model):
    _name = "account.tax.mepco"
    _description = "Indicador SII combustibles"

    name = fields.Char(string="Nombre de envío", required=True,)
    date = fields.Date(string="Día Inicio Validez")
    amount = fields.Float(string="Monto", digits=(12, 6), default=0.0,)
    type = fields.Selection(
        [("diesel", "Diesel"), ("gasolina_93", "Gasolina 93"), ("gasolina_97", "Gasolina 97"),],
        string="Indicador Mepco",
    )
    sequence = fields.Integer(string="Secuencia")
    company_id = fields.Many2one("res.company")
    currency_id = fields.Many2one("res.currency")
    factor = fields.Float(string="Factor cálculo", digits=(12, 6),)

    _order = "date desc, sequence desc"
    _sql_constraint = [
        ("date_unique", "unique(date)", "Error! Date Already Exist!"),
    ]
