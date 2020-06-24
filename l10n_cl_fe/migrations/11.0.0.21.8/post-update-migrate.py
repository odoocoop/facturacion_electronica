# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_fe from version %s to 11.0.0.21.8' % installed_version)

    env = api.Environment(cr, SUPERUSER_ID, {})
    for r in env['account.move.consumo_folios'].sudo().search(
        [
            ('total_neto', '=', 0),
            ('total_exento', '=', 0),
        ]):
        r._resumenes()
    for r in env['ir.sequence'].sudo().search(
        [
            ('sii_document_class_id', '!=', False),
        ]):
        r._qty_available()
