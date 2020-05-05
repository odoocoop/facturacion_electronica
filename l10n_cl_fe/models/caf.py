# -*- coding: utf-8 -*-
from odoo import models, fields, api, SUPERUSER_ID
from odoo.tools.translate import _
from odoo.exceptions import UserError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import pytz
from lxml import etree
import logging
_logger = logging.getLogger(__name__)

try:
    import base64
except ImportError:
    pass


class CAF(models.Model):
    _name = 'dte.caf'
    _description = 'Archivo CAF'

    @api.depends('caf_file')
    def _compute_data(self):
        for caf in self:
            if caf:
                caf.load_caf()

    name = fields.Char(
            string='File Name',
            readonly=True,
            related='filename',
        )
    filename = fields.Char(
            string='File Name',
        )
    caf_file = fields.Binary(
            string='CAF XML File',
            filters='*.xml',
            required=True,
            help='Upload the CAF XML File in this holder',
        )
    issued_date = fields.Date(
            string='Issued Date',
            compute='_compute_data',
            store=True,
        )
    expiration_date = fields.Date(
            string='Expiration Date',
            compute='_compute_data',
            store=True,
        )
    sii_document_class = fields.Integer(
            string='SII Document Class',
            compute='_compute_data',
            store=True,
        )
    start_nm = fields.Integer(
            string='Start Number',
            help='CAF Starts from this number',
            compute='_compute_data',
            store=True,
        )
    final_nm = fields.Integer(
            string='End Number',
            help='CAF Ends to this number',
            compute='_compute_data',
            store=True,
        )
    status = fields.Selection(
            [
                ('draft', 'Draft'),
                ('in_use', 'In Use'),
                ('spent', 'Spent'),
            ],
            string='Status',
            default='draft',
            help='''Draft: means it has not been used yet. You must put in in used
in order to make it available for use. Spent: means that the number interval
has been exhausted.''',
        )
    rut_n = fields.Char(
            string='RUT',
            compute='_compute_data',
            store=True,
        )
    company_id = fields.Many2one(
            'res.company',
            string='Company',
            required=False,
            default=lambda self: self.env.user.company_id,
        )
    sequence_id = fields.Many2one(
            'ir.sequence',
            string='Sequence',
        )
    use_level = fields.Float(
            string="Use Level",
            compute='_used_level',
        )
    _sql_constraints = [
                ('filename_unique', 'unique(filename)', 'Error! Filename Already Exist!'),
            ]

    @api.onchange("caf_file",)
    def load_caf(self, flags=False):
        if not self.caf_file or not self.sequence_id:
            return
        result = self.decode_caf().find('CAF/DA')
        self.start_nm = result.find('RNG/D').text
        self.final_nm = result.find('RNG/H').text
        self.sii_document_class = result.find('TD').text
        fa = result.find('FA').text
        self.issued_date = fa
        if self.sequence_id.sii_document_class_id.sii_code not in [34, 52]\
           and not self.sequence_id.sii_document_class_id.es_boleta():
            self.expiration_date = date(int(fa[:4]),
                                    int(fa[5:7]),
                                    int(fa[8:10])
                                   ) + relativedelta(months=6)
        self.rut_n = 'CL' + result.find('RE').text.replace('-', '')
        if self.rut_n != self.company_id.vat.replace('L0', 'L'):
            raise UserError(_(
                'Company vat %s should be the same that assigned company\'s vat: %s!') % (self.rut_n, self.company_id.vat))
        elif self.sii_document_class != self.sequence_id.sii_document_class_id.sii_code:
            raise UserError(_(
                '''SII Document Type for this CAF is %s and selected sequence
associated document class is %s. This values should be equal for DTE Invoicing
to work properly!''') % (self.sii_document_class, self.sequence_id.sii_document_class_id.sii_code))
        if flags:
            return True
        self.status = 'in_use'

    def _set_level(self):
        folio = self.sequence_id.number_next_actual
        try:
            if folio > self.final_nm:
                self.use_level = 100
            elif folio < self.start_nm:
                self.use_level = 0
            else:
                self.use_level = 100.0 * ((int(folio) - self.start_nm) / float(self.final_nm - self.start_nm + 1))
        except ZeroDivisionError:
            self.use_level = 0

    def _used_level(self):
        for r in self:
            r._set_level()

    def decode_caf(self):
        post = base64.b64decode(self.caf_file).decode('ISO-8859-1')
        post = etree.fromstring(post)
        return post
