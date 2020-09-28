import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning("Post Migrating l10n_cl_fe from version %s to 12.0.0.24.0" % installed_version)

    env = api.Environment(cr, SUPERUSER_ID, {})
    ICPSudo = env["ir.config_parameter"].sudo()
    ICPSudo.set_param("account.auto_send_dte", 1)
