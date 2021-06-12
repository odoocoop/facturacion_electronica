# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'


    @api.model
    def create_from_ui(self, partner):
        ad = ''
        if 'activity_description_text' in partner:
            ad = partner['activity_description_text']
            del partner['activity_description_text']
            ad_id = self.env['sii.activity.description'].search([
                ('name', '=', ad)
            ])
            if not ad_id:
                ad_id = self.env['sii.activity.description'].create(
                    {'name': ad}
                )
            partner['activity_description'] = ad_id.id
        return super(ResPartner, self).create_from_ui(partner)
