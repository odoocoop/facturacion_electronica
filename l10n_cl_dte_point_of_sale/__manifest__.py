# -*- coding: utf-8 -*-
{
    "name": """Boleta / Factura Electrónica Chilena para punto de ventas \
    """,
    'version': '0.12.4',
    'category': 'Point of Sale/Localization/Chile',
    'sequence': 12,
    'author':  'Daniel Santibáñez Polanco, Cooperativa OdooCoop',
    'website': 'https://globalresponse.cl',
    'license': 'AGPL-3',
    'summary': '',
    'description': """
Chile: API and GUI to access Electronic Invoicing webservices for Point of Sale.
""",
    'depends': [
        'l10n_cl_fe',
        'account',
        'point_of_sale',
        'portal',
        ],
    'external_dependencies': {
        'python': [
        ]
    },
    'data': [
        'data/report_paperformat.xml',
        'report/report_pos_common_templates.xml',
        'report/report_pos_boleta.xml',
        'wizard/notas.xml',
        'views/pos_dte.xml',
        'views/pos_config.xml',
        'views/pos_session.xml',
        'views/point_of_sale.xml',
        'views/portal_boleta_layout.xml',
        'views/sii_xml_envio.xml',
        'wizard/masive_send_dte.xml',
#        'data/sequence.xml',
        'security/ir.model.access.csv',
    ],
    'qweb': [
        'static/src/xml/layout.xml',
        'static/src/xml/client.xml',
        'static/src/xml/payment.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
