from odoo import models
from odoo.exceptions import UserError


class IRModule(models.Model):
    _inherit = "ir.module.module"

    def modules_to_remove(self):
        modules_to_remove = self.mapped("name")
        if "l10n_cl_dte_point_of_sale" in modules_to_remove:
            if self.env["sii.xml.envio"].search([
                ("state", "=", "Aceptado"),
                ('order_ids', '!=', False)], limit=1):
                raise UserError("NO puede desinstalar el módulo l10n_cl_dte_point_of_sale ya que tiene DTEs válidos emitidos")
        return super(IRModule, self).modules_to_remove()

    def button_uninstall(self):
        modules_to_remove = self.mapped("name")
        if "l10n_cl_dte_point_of_sale" in modules_to_remove:
            if self.env["sii.xml.envio"].search([
                ("state", "=", "Aceptado"),
                ('order_ids', '!=', False)], limit=1):
                raise UserError("NO puede desinstalar el módulo l10n_cl_dte_point_of_sale ya que tiene DTEs válidos emitidos")
        return super(IRModule, self).button_uninstall()
