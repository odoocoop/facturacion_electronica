# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class SetDTEClaimtWizard(models.TransientModel):
    _name = 'set.dte.claim'
    _description = 'Ingresar Reclamo SII'

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


    @api.multi
    def confirm(self):
        dte = self.env['mail.message.dte.document'].browse(self._context.get('active_id', []))
        claims = len(dte.claim_ids) +1
        self.env['mail.message.dte.document.claim'].create({
            'document_id': dte.id,
            'claim': self.claim,
            'date': fields.Datetime.now(),
            'user_id': self.env.uid,
            'claim_description': self.claim_description,
            'sequence': claims,
        })
