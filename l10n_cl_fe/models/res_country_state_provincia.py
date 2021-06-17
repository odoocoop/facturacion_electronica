from odoo import fields, models


class ResStateRegion(models.Model):
    _name = "res.country.state.provincia"
    _description = "Subdivisión Provincias"

    name = fields.Char(string="Region Name", help="The state code.\n", required=True,)
    code = fields.Char(string="Region Code", help="The povincia code.\n", required=True,)
    child_ids = fields.One2many("res.city", "provincia_id", string="Child Regions",)
    state_id = fields.Many2one("res.country.state", strin="Región")
    country_id = fields.Many2one('res.country', string='Country', required=True)
