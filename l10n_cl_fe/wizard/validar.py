# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError
import logging
import base64
_logger = logging.getLogger(__name__)

try:
    from facturacion_electronica import facturacion_electronica as fe
except:
    _logger.warning('No se ha podido cargar fe')

class ValidarDTEWizard(models.TransientModel):
    _name = 'sii.dte.validar.wizard'
    _description = 'SII XML from Provider'

    def _get_docs(self):
        if not self.tipo.model == 'mail.message.dte.document':
            return self.env['mail.message.dte.document']
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        return [(6, 0, active_ids)]

    def _get_invs(self):
        if not self.tipo.model == 'account.invoice':
            return self.env['account.invoice']
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        return [(6, 0, active_ids)]

    action = fields.Selection(
        [
            ('receipt', 'Recibo de mercaderías'),
            ('validate', 'Aprobar comercialmente'),
        ],
        string="Acción",
        default="validate",
    )
    invoice_ids = fields.Many2many(
        'account.invoice',
        string="Facturas",
        default=_get_invs,
    )
    document_ids = fields.Many2many(
        'mail.message.dte.document',
        string="Documetnos Dte",
        default=_get_docs,
    )
    option = fields.Selection(
        [
            ('accept', 'Aceptar'),
            ('reject', 'Rechazar'),
        ],
        string="Opción",
    )
    claim = fields.Selection(
        [
            ('ACD', 'Acepta Contenido del Documento'),
            ('RCD', 'Reclamo al  Contenido del Documento '),
            ('ERM', 'Otorga  Recibo  de  Mercaderías  o Servicios'),
            ('RFP', 'Reclamo por Falta Parcial de Mercaderías'),
            ('RFT', 'Reclamo por Falta Total de Mercaderías'),
        ],
        string="Reclamo",
        required=True,
    )
    claim_description = fields.Char(
        string="Glosa Reclamo",
    )
    tipo = fields.Many2one(
        'ir.model',
        string="Tipo de Documento",
        domain=[('model', 'in', ['account.invoice', 'mail.message.dte.document'])]
    )

    @api.multi
    def confirm(self):
        #if self.action == 'validate':
        self.do_receipt()
        self.do_validar_comercial()
        #   _logger.info("ee")

    def do_reject(self, document_ids):
        for doc in document_ids:
            claims = 1
            claim = self.env['sii.dte.claim'].create({
                'claim': self.claim,
                'date': fields.Datetime.now(),
                'user_id': self.env.uid,
                'claim_description': self.claim_description,
                'sequence': claims,
            })
            if self.tipo.model == 'account.invoice':
                claim.invoice_id = doc.id
            else:
                claim.document_id = doc.id
            claim.do_reject(doc)

    def do_validar_comercial(self):
        for doc in self.invoice_ids:
            claims = 1
            claim = self.env['sii.dte.claim'].create({
                'invoice_id': inv.id,
                'claim': self.claim,
                'date': fields.Datetime.now(),
                'user_id': self.env.uid,
                'claim_description': self.claim_description,
                'sequence': claims,
            })
            if self.tipo.model == 'account.invoice':
                claim.invoice_id = doc.id
            else:
                claim.document_id = doc.id
            claim.do_validar_comercial()

    @api.multi
    def do_receipt(self):
        message = ""
        for doc in self.invoice_ids:
            claim = self.env['sii.dte.claim'].create({
                'invoice_id': inv.id,
                'claim': self.claim,
                'date': fields.Datetime.now(),
                'user_id': self.env.uid,
                'claim_description': self.claim_description,
                'sequence': claims,
            })
            if self.tipo.model == 'account.invoice':
                claim.invoice_id = doc.id
            else:
                claim.document_id = doc.id
            claim.do_recep_mercaderia()
