# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_fe from version %s to 11.0.0.8.0' % installed_version)
    env = api.Environment(cr, SUPERUSER_ID, {})
    for row in env['res.company'].search([]):
        alias = env['mail.alias'].create(
            {
                'alias_name': row.partner_id.dte_email,
                'alias_model_id': env['ir.model'].search([('model', '=', 'mail.message.dte')]).id,
                'alias_parent_model_id': env['ir.model'].search([('model', '=', 'res.company')]).id,
                'alias_user_id': 3,

            })
        row.write({
            'dte_email_id': alias.id
        })
