# -*- coding: utf-8 -*-
{   'active': True,
    'author': u'Daniel Santibáñez Polanco, Cooperativa OdooCoop',
    'website': 'http://globalresponse.cl',
    'category': 'Stock/picking',
    'demo_xml': [],
    'depends': [
        'stock',
        'fleet',
        'delivery',
        'sale_stock',
        'l10n_cl_fe',
        ],
    'description': '''
\n\nMódulo de Guías de Despacho de la localización Chilena.\n\n\nIncluye:\n
- Configuración de libros, diarios (journals) y otros detalles para Guías de despacho en Chile.\n
- Asistente para configurar los talonarios de facturas, boletas, guías de despacho, etc.
''',
    'init_xml': [],
    'installable': True,
    'license': 'AGPL-3',
    'name': u'Guías de Despacho Electrónica para Chile',
    'test': [],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_picking.xml',
        'views/dte.xml',
        'views/layout.xml',
        'views/libro_guias.xml',
        "views/account_invoice.xml",
        'wizard/masive_send_dte.xml',
    ],
    'version': '0.12.2',
    'application': True,
}
