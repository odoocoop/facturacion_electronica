# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Pre Migrating l10n_cl_stock_picking from version %s to 11.0.0.8.0' % installed_version)
    cr.execute("DELETE FROM ir_ui_view where name='view_electroinic_stock_picking_form'")
    cr.execute(
        "ALTER TABLE stock_picking ADD COLUMN xml_temp VARCHAR, ADD COLUMN sii_xml_response_temp VARCHAR, ADD COLUMN sii_receipt_temp VARCHAR, ADD COLUMN sii_send_ident_temp VARCHAR, ADD COLUMN sii_send_file_name_temp VARCHAR")
    cr.execute(
        "UPDATE stock_picking set xml_temp=sii_xml_request, sii_receipt_temp=sii_receipt, sii_xml_response_temp=sii_xml_response, sii_send_ident_temp=sii_send_ident, sii_send_file_name_temp=sii_send_file_name")
