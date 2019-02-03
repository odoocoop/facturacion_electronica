# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_fe from version %s to 11.0.0.5.0' % installed_version)

    cr.execute(
        "INSERT INTO res_partner (parent_id, name, email, type, send_dte, principal, invoice_warn, picking_warn, sale_warn, purchase_warn, active) SELECT id, email_temp, email_temp, 'dte', True, True, 'no-message', 'no-message', 'no-message', 'no-message', True FROM res_partner rp WHERE rp.email_temp!=''")
    cr.execute("ALTER TABLE res_partner DROP COLUMN email_temp")
