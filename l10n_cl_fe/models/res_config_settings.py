# -*- coding: utf-8 -*-
from ast import literal_eval
from odoo import api, fields, models
from openerp.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    auto_send_dte = fields.Integer(
            string="Tiempo de Espera para Enviar DTE automático al SII (en horas)",
            default=12,
        )
    auto_send_email = fields.Boolean(
            string="Enviar Email automático al Auto Enviar DTE al SII",
            default=True,
        )
    dte_email_id = fields.Many2one(
        'mail.alias',
        related="company_id.dte_email_id"
    )
    limit_dte_lines = fields.Boolean(
        string="Limitar Cantidad de líneas por documento",
        default=False,
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        account_auto_send_dte = int(ICPSudo.get_param('account.auto_send_dte', default=12))
        account_auto_send_email = ICPSudo.get_param('account.auto_send_email', default=True)
        account_limit_dte_lines = ICPSudo.get_param('account.limit_dte_lines', default=False)
        res.update(
                auto_send_email=account_auto_send_email,
                auto_send_dte=account_auto_send_dte,
                limit_dte_lines=account_limit_dte_lines,
            )
        return res

    @api.multi
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        if self.dte_email_id and not self.default_external_email_server:
            raise UserError('Debe Cofigurar Servidor de Correo Externo en la pestaña Opciones Generales')
        ICPSudo.set_param('account.auto_send_dte', self.auto_send_dte)
        ICPSudo.set_param('account.auto_send_email', self.auto_send_email)
        ICPSudo.set_param('account.limit_dte_lines', self.limit_dte_lines)
