from odoo import SUPERUSER_ID, api

from . import controllers, models, wizard, report


def _set_default_configs(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ICPSudo = env["ir.config_parameter"].sudo()
    ICPSudo.set_param("account.auto_send_dte", 1)
    ICPSudo.set_param("account.auto_send_email", True)
    ICPSudo.set_param("account.auto_send_persistencia", 24)
