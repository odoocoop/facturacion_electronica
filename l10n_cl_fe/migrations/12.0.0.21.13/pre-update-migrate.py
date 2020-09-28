import logging

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning("Pre Migrating l10n_cl_fe from version %s to 12.0.0.21.13" % installed_version)

    cr.execute("ALTER TABLE ir_sequence ADD COLUMN qty_available INTEGER")
