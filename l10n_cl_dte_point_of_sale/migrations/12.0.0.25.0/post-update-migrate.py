# -*- coding: utf-8 -*-
import logging
from odoo import SUPERUSER_ID, api
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_dte_point_of_sale from version %s to 12.0.0.25.0' % installed_version)

    env = api.Environment(cr, SUPERUSER_ID, {})
    for r in env["pos.config"].search([
        '|', ('secuencia_boleta', '!=', False),
        ('secuencia_boleta_exenta', '!=', False)]):
        r.acteco_ids += r.company_activity_ids[:4]
