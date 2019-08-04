# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.translate import _
import json
import logging
_logger = logging.getLogger(__name__)

try:
    import urllib3
    urllib3.disable_warnings()
    pool = urllib3.PoolManager()
except:
    _logger.warning("Problemas con urllib3")


class apicaf(models.TransientModel):
    _name = "dte.caf.apicaf"

    @api.onchange('firma')
    def conectar_api(self):
        if not self.firma:
            return
        ICPSudo = self.env['ir.config_parameter'].sudo()
        url = ICPSudo.get_param('dte.url_apicaf')
        token = ICPSudo.get_param('dte.token_apicaf')
        params = {
            'firma_electronica': {
                'priv_key': self.firma.priv_key,
                'cert': self.firma.cert,
                'init_signature': False,
                'subject_serial_number': self.firma.subject_serial_number,
            },
            'token': token,
            'rut': self.company_id.document_number,
            'etapa': self.etapa,
            'entorno': 'produccion' if self.company_id.dte_service_provider ==  'SII' else 'certificacion'
        }
        resp = pool.request('POST', url, body=json.dumps(params))
        if resp.status != 200:
            _logger.warning("Error en conexión con api apicaf %s" % resp.data)
            message = ''
            if resp.status == 403:
                data = json.loads(resp.data.decode('ISO-8859-1'))
                message = data['message']
            else:
                message = str(resp.data)
            self.env['bus.bus'].sendone((
                self._cr.dbname, 'dte.caf.apicaf',
                self.env.user.partner_id.id), {
                        'title': "Error en conexión con apicaf",
                        'message': message,
                        'url': {
                            'name': 'ir a apicaf.cl',
                            'uri': 'https://apicaf.cl'
                        },
                        'type': 'dte_notif',
                })
            return
        data = json.loads(resp.data.decode('ISO-8859-1'))
        self.etapa = data['etapa']
        self.id_peticion = data['id_peticion']
        '''@TODO verificación de folios autorizados en el SII'''
        if self.cod_docto:
            self.get_disp()

    documentos = fields.Many2many(
            'account.journal.sii_document_class',
            string="Documentos disponibles",
        )
    jdc_id = fields.Many2one(
            'account.journal.sii_document_class',
            string="Secuencia de diario"
        )
    sequence_id = fields.Many2one(
            'ir.sequence',
            string="Secuencia"
        )
    cod_docto = fields.Many2one(
            'sii.document_class',
            related="sequence_id.sii_document_class_id",
            string="Código Documento",
            readonly=True,
        )
    etapa = fields.Selection(
            [
                ('conectar', 'Conectar al SII'),
                ('listar', 'Listar documentos'),
                ('disponibles', 'Folios disponibles para el Tipo de Documento'),
                ('confirmar', 'Confirmar Folios'),
                ('obtener', 'Obtener Folios'),
                ('archivo', 'Obtener archivo'),
            ],
            default='conectar',
            string='Etapa',
            required=True,
        )
    folios_disp = fields.Integer(
            string="Folios disponibles SIN USAR",
            default=0,
            readonly=True,
        )
    max_autor = fields.Integer(
            string="Cantidad Máxima Autorizada para el Documento",
            default=0,
            readonly=True,
        )
    cant_doctos = fields.Integer(
            string="Cantidad de Folios a Solicitar",
            default=0,
        )
    company_id = fields.Many2one(
            'res.company',
            string="Compañía"
        )
    firma = fields.Many2one(
            'sii.firma',
            string="Firma Electrónica"
        )
    id_peticion = fields.Integer(
            string="ID Petición",
            default=0,
        )

    @api.onchange('jdc_id')
    def _set_cod_docto(self):
        if not self.documentos:
            return
        self.cod_docto = self.jdc_id.sii_document_class_id.id
        self.sequence_id = self.jdc_id.sequence_id.id

    @api.onchange('cod_docto')
    def get_disp(self):
        if not self.id_peticion:
            return
        ICPSudo = self.env['ir.config_parameter'].sudo()
        url = ICPSudo.get_param('dte.url_apicaf')
        token = ICPSudo.get_param('dte.token_apicaf')
        params = {
                'token': token,
                'etapa': self.etapa,
                'id_peticion': self.id_peticion,
                'cod_docto': self.cod_docto.sii_code,
                }
        resp = pool.request('POST', url, body=json.dumps(params))
        if resp.status != 200:
            _logger.warning("Error en conexión con api apicaf %s" % resp.data)
            message = ''
            if resp.status == 403:
                data = json.loads(resp.data.decode('ISO-8859-1'))
                message = data['message']
            else:
                message = str(resp.data)
            self.env['bus.bus'].sendone((
                self._cr.dbname, 'dte.caf.apicaf', self.env.user.partner_id.id),
                {
                    'title': "Error en conexión con apicaf",
                    'message': message,
                    'url': {'name': 'ir a apicaf.cl', 'uri': 'https://apicaf.cl'},
                    'type': 'dte_notif',
                })
            return
        data = json.loads(resp.data.decode('ISO-8859-1'))
        self.etapa = data['etapa']
        params = {
                'token': token,
                'etapa': self.etapa,
                'id_peticion': self.id_peticion
                }
        resp = pool.request('POST', url, body=json.dumps(params))
        if resp.status != 200:
            _logger.warning("Error en conexión con api apicaf %s" % resp.data)
            message = ''
            if resp.status == 403:
                data = json.loads(resp.data.decode('ISO-8859-1'))
                message = data['message']
            else:
                message = str(resp.data)
            self.env['bus.bus'].sendone((
                self._cr.dbname, 'dte.caf.apicaf', self.env.user.partner_id.id),
                {
                    'title': "Error en conexión con apicaf",
                    'message': message,
                    'url': {'name': 'ir a apicaf.cl', 'uri': 'https://apicaf.cl'},
                    'type': 'dte_notif',
                })
            return
        data = json.loads(resp.data.decode('ISO-8859-1'))
        max_autor = int(data['max_autor'])
        self.folios_disp = data['folios_disp']
        self.max_autor = max_autor
        self.cant_doctos = max_autor if max_autor >= 0 else 1
        self.etapa = data['etapa']

    @api.multi
    def obtener_caf(self):
        ICPSudo = self.env['ir.config_parameter'].sudo()
        url = ICPSudo.get_param('dte.url_apicaf')
        token = ICPSudo.get_param('dte.token_apicaf')
        resp = pool.request('POST', url, body=json.dumps({
                'token': token,
                'etapa': self.etapa,
                'id_peticion': self.id_peticion,
                'cant_doctos': self.cant_doctos
                }
            ))
        if resp.status != 200:
            _logger.warning("Error en conexión con api apicaf %s" % resp.data)
            message = ''
            if resp.status == 403:
                data = json.loads(resp.data.decode('ISO-8859-1'))
                message = data['message']
            else:
                message = str(resp.data)
            self.env['bus.bus'].sendone((
                self._cr.dbname, 'dte.caf.apicaf', self.env.user.partner_id.id),
                {
                    'title': "Error en conexión con apicaf",
                    'message': message,
                    'url': {
                                'name': 'ir a apicaf.cl',
                                'uri': 'https://apicaf.cl'
                           },
                    'type': 'dte_notif',
            })
            return
        data = json.loads(resp.data.decode('ISO-8859-1'))
        self.etapa = data['etapa'] # obtener
        resp = pool.request('POST', url, body=json.dumps({
                'token': token,
                'etapa': self.etapa,
                'id_peticion': self.id_peticion,
                }
            ))
        if resp.status != 200:
            _logger.warning("Error en conexión con api apicaf %s" % resp.data)
            message = ''
            if resp.status == 403:
                data = json.loads(resp.data.decode('ISO-8859-1'))
                message = data['message']
            else:
                message = str(resp.data)
            self.env['bus.bus'].sendone((
                self._cr.dbname, 'dte.caf.apicaf', self.env.user.partner_id.id),
                {
                    'title': "Error en conexión con apicaf",
                    'message': message,
                    'url': {
                                'name': 'ir a apicaf.cl',
                                'uri': 'https://apicaf.cl'
                           },
                    'type': 'dte_notif',
            })
            return
        data = json.loads(resp.data.decode('ISO-8859-1'))
        self.etapa = data['etapa']#archivo
        resp = pool.request('POST', url, body=json.dumps({
                'token': token,
                'etapa': self.etapa,
                'id_peticion': self.id_peticion,
                }
            ))
        if resp.status != 200:
            _logger.warning("Error en conexión con api apicaf %s" % resp.data)
            message = ''
            if resp.status == 403:
                data = json.loads(resp.data.decode('ISO-8859-1'))
                message = data['message']
            else:
                message = str(resp.data)
            self.env['bus.bus'].sendone((
                self._cr.dbname, 'dte.caf.apicaf', self.env.user.partner_id.id),
                {
                    'title': "Error en conexión con apicaf",
                    'message': message,
                    'url': {
                                'name': 'ir a apicaf.cl',
                                'uri': 'https://apicaf.cl'
                           },
                    'type': 'dte_notif',
            })
            return
        data = json.loads(resp.data.decode('ISO-8859-1'))
        caf = self.env['dte.caf'].create({
                'caf_file': data['archivo_caf'],
                'sequence_id': self.sequence_id.id,
                'company_id': self.company_id.id,
            })
        caf._compute_data()
