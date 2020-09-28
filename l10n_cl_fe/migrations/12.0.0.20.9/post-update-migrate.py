import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning("Post Migrating l10n_cl_fe from version %s to 12.0.0.20.9" % installed_version)

    env = api.Environment(cr, SUPERUSER_ID, {})
    for r in env["res.partner"].sudo().search([("dte_email", "!=", False),]):
        for p in (
            env["res.partner"]
            .sudo()
            .search([("email", "!=", r.dte_email), ("send_dte", "=", True), ("commercial_partner_id", "=", r.id),])
        ):
            p.principal = False
            p.send_dte = False
        if r.dte_email_id:
            if not r.dte_email_id.principal:
                r.dte_email_id.principal = True
            if not r.dte_email_id.send_dte:
                r.dte_email_id.send_dte = True
