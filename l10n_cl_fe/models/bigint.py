# -*- coding: utf-8 -*-
from odoo import fields


class BigInt(fields.Integer):
    column_type = ('int8', 'bigint')
