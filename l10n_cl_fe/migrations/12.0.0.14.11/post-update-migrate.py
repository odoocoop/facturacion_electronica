# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_fe from version %s to 12.0.0.14.11' % installed_version)

    env = api.Environment(cr, SUPERUSER_ID, {})
    for r in env['account.journal.sii_document_class'].sudo().search([]):
        r.company_id = r.journal_id.company_id.id