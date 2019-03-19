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
    url_remote_partners = fields.Char(
            string="Url Remote Partners",
            default="https://sre.cl/api/company_info"
    )
    token_remote_partners = fields.Char(
            string="Token Remote Partners",
            default="token_publico",
    )
    sync_remote_partners = fields.Boolean(
            string="Sync Remote Partners",
            default=True,
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        account_auto_send_dte = int(ICPSudo.get_param('account.auto_send_dte', default=12))
        account_auto_send_email = ICPSudo.get_param('account.auto_send_email', default=True)
        account_limit_dte_lines = ICPSudo.get_param('account.limit_dte_lines', default=False)
        account_url_remote_partners = ICPSudo.get_param('account.url_remote_partners', default='https://sre.cl/api/company_info')
        account_token_remote_partners = ICPSudo.get_param('account.token_remote_partners', default="token_publico")
        account_sync_remote_partners = ICPSudo.get_param('account.sync_remote_partners', default=True)
        res.update(
                auto_send_email=account_auto_send_email,
                auto_send_dte=account_auto_send_dte,
                limit_dte_lines=account_limit_dte_lines,
                url_remote_partners=account_url_remote_partners,
                token_remote_partners=account_token_remote_partners,
                sync_remote_partners=account_sync_remote_partners,
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
        ICPSudo.set_param('account.url_remote_partners', self.url_remote_partners)
        ICPSudo.set_param('account.token_remote_partners', self.token_remote_partners)
        ICPSudo.set_param('account.sync_remote_partners', self.sync_remote_partners)
