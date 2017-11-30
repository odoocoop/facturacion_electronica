# -*- coding: utf-8 -*-
{   'active': True,
    'author': u'Daniel Santibáñez Polanco, Chilean Localization Team 9.0',
    'website': 'http://globalresponse.cl',
    'category': 'Stock/picking',
    'demo_xml': [],
    'depends': [
        'stock',
        'fleet',
        'delivery',
        ],
    'description': u'''
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
        'views/dte.xml',
        'views/stock_picking.xml',
        'views/layout.xml',
        'views/libro_guias.xml',
        'wizard/masive_send_dte.xml',
    ],
    'version': '9.0.4.2',
}
