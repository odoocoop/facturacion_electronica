# -*- coding: utf-8 -*-
from . import models
from . import controllers
from . import wizard
from odoo import api, SUPERUSER_ID


def _set_default_configs(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ICPSudo = env['ir.config_parameter'].sudo()
    ICPSudo.set_param('account.auto_send_dte', 12)
    ICPSudo.set_param('account.auto_send_email', True)
    ICPSudo.set_param('account.auto_send_persistencia', 24)
    ICPSudo.set_param('account.limit_dte_lines', False)
    ICPSudo.set_param('partner.url_remote_partners', 'https://sre.cl/api/company_info')
    ICPSudo.set_param('partner.token_remote_partners', 'token_publico')
    ICPSudo.set_param('partner.sync_remote_partners', True)
    ICPSudo.set_param('dte.url_apicaf', 'https://apicaf.cl/api/caf')
    ICPSudo.set_param('dte.token_apicaf', 'token_publico')
