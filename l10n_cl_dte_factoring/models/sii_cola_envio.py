# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
import ast
import logging
_logger = logging.getLogger(__name__)


class ColaEnvio(models.Model):
    _inherit = "sii.cola_envio"

    tipo_trabajo = fields.Selection(
        selection_add=[
            ('cesion','Cesion'),
            ('cesion_consulta','Consulta Cesion')
        ]
    )

    def _procesar_tipo_trabajo(self):
        if self.tipo_trabajo in ['cesion', 'cesion_consulta' ]:
            docs = self.env[self.model].sudo(self.user_id.id).browse(ast.literal_eval(self.doc_ids))
            if self.tipo_trabajo == 'cesion':
                try:
                    docs.cesion_dte_send()
                    if docs[0].sii_cesion_result not in ['', 'NoEnviado']:
                        self.tipo_trabajo = 'cesion_consulta'
                except Exception as e:
                    _logger.warning("Error en envío Cola")
                    _logger.warning(str(e))
            else:
                try:
                    docs[0].ask_for_cesion_dte_status()
                    if docs[0].sii_cesion_result not in ['enviado']:
                        self.unlink()
                except Exception as e:
                    _logger.warning("Error en Consulta")
                    _logger.warning(str(e))
            return
        return super(ColaEnvio, self)._procesar_tipo_trabajo()

    @api.model
    def _cron_procesar_cola(self):
        super(ColaEnvio, self)._cron_procesar_cola()
        ids = self.search([("active", "=", True), ('tipo_trabajo', '=', 'cesion')], limit=20)
        if ids:
            for c in ids:
                try:
                    c._procesar_tipo_trabajo()
                except Exception as e:
                    _logger.warning("error al procesartipo trabajo cesion %s"%str(e))
        ids = self.search([("active", "=", True), ('tipo_trabajo', '=', 'cesion_consulta')], limit=20)
        if ids:
            for c in ids:
                try:
                    c._procesar_tipo_trabajo()
                except Exception as e:
                    _logger.warning("error al procesartipo trabajo cesion consulta %s"%str(e))
