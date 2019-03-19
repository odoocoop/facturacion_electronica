# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_fe from version %s to 11.0.0.8.12' % installed_version)
    env = api.Environment(cr, SUPERUSER_ID, {})
    for row in env['account.invoice'].search([
            ('type', 'in', ['in_invoice', 'in_refund']),
            ('state', '=', 'draft'),
            ('sii_xml_request', '!=', False),
        ]):
        try:
            row.action_invoice_cancel()
            row.action_invoice_draft()
            row.invoice_validate()
        except:
            pass
