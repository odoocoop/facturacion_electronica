# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Pre Migrating l10n_cl_fe from version %s to 11.0.0.7.5' % installed_version)

    cr.execute(
        "ALTER TABLE res_company ADD COLUMN key_file_temp BYTEA, ADD COLUMN filename_temp varchar, ADD COLUMN cert_temp text, ADD COLUMN priv_temp text, ADD COLUMN expire_temp date, ADD COLUMN emision_temp date, ADD COLUMN serial_temp varchar")
    cr.execute(
        "ALTER TABLE res_users ADD COLUMN key_file_temp BYTEA, ADD COLUMN filename_temp varchar, ADD COLUMN cert_temp text, ADD COLUMN priv_temp text, ADD COLUMN expire_temp date, ADD COLUMN emision_temp date, ADD COLUMN serial_temp varchar")
    cr.execute(
        "UPDATE res_users set filename_temp=filename,key_file_temp=key_file, cert_temp=cert, priv_temp=priv_key,expire_temp=not_after,emision_temp=not_before,serial_temp=subject_serial_number  where key_file!=''")
    cr.execute(
        "UPDATE res_company set filename_temp=filename,key_file_temp=key_file, cert_temp=cert, priv_temp=priv_key,expire_temp=not_after,emision_temp=not_before,serial_temp=subject_serial_number  where key_file!=''")
    cr.execute("CREATE TABLE back_res_c AS TABLE res_company_res_users_rel")

