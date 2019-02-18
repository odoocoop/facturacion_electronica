# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Pre Migrating l10n_cl_fe from version %s to 11.0.0.7.5' % installed_version)

    cr.execute(
        "ALTER TABLE res_company ADD COLUMN key_file_temp BYTEA, ADD COLUMN filename_temp varchar")
    cr.execute(
        "ALTER TABLE res_users ADD COLUMN key_file_temp BYTEA, ADD COLUMN filename_temp varchar")
    cr.execute(
        "UPDATE res_users set filename_temp=filename,key_file_temp=key_file  where key_file!=''")
    cr.execute(
        "UPDATE res_company set filename_temp=filename,key_file_temp=key_file  where key_file!=''")
    cr.execute("CREATE TABLE back_res_c AS TABLE res_company_res_users_rel")

