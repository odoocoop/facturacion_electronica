# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _


class SIIXMLEnvio(models.Model):
    _inherit = 'sii.xml.envio'

    order_ids = fields.One2many(
            'pos.order',
            'sii_xml_request',
            string="Ordenes POS",
            readonly=True,
            states={'draft': [('readonly', False)]},
        )

    def set_childs(self, state):
        result = super(SIIXMLEnvio, self).set_childs(state)
        for r in self.order_ids:
            r.sii_result = state
        return result
