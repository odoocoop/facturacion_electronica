from odoo import api, fields, models
from odoo.exceptions import UserError

try:
    from facturacion_electronica import __version__
except ImportError:
    __version__ = "0.0.0"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    auto_send_dte = fields.Integer(string="Tiempo de Espera para Enviar DTE automático al SII (en horas)", default=1,)
    auto_send_email = fields.Boolean(string="Enviar Email automático al Auto Enviar DTE al SII", default=True,)
    auto_send_persistencia = fields.Integer(string="Enviar Email automático al Cliente cada  n horas", default=24,)
    dte_email_id = fields.Many2one("mail.alias", related="company_id.dte_email_id", readonly=False)
    limit_dte_lines = fields.Boolean(related="company_id.limit_dte_lines", string="Limitar Cantidad de líneas por documento", readonly=False)
    url_remote_partners = fields.Char(related="company_id.url_remote_partners", string="Url Remote Partners", readonly=False)
    token_remote_partners = fields.Char(related="company_id.token_remote_partners", string="Token Remote Partners", readonly=False)
    sync_remote_partners = fields.Boolean(related="company_id.sync_remote_partners", string="Sync Remote Partners", readonly=False)
    url_apicaf = fields.Char(related="company_id.url_apicaf", string="URL APICAF", readonly=False)
    token_apicaf = fields.Char(related="company_id.token_apicaf", string="Token APICAF", readonly=False)
    cf_autosend = fields.Boolean(related="company_id.cf_autosend", string="AutoEnviar Consumo de Folios", readonly=False)
    fe_version = fields.Char(string="Versión FE instalado", readonly=True,)
    medios_de_pago_electronico = fields.Many2many(
        'account.journal',
        related="company_id.medios_de_pago_electronico",
        string="Medios de pago Electrónico",
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICPSudo = self.env["ir.config_parameter"].sudo()
        account_auto_send_dte = int(ICPSudo.get_param("account.auto_send_dte", default=1))
        account_auto_send_email = ICPSudo.get_param("account.auto_send_email", default=True)
        account_auto_send_persistencia = int(ICPSudo.get_param("account.auto_send_persistencia", default=24))
        res.update(
            auto_send_email=account_auto_send_email,
            auto_send_dte=account_auto_send_dte,
            auto_send_persistencia=account_auto_send_persistencia,
            fe_version=__version__,
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICPSudo = self.env["ir.config_parameter"].sudo()
        if self.dte_email_id and not self.external_email_server_default:
            raise UserError("Debe Cofigurar Servidor de Correo Externo en la pestaña Opciones Generales")
        ICPSudo.set_param("account.auto_send_dte", self.auto_send_dte)
        ICPSudo.set_param("account.auto_send_email", self.auto_send_email)
        ICPSudo.set_param("account.auto_send_peresistencia", self.auto_send_persistencia)
