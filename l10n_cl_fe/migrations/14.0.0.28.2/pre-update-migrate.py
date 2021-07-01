import logging

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning("Pre Migrating l10n_cl_fe from version %s to 12.0.0.28.2" % installed_version)

    cr.execute("update res_partner set state_id=null where state_id is not null")
