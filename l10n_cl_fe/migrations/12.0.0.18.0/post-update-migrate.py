# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_fe from version %s to 12.0.0.18.0' % installed_version)

    env = api.Environment(cr, SUPERUSER_ID, {})
    for r in env['ir.sequence'].sudo().search(
        [
            ('is_dte', '=', True),
            ('sii_document_class_id', '!=', False)
        ]):
        r.autoreponer_caf = True
        r.autoreponer_cantidad = 10
        r.nivel_minimo = 5
        if r.sii_document_class_id.sii_code in [56, 61, 111, 112]:
            r.autoreponer_cantidad = 1
            r.nivel_minimo = 1
