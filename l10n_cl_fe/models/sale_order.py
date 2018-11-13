from odoo import api, fields, models
from odoo.tools.translate import _


class SO(models.Model):
    _inherit = 'sale.order'
