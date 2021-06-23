# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class AduanasUnidadesMedida(models.Model):
    _inherit = 'uom.uom'

    code = fields.Char(
            string="Código Aduanas",
        )
    exp_name = fields.Char(
        string="Nombre en Exportación"
    )


    @api.multi
    def name_get(self):
        res = []
        for r in self:
            name = r.name
            if self.env.context.get("exportacion", False) and r.exp_name:
                name = r.exp_name
            res.append((r.id, name))
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('exp_name', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()
