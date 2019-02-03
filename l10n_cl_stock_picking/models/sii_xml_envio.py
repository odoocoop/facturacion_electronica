# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _

class SIIXMLEnvio(models.Model):
    _inherit = 'sii.xml.envio'

    picking_ids = fields.One2many(
        'stock.picking',
        'sii_xml_request',
        string="Guías",
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
