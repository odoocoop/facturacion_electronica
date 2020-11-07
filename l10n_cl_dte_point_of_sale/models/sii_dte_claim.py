# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _


class DTEClaim(models.Model):
    _inherit = 'sii.dte.claim'

    order_id = fields.Many2one("pos.order", string="Documento", ondelete="cascade",)
