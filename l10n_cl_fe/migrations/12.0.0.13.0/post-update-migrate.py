# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_fe from version %s to 12.0.0.13.0' % installed_version)

    env = api.Environment(cr, SUPERUSER_ID, {})
    for r in env['account.journal'].search([('type', 'in', ['sale', 'purchase'])]):
        r.set_documents()
    cr.execute("UPDATE account_invoice set sii_document_number=CAST(reference as BIGINT) where reference ~ '^[0-9]*$' and reference!=''")