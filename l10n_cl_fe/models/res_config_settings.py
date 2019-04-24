# -*- coding: utf-8 -*-
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
    url_apicaf = fields.Char(
            string="URL APICAF",
            default='https://apicaf.cl/api/caf',
    )
    token_apicaf = fields.Char(
            string="Token APICAF",
            default='token_publico',
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        account_auto_send_dte = int(ICPSudo.get_param('account.auto_send_dte', default=12))
        account_auto_send_email = ICPSudo.get_param('account.auto_send_email', default=True)
        account_limit_dte_lines = ICPSudo.get_param('account.limit_dte_lines', default=False)
        partner_url_remote_partners = ICPSudo.get_param('partner.url_remote_partners', default='https://sre.cl/api/company_info')
        partner_token_remote_partners = ICPSudo.get_param('partner.token_remote_partners', default="token_publico")
        partner_sync_remote_partners = ICPSudo.get_param('partner.sync_remote_partners', default=True)
        dte_url_apicaf = ICPSudo.get_param('dte.url_apicaf', default='https://apicaf.cl/api/caf')
        dte_token_apicaf = ICPSudo.get_param('dte.token_apicaf', default="token_publico")
        res.update(
                auto_send_email=account_auto_send_email,
                auto_send_dte=account_auto_send_dte,
                limit_dte_lines=account_limit_dte_lines,
                url_remote_partners=partner_url_remote_partners,
                token_remote_partners=partner_token_remote_partners,
                sync_remote_partners=partner_sync_remote_partners,
                url_apicaf=dte_url_apicaf,
                token_apicaf=dte_token_apicaf,
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
        ICPSudo.set_param('partner.url_remote_partners', self.url_remote_partners)
        ICPSudo.set_param('partner.token_remote_partners', self.token_remote_partners)
        ICPSudo.set_param('partner.sync_remote_partners', self.sync_remote_partners)
        ICPSudo.set_param('dte.url_apicaf', self.url_apicaf)
        ICPSudo.set_param('dte.token_apicaf', self.token_apicaf)
