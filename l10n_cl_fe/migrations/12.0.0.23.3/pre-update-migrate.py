import base64
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning("Pre Migrating l10n_cl_fe from version %s to 12.0.0.23.3" % installed_version)

    cr.execute("ALTER TABLE dte_caf ADD COLUMN caf_string TEXT")
    cr.execute("select id, caf_file from dte_caf")
    for row in cr.dictfetchall():
        cr.execute(
            "update dte_caf set caf_string='%s' where id=%s"
            % (base64.b64decode(row["caf_file"]).decode("ISO-8859-1"), row["id"])
        )
