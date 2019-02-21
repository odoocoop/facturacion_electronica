# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    def get_digital_signature(self, company_id):
        signature = self.env['sii.firma'].search(
            [
                ('user_ids', 'child_of', [self.id]),
                ('company_ids', 'child_of', [company_id.id]),
                ('state', '=', 'valid')
            ],
            limit=1,
            order="priority ASC",
        )
        signature.check_signature()
        if signature and signature.active:
            return signature
        return self.env['sii.firma']

