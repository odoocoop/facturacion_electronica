# -*- coding: utf-8 -*-
{
    "name": """Global Discount\
    """,
    'version': '9.0.0.4.0',
    'category': 'Accoun/invoice',
    'sequence': 12,
    'author':  'Daniel Santibáñez Polanco',
    'website': 'http://globalresponse.cl',
    'license': 'AGPL-3',
    'summary': '',
    'description': """
Make available a global discount.
===============================================================
""",
    'depends': [
        'account',
        'sale',
        'l10n_cl_invoice',
        'l10n_cl_dte',
        ],
    'data': [
        #'security/ir.model.access.csv',
        'views/account_invoice.xml',
        'views/layout.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
