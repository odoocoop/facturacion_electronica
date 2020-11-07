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

    def set_childs(self, state):
        result = super(SIIXMLEnvio, self).set_childs(state)
        for r in self.picking_ids:
            r.sii_result = state
        return result
