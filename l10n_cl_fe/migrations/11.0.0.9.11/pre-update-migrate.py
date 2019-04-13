# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Pre Migrating l10n_cl_fe from version %s to 11.0.0.9.11' % installed_version)

    cr.execute(
        "ALTER TABLE account_move_book ADD COLUMN xml_temp VARCHAR, ADD COLUMN sii_xml_response_temp VARCHAR, ADD COLUMN sii_receipt_temp VARCHAR, ADD COLUMN sii_send_ident_temp VARCHAR")
    cr.execute(
        "ALTER TABLE account_move_consumo_folios ADD COLUMN xml_temp VARCHAR, ADD COLUMN sii_xml_response_temp VARCHAR, ADD COLUMN sii_send_ident_temp VARCHAR")
    cr.execute(
        "UPDATE account_move_book set xml_temp=sii_xml_request, sii_receipt_temp=sii_receipt, sii_xml_response_temp=sii_xml_response, sii_send_ident_temp=sii_send_ident")
    cr.execute(
        "UPDATE account_move_consumo_folios set xml_temp=sii_xml_request, sii_xml_response_temp=sii_xml_response, sii_send_ident_temp=sii_send_ident")
