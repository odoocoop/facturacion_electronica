# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.tools.translate import _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    sucursal_id = fields.Many2one(
            'sii.sucursal',
            string="Sucursal",
        )
    sii_code = fields.Char(
            related='sucursal_id.name',
            string="Código SII Sucursal",
            readonly=True,
        )
    journal_document_class_ids = fields.One2many(
            'account.journal.sii_document_class',
            'journal_id',
            'Documents Class',
        )
    document_class_ids = fields.Many2many(
        'sii.document_class',
        string="Document Class IDs"
    )
    use_documents = fields.Boolean(
            string='Use Documents?',
            default='_get_default_doc',
        )
    company_activity_ids = fields.Many2many(
        'partner.activities',
        related='company_id.company_activities_ids'
    )
    journal_activities_ids = fields.Many2many(
            'partner.activities',
            id1='journal_id',
            id2='activities_id',
            string='Journal Turns',
            help="""Select the turns you want to \
            invoice in this Journal""",
        )
    restore_mode = fields.Boolean(
            string="Restore Mode",
            default=False,
        )

    @api.onchange('journal_document_class_ids')
    def set_documents(self):
        self.document_class_ids = []
        for r in self.journal_document_class_ids:
            self.document_class_ids += r.sii_document_class_id

    @api.onchange('journal_activities_ids')
    def max_actecos(self):
        if len(self.journal_activities_ids) > 4:
            raise UserError("Deben Ser máximo 4 actecos por Diario, seleccione los más significativos para este diario")

    @api.multi
    def _get_default_doc(self):
        self.ensure_one()
        if self.type == 'sale' or self.type == 'purchase':
            self.use_documents = True

    @api.multi
    def name_get(self):
        res = []
        for journal in self:
            currency = journal.currency_id or journal.company_id.currency_id
            name = "%s (%s)" % (journal.name, currency.name)
            if journal.sucursal_id and self.env.context.get('show_full_name', False):
                name = "%s (%s)" % (name, journal.sucursal_id.name)
            res.append((journal.id, name))
        return res
