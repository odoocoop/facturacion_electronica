# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_fe from version %s to 11.0.0.9.4' % installed_version)
    env = api.Environment(cr, SUPERUSER_ID, {})
    ICPSudo = env['ir.config_parameter'].sudo()
    ICPSudo.set_param('account.auto_send_dte', 12)
    ICPSudo.set_param('account.auto_send_email', True)
    ICPSudo.set_param('account.limit_dte_lines', False)
    ICPSudo.set_param('partner.url_remote_partners', 'https://sre.cl/api/company_info')
    ICPSudo.set_param('partner.token_remote_partners', 'token_publico')
    ICPSudo.set_param('partner.sync_remote_partners', True)
