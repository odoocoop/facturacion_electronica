# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Pre Migrating l10n_cl_fe from version %s to 11.0.0.5.0' % installed_version)

    cr.execute(
        "ALTER TABLE res_partner ADD COLUMN email_temp VARCHAR")
    cr.execute(
        "UPDATE res_partner set email_temp=dte_email where dte_email!=''")
