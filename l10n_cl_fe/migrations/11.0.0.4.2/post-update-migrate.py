# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_fe from version %s to 11.0.0.4.2' % installed_version)

    env = api.Environment(cr, SUPERUSER_ID, {})
    cf_obj = env['account.move.consumo_folios']
    cfs = cf_obj.search( [])
    for cf in cfs:
        cfs_day = cf_obj.search( [('fecha_inicio', '=', cf.fecha_inicio),
            ('state', 'not in', ['draft', 'Rechazado', 'Anulado']),
            ('company_id', '=', cf.company_id.id),
            ('id', '!=', cf.id),
            ('sec_envio', '<', cf.sec_envio)
            ])
        for cf_day in cfs_day:
            cf_day.state = 'Anulado'
        cf.get_totales()
