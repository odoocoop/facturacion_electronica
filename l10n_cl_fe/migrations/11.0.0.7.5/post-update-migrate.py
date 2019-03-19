# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_fe from version %s to 11.0.0.7.5' % installed_version)

    def process_firma(row):
        users = []
        if row.get('user_id'):
            users.append(row.get('user_id'))
        else:
            cr.execute(
                "SELECT res_users_id FROM res_company_res_users_rel WHERE res_company_id=%s" % row['company_id'])
            for row_u in cr.dictfetchall():
                users.append(row_u['res_users_id'])
        if len(users) == 0:
            users.append(1)
        env = api.Environment(cr, SUPERUSER_ID, {})
        firma = env['sii.firma'].create({
                    'file_content': row['key_file_temp'].tobytes(),
                    'name': row['filename_temp'],
                    'cert': row['cert_temp'],
                    'priv_key': row['priv_temp'],
                    'expire_date': row['expire_temp'],
                    'emision_date': row['emision_temp'],
                    'subject_serial_number': row['serial_temp'],
                    'company_ids': [env.user.company_id.id],
                    'user_ids': users,
                    'priority': 1,
                    'active': True,
                    'state': 'valid',
        })
        #firma.action_process()
    cr.execute(
        "SELECT filename_temp, key_file_temp, cert_temp, priv_temp, expire_temp, emision_temp, serial_temp, company_id, id as user_id FROM res_users ru WHERE ru.key_file_temp!=''")
    for row in cr.dictfetchall():
        process_firma(row)
    cr.execute(
        "SELECT filename_temp, key_file_temp, key_file_temp, cert_temp, priv_temp, expire_temp, emision_temp, serial_temp, id as company_id FROM res_company rc WHERE rc.key_file_temp!=''")
    for row in cr.dictfetchall():
        process_firma(row)

    cr.execute("ALTER TABLE res_users DROP COLUMN key_file_temp, DROP COLUMN filename_temp, DROP COLUMN cert_temp, DROP COLUMN priv_temp, DROP COLUMN expire_temp, DROP COLUMN emision_temp, DROP COLUMN serial_temp")
    cr.execute("ALTER TABLE res_company DROP COLUMN key_file_temp, DROP COLUMN filename_temp, DROP COLUMN cert_temp, DROP COLUMN priv_temp, DROP COLUMN expire_temp, DROP COLUMN emision_temp, DROP COLUMN serial_temp")
    cr.execute("DROP TABLE back_res_c")
