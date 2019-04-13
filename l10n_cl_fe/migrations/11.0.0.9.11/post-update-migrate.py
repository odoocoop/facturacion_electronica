# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning('Post Migrating l10n_cl_fe from version %s to 11.0.0.9.11' % installed_version)

    cr.execute('ALTER TABLE sii_xml_envio ADD COLUMN book_temp INTEGER, ADD COLUMN cf_temp INTEGER')
    cr.execute(
        "INSERT INTO sii_xml_envio (book_temp, xml_envio, company_id, sii_send_ident, sii_receipt, sii_xml_response, state, name ) SELECT id, xml_temp, company_id, sii_send_ident, sii_receipt_temp, sii_xml_response_temp, state, name FROM account_move_book ai WHERE ai.xml_temp!=''")
    cr.execute(
        "INSERT INTO sii_xml_envio (cf_temp, xml_envio, company_id, sii_send_ident, sii_xml_response, state, name ) SELECT id, xml_temp, company_id, sii_send_ident, sii_xml_response_temp, state, name FROM account_move_consumo_folios ai WHERE ai.xml_temp!=''")

    cr.execute(
        "ALTER TABLE account_move_book DROP COLUMN sii_receipt_temp, DROP COLUMN xml_temp, DROP COLUMN sii_xml_response_temp, DROP COLUMN sii_send_ident_temp")
    cr.execute(
        "ALTER TABLE account_move_consumo_folios DROP COLUMN xml_temp, DROP COLUMN sii_xml_response_temp, DROP COLUMN sii_send_ident_temp")
    cr.execute("UPDATE account_move_book ai SET sii_xml_request=sr.id FROM sii_xml_envio sr WHERE ai.id=sr.book_temp")
    cr.execute("UPDATE account_move_consumo_folios ai SET sii_xml_request=sr.id FROM sii_xml_envio sr WHERE ai.id=sr.cf_temp")
    cr.execute("ALTER TABLE sii_xml_envio DROP COLUMN book_temp, DROP COLUMN cf_temp")
