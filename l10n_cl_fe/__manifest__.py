# -*- coding: utf-8 -*-
{
    "name": """Facturación Electrónica para Chile\
    """,
    'version': '0.28.0',
    'category': 'Localization/Chile',
    'sequence': 12,
    'author':  'Daniel Santibáñez Polanco, Cooperativa OdooCoop',
    'website': 'https://globalresponse.cl',
    'license': 'AGPL-3',
    'summary': 'Facturación Electrónica para Chile. Mayor información en https://globalresponse.cl',
    'description': """
Facturación Electrónica para Chile. Mayor infromación en https://globalresponse.cl
""",
    'depends': [
            'base',
            'base_address_city',
            'account',
            'purchase',
            'sale_management',
            'l10n_cl_chart_of_account',
            'report_xlsx',
            'contacts',
            'portal',
        ],
    'external_dependencies': {
        'python': [
            'facturacion_electronica',
            'base64',
            'hashlib',
            'suds',
            'ast',
            'num2words',
            'xlsxwriter',
            'io',
            'PIL',#Via Pillow
            'urllib3',
            'fitz', # Via PyMUPDF, no instalar directo fitz
        ]
    },
    'data': [
            'views/sii_menuitem.xml',
            'wizard/apicaf.xml',
            'wizard/masive_send_dte.xml',
            'wizard/masive_dte_process.xml',
            'wizard/masive_dte_accept.xml',
            'wizard/notas.xml',
            'wizard/upload_xml.xml',
            'wizard/validar.xml',
            'views/assets.xml',
            'wizard/journal_config_wizard_view.xml',
            'views/account_tax_mepco.xml',
            'views/account_tax.xml',
            'views/account_invoice.xml',
            'views/consumo_folios.xml',
            'views/caf.xml',
            'views/export.xml',
            'views/layout.xml',
            'views/libro_compra_venta.xml',
            'views/libro_honorarios.xml',
            'views/mail_dte.xml',
            'views/partner_activities.xml',
            'views/payment_t_view.xml',
            'views/res_company.xml',
            'views/res_partner.xml',
            'views/res_state_view.xml',
            'views/res_city.xml',
            'views/sii_activity_description.xml',
            'views/sii_cola_envio.xml',
            'views/sii_regional_offices_view.xml',
            'views/sii_firma.xml',
            'views/account_journal_sii_document_class_view.xml',
            'views/account_move_line_view.xml',
            'views/account_move_view.xml',
            'views/account_move_boleta_voucher.xml',
            'views/country_view.xml',
            'views/currency_view.xml',
            'views/honorarios.xml',
            'views/journal_view.xml',
            'views/report_invoice.xml',
            'views/sii_concept_type_view.xml',
            'views/sii_document_class_view.xml',
            'views/sii_document_letter_view.xml',
            'views/sii_document_type_view.xml',
            'views/sii_optional_type_view.xml',
            'views/sii_responsability_view.xml',
            'views/sii_respuesta_cliente.xml',
            'views/sii_sucursal_view.xml',
            'views/sii_xml_envio.xml',
            'views/global_descuento_recargo.xml',
            'views/res_config_settings.xml',
            'views/portal_boleta_layout.xml',
            'views/sale_order.xml',
            'data/responsability.xml',
            'data/counties_data.xml',
            'data/country.xml',
            'data/cron.xml',
            'data/document_type.xml',
            'data/partner.activities.csv',
            'data/partner.xml',
            'data/product.xml',
            'data/sequence.xml',
            'data/sii.concept_type.csv',
            'data/sii.document_letter.csv',
            'data/sii.document_class.csv',
            'data/sii.regional.offices.csv',
            'data/decimal_precision.xml',
            'data/res.currency.csv',
            'security/state_manager.xml',
            'security/ir.model.access.csv',
    ],
    'qweb': [
        "static/src/xml/base.xml",
    ],
    'post_init_hook': '_set_default_configs',
    'installable': True,
    'auto_install': False,
    'application': True,
}
