# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Pre Migrating l10n_cl_fe from version %s to 11.0.0.6.9' % installed_version)


    cr.execute("update ir_model_data set name=replace(name, ' ', '') where module='l10n_cl_fe' and model in ('res.country.state', 'res.city');")
    cr.execute("update ir_model_data set name=concat(name, '00') where  model='res.country.state' and module='l10n_cl_fe' and length(name) =5;")
