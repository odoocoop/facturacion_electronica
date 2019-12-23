# -*- coding: utf-8 -*-
from __future__ import print_function
from odoo import api, models, fields
from odoo.tools.translate import _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountJournalDocumentConfig(models.TransientModel):
    _name = 'account.journal.document_config'
    _description = 'Wizard configuración secuencias para diarios DTE'

    def _es_compra(self):
        context = dict(self._context or {})
        journal_ids = context.get('active_ids', False)
        journal = self.env['account.journal'].browse(journal_ids)
        if journal.type == "purchase":
            return True
        return False

    dte_register = fields.Boolean(
            string='Register Electronic Documents?',
            default=True,
            help="""This option allows you to register electronic documents (DTEs).
""")
    non_dte_register = fields.Boolean(
            'Register Manual Documents?')
    electronic_ticket = fields.Boolean(
            string='¿Incluir Boleta Electrónica?',
        )
    free_tax_zone = fields.Boolean(
            'Register Free-Tax Zone or # 1057 Resolution Documents?')
    settlement_invoice = fields.Boolean(
            'Register Settlement Invoices?')
    weird_documents = fields.Boolean(
            'Unusual Documents', help="""
Include unusual taxes documents, as transfer invoice, and reissue
""")
    other_available = fields.Boolean(
            'Others available?',
            default='_get_other_avail',
        )
    purchase = fields.Boolean(
            'Compra',
            default=lambda self: self._es_compra(),
        )

    @api.model
    def _get_other_avail(self):
        return True

    def _check_activities(self):
        for r in self:
            if 'purchase' in r.type:
                r.excempt_documents = True
            elif 'sale' in r.type:
                no_vat = False
                for turn in r.journal_activities_ids:
                    if turn.vat_affected == 'SI':
                        continue
                    else:
                        no_vat = True
                        break
                self.excempt_documents = no_vat

    @api.multi
    def confirm(self):
        context = dict(self._context or {})
        journal_ids = context.get('active_ids', False)
        if self.purchase:
            self.non_dte_register = True
            self.electronic_ticket = True
        self.create_journals(journal_ids)

    def create_journals(self, journal_ids):
        for journal in self.env['account.journal'].browse(journal_ids):
            responsability = journal.company_id.responsability_id
            if not responsability.id:
                raise UserError(
                    _('Your company has not setted any responsability. Please, set your company responsability in the company partner before continue.'))
            journal_type = journal.type
            if journal_type in ['sale', 'sale_refund']:
                letter_ids = []
                for x in responsability.issued_letter_ids:
                    if self.electronic_ticket or x.name != 'B':
                        letter_ids.append(x.id)
            elif journal_type in ['purchase', 'purchase_refund']:
                letter_ids = [x.id for x in responsability.received_letter_ids]

            if journal_type == 'sale':
                for doc_type in ['invoice', 'credit_note', 'debit_note']:
                    self.create_journal_document(letter_ids, doc_type, journal)
            elif journal_type == 'purchase':
                for doc_type in ['invoice', 'debit_note', 'credit_note', 'invoice_in']:
                    self.create_journal_document(letter_ids, doc_type, journal)

    def create_sequence(self, name, journal, document_class):
        vals = {
            'name': journal.name + ' - ' + name,
            'padding': 6,
            'implementation': 'no_gap',
            'sii_document_class_id': document_class.id,
            'company_id': journal.company_id.id,
            'forced_by_caf': True,
            'autoreponer_caf': True,
            'autoreponer_cantidad': 1 if document_class.sii_code in [56, 61, 111, 112] else 10,
            'nivel_minimo': 1 if document_class.sii_code in [56, 61, 111, 112] else 5,
        }
        return vals

    def create_journal_document(self, letter_ids, document_type, journal):
        if_zf = [] if self.free_tax_zone else [901, 906, 907]
        if_lf = [] if self.settlement_invoice else [40, 43]
        if_tr = [] if self.weird_documents else [29, 108, 914, 911, 904, 905]
        # if_pr = [] if wz.purchase_invoices else [45, 46]
        if_na = [] #if journal.excempt_documents else [32, 34]
        dt_types_exclude = if_zf + if_lf + if_tr + if_na
        domain = [
            ('document_letter_id', 'in', letter_ids),
            ('document_type', '=', document_type),
            ('sii_code', 'not in', dt_types_exclude)
        ]
        if not self.non_dte_register and journal.type == 'sale':
            domain.append(('dte', '=', True))
        document_class_obj = self.env['sii.document_class']
        document_class_ids = document_class_obj.search(domain)
        journal.document_class_ids = document_class_ids.ids
        if journal.type == 'purchase':
            return
        journal_document_obj = self.env['account.journal.sii_document_class']
        sequence = 10
        for document_class in document_class_ids:
            sequence_id = self.env['ir.sequence']
            seq_vals = self.create_sequence(
                                    document_class.name,
                                    journal,
                                    document_class)
            sequence_id = self.env['ir.sequence'].create(seq_vals)
            vals = {
                'sii_document_class_id': document_class.id,
                'sequence_id': sequence_id.id,
                'journal_id': journal.id,
                'sequence': sequence,
            }
            journal_document_obj.create(vals)
            sequence += 10
