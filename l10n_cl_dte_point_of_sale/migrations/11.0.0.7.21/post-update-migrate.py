# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_dte_point_of_sale from version %s to 11.0.0.7.21' % installed_version)

    cr.execute("UPDATE pos_order po SET document_class_id=se.sii_document_class_id FROM ir_sequence se WHERE se.id=po.sequence_id")
