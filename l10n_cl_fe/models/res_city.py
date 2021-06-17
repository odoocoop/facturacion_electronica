from odoo import fields, models


class ResCity(models.Model):
    _inherit = "res.city"

    code = fields.Char(string="City Code", help="The city code.\n", required=True,)
    provincia_id = fields.Many2one("res.country.state.provincia")
