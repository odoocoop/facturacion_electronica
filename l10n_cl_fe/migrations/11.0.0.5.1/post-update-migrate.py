# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_fe from version %s to 11.0.0.5.1' % installed_version)

    cr.execute(
        "UPDATE account_invoice set sii_document_number=dcn_temp where dcn_temp>0")
    cr.execute(
        "UPDATE account_move set sii_document_number=dcn_temp where dcn_temp>0")
    cr.execute("ALTER TABLE account_invoice DROP COLUMN dcn_temp")
    cr.execute("ALTER TABLE account_move DROP COLUMN dcn_temp")
