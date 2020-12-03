# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _
import ast
from datetime import datetime, timedelta, date
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
import logging
_logger = logging.getLogger(__name__)


class ColaEnvio(models.Model):
    _name = "sii.cola_envio"

    doc_ids = fields.Char(
            string="Id Documentos",
        )
    model = fields.Char(
            string="Model destino",
        )
    user_id = fields.Many2one(
            'res.users',
        )
    tipo_trabajo = fields.Selection(
            [
                    ('pasivo', 'pasivo'),
                    ('envio', 'Envío'),
                    ('consulta', 'Consulta'),
                    ('persistencia', 'Persistencia Respuesta'),
            ],
            string="Tipo de trabajo",
        )
    active = fields.Boolean(
            string="Active",
            default=True,
        )
    n_atencion = fields.Char(
            string="Número atención",
        )
    set_pruebas = fields.Boolean(string="Set de pruebas", default=False)
    date_time = fields.Datetime(
            string='Auto Envío al SII',
        )
    send_email = fields.Boolean(
            string="Auto Enviar Email",
            default=False,
        )
    company_id = fields.Many2one(
            'res.company',
            string="Compañia",
    )

    def enviar_email(self, doc):
        if not doc.partner_id:
            return
        doc.send_exchange()

    def _es_doc(self, doc):
        if hasattr(doc, 'sii_message'):
            return doc.sii_message
        return True

    def _procesar_tipo_trabajo(self):
        if not self.user_id.active:
            _logger.warning("¡Usuario %s desactivado!" % self.user_id.name)
            return
        docs = self.env[self.model].with_context(
                    user=self.user_id.id,
                    company_id=self.company_id.id,
                    set_pruebas=self.set_pruebas
                    ).browse(ast.literal_eval(self.doc_ids))
        if self.tipo_trabajo == 'persistencia':
            if self.date_time and datetime.now() >= datetime.strptime(
                            self.date_time, DTF):
                for doc in docs:
                    if  doc.partner_id and datetime.strptime(
                            doc.sii_xml_request.create_date, DTF) <= (
                                datetime.now() + timedelta(days=8)) \
                            and self.env['sii.respuesta.cliente'].search([
                                    ('id', 'in', doc.respuesta_ids.ids),
                                    ('company_id', '=', self.company_id.id),
                                    ('recep_envio', '=', 'no_revisado'),
                                    ('type', '=', 'RecepcionEnvio'),
                    ]):
                        self.enviar_email(doc)
                    else:
                        docs -= doc
                if not docs:
                    self.unlink()
                else:
                    persistente = int(self.env[
                                    'ir.config_parameter'].sudo().get_param(
                                            'account.auto_send_persistencia',
                                            default=24))
                    self.date_time = (datetime.now() + timedelta(
                                        hours=int(persistente)
                                    ))

            return
        if self.tipo_trabajo == 'pasivo':
            if docs[0].sii_xml_request and docs[0].sii_xml_request.state in [
                            'Aceptado', 'Enviado', 'Rechazado', 'Anulado']:
                self.unlink()
                return
            if self.date_time and datetime.now() >= datetime.strptime(
                            self.date_time, DTF):
                try:
                    envio_id = docs.do_dte_send(self.n_atencion)
                    if envio_id.sii_send_ident:
                        self.tipo_trabajo = 'consulta'
                except Exception as e:
                    _logger.warning('Error en Envío automático')
                    _logger.warning(str(e))
                try:
                    envio_id.get_send_status()
                except Exception as e:
                    _logger.warning("error temporal en cola %s" % str(e))
            return
        if self._es_doc(docs[0]) and docs[0].sii_result in [
                                        'Proceso', 'Reparo',
                                        'Rechazado', 'Anulado']:
            if self.send_email and docs[0].sii_result in ['Proceso', 'Reparo']:
                for doc in docs:
                    if not doc.partner_id:
                        docs-= doc
                        continue
                    self.enviar_email(doc)
                if not docs:
                    self.unlink()
                    return
                self.tipo_trabajo = 'persistencia'
                persistente = int(self.env[
                                'ir.config_parameter'].sudo().get_param(
                                        'account.auto_send_persistencia',
                                        default=24))
                self.date_time = (datetime.now() + timedelta(
                                    hours=int(persistente)
                                ))
                return
            self.unlink()
            return
        if self.tipo_trabajo == 'consulta':
            try:
                docs.ask_for_dte_status()
            except Exception as e:
                _logger.warning("Error en Consulta")
                _logger.warning(str(e))
        elif self.tipo_trabajo == 'envio' and (
            not docs[0].sii_xml_request or \
            not docs[0].sii_xml_request.sii_send_ident or \
            docs[0].sii_xml_request.state not in ['Aceptado', 'Enviado']):
            envio_id = False
            try:
                envio_id = docs.with_context(
                            user=self.user_id.id,
                            company_id=self.company_id.id).do_dte_send(
                                                            self.n_atencion)
                if envio_id.sii_send_ident:
                    self.tipo_trabajo = 'consulta'
            except Exception as e:
                _logger.warning("Error en envío Cola")
                _logger.warning(str(e))
            if envio_id:
                try:
                    envio_id.get_send_status()
                except Exception as e:
                    _logger.warning(
                        "Error temporal de conexión en consulta %s" % str(e))
        elif self.tipo_trabajo == 'envio' and docs[0].sii_xml_request and (
            docs[0].sii_xml_request.sii_send_ident or \
            docs[0].sii_xml_request.state in [ 'Aceptado',
                                              'Enviado', 'Rechazado']):
            self.tipo_trabajo = 'consulta'

    @api.model
    def _cron_procesar_cola(self):
        ids = self.search([("active", "=", True), ('tipo_trabajo', '=', 'envio')], limit=20)
        if ids:
            for c in ids:
                try:
                    c._procesar_tipo_trabajo()
                except Exception as e:
                    _logger.warning("error al procesartipo trabajo %s"%str(e))
        ids = self.search([("active", "=", True), ('tipo_trabajo', '=', 'pasivo')], limit=20)
        if ids:
            for c in ids:
                try:
                    c._procesar_tipo_trabajo()
                except Exception as e:
                    _logger.warning("error al procesartipo trabajo %s"%str(e))
        ids = self.search([("active", "=", True), ('tipo_trabajo', '=', 'consulta')], limit=20)
        if ids:
            for c in ids:
                try:
                    c._procesar_tipo_trabajo()
                except Exception as e:
                    _logger.warning("error al procesartipo trabajo %s"%str(e))
        ids = self.search([("active", "=", True), ('tipo_trabajo', '=', 'persistencia')], limit=20)
        if ids:
            for c in ids:
                try:
                    c._procesar_tipo_trabajo()
                except Exception as e:
                    _logger.warning("error al procesartipo trabajo %s"%str(e))
