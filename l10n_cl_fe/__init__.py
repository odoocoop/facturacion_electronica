from odoo import SUPERUSER_ID, api

from . import controllers, models, wizard


def _set_default_configs(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ICPSudo = env["ir.config_parameter"].sudo()
    ICPSudo.set_param("account.auto_send_dte", 1)
    ICPSudo.set_param("account.auto_send_email", True)
    ICPSudo.set_param("account.auto_send_persistencia", 24)
    ICPSudo.set_param("account.limit_dte_lines", False)
    ICPSudo.set_param("partner.url_remote_partners", "https://sre.cl/api/company_info")
    ICPSudo.set_param("partner.token_remote_partners", "token_publico")
    ICPSudo.set_param("partner.sync_remote_partners", True)
    ICPSudo.set_param("dte.url_apicaf", "https://apicaf.cl/api/caf")
    ICPSudo.set_param("dte.token_apicaf", "token_publico")
