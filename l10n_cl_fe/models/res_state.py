from odoo import api, fields, models


class ResState(models.Model):
    _inherit = "res.country.state"

    @api.multi
    def name_get(self):
        res = []
        for state in self:
            data = []
            data.insert(0, state.name)
            if state.region_id:
                data.insert(0, state.region_id.name)
            data = " / ".join(data)
            res.append((state.id, (state.code and "[" + state.code + "] " or "") + data))
        return res

    region_id = fields.Many2one("res.country.state.region", string="Region", index=True,)
