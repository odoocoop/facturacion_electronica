from odoo import api, fields, models


class ResState(models.Model):
    _inherit = "res.country.state"

    child_ids = fields.One2many("res.country.state.provincia", "state_id", string="Child Provs",)
