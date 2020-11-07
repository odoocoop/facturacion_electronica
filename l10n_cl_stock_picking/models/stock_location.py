# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class StockLocation(models.Model):
    _inherit = 'stock.location'

    sii_document_class_id = fields.Many2one(
            'sii.document_class',
            string='Document Type',
            required=False,
        )
    sequence_id = fields.Many2one(
            'ir.sequence',
            string='Entry Sequence',
            required=False,
            help="""This field contains the information related to the numbering \
            of the documents entries of this document type.""",
        )
    sucursal_id = fields.Many2one(
        'sii.sucursal',
        string="Sucursal SII"
    )
    sii_code = fields.Char(
        related='sucursal_id.sii_code',
        string="Código de Sucursal SII",
    )
    restore_mode = fields.Boolean(
            string="Modo Restauración",
            default=False,
        )
    company_activity_ids = fields.Many2many("partner.activities", related="company_id.company_activities_ids")
    acteco_ids = fields.Many2many(
            'partner.activities',
            string="Código de Actividades",
        )
