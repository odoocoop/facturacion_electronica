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


class APICAFDocs(models.TransientModel):
    _name = "dte.caf.apicaf.docs"
    _description = "Líneas de archivos disponibles para remitir folios"

    def get_name(self):
        for r in self:
            name = "%s, %s, %s-%s" % (r.fecha,
                                      r.cantidad,
                                      r.inicial,
                                      r.final)
            r.name = name

    apicaf_id = fields.Many2one(
        'dte.caf.apicaf'
    )
    name = fields.Char(compute='get_name')
    fecha = fields.Date(
            string="Fecha de Emisión CAF",
        )
    cantidad = fields.Integer(
            string="Cantidad Folios del CAF",
        )
    inicial = fields.Integer(
            string="Folio Inicial",
        )
    final = fields.Integer(
            string="Folio Final",
        )
    form_name = fields.Char(
            string="Form Name",
            invisible=True
        )
    cod_docto = fields.Many2one(
            'sii.document_class',
            string="Código Documento",
        )
    selected = fields.Boolean(
            string="Seleccionar"
        )
    sequence = fields.Integer(
            string="secuencia"
        )

    @api.onchange('selected')
    def selected_caf(self):
        if self.selected and self.sequence != 1:
            self.sequence = -1
        elif not self.selected and self.sequence == 1:
            self.sequence = 0


class APICAF(models.TransientModel):
    _name = "dte.caf.apicaf"
    _description = "Asistente para la administración de CAF en el SII"

    @api.onchange('firma', 'operacion')
    def conectar_api(self):
        if not self.firma:
            return
        ICPSudo = self.env['ir.config_parameter'].sudo()
        url = ICPSudo.get_param('dte.url_apicaf')
        token = ICPSudo.get_param('dte.token_apicaf')
        etapa = 'conectar'
        if self.operacion == 'reobtener':
            etapa = 'reob_conectar'
        elif self.operacion == 'anular':
            etapa = 'an_conectar'
        params = {
            'firma_electronica': {
                'priv_key': self.firma.priv_key,
                'cert': self.firma.cert,
                'init_signature': False,
                'subject_serial_number': self.firma.subject_serial_number,
            },
            'token': token,
            'rut': self.company_id.document_number,
            'etapa': etapa,
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
        if self.operacion == 'obtener':
            self.etapa = data['etapa']
        elif self.operacion == 'reobtener':
            self.reob_etapa = data['etapa']
        elif self.operacion == 'anular':
            self.an_etapa = data['etapa']
        self.id_peticion = data['id_peticion']
        '''@TODO verificación de folios autorizados en el SII'''
        self.listar()
        if self.cod_docto:
            self.get_disp()

    @api.depends('api_folios_disp', 'api_max_autor')
    def _details(self):
        self.folios_disp = self.api_folios_disp
        self.max_autor = self.api_max_autor

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
        )
    reob_etapa = fields.Selection(
            [
                ('reob_conectar', 'Conectar al SII'),
                ('reob_listar', 'Listar documentos'),
                ('reob_disponibles', 'CAFs disponibles para el Tipo de Documento'),
                ('reob_confirmar', 'Confirmar Folios'),
                ('reob_obtener', 'Obtener Folios'),
                ('reob_archivo', 'Obtener archivo'),
            ],
            default='reob_conectar',
            string='Etapa Reobtención',
        )
    an_etapa = fields.Selection(
            [
                ('an_conectar', 'Conectar al SII'),
                ('an_listar', 'Listar documentos'),
                ('an_disponibles', 'CAFs disponibles para el Tipo de Documento'),
                ('an_confirmar', 'Confirmar Folios'),
                ('an_motivo', 'Motivo'),
                ('an_finalizar', 'Anulación'),
            ],
            default='an_conectar',
            string='Etapa Anulación',
            required=True,
        )
    operacion = fields.Selection(
            [
                ('obtener', 'Solicitar Folios'),
                ('reobtener', 'Reobtener Folios'),
                ('anular', 'Anular Folios'),
            ],
            string="Opción a realizar",
            default='obtener',
        )
    folios_disp = fields.Integer(
            string="Folios Emitidos SIN USAR",
            compute='_details',
            help='Debe Revisar si ha tenido algún salto de folios, si piensa que ya no debiera tener folios disponibles o puede que no se hayan enviado al SII o estén recahzados, por loque debe revisar el estado de facturas lo antes posible',
        )
    api_folios_disp = fields.Integer(
            string="Folios Emitidos SIN USAR",
            default=0,
        )
    max_autor = fields.Integer(
            string="Cantidad Máxima Autorizada para el Documento",
            compute='_details'
        )
    api_max_autor = fields.Integer(
            string="Cantidad Máxima Autorizada para el Documento",
            default=0,
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
    lineas_disponibles = fields.One2many(
            'dte.caf.apicaf.docs',
            'apicaf_id',
            string="CAF disponibles",
        )
    form_name = fields.Char(
            string="Form Name",
        )
    folio_ini = fields.Integer(
            string="Folio inicial Anular",
        )
    folio_fin = fields.Integer(
            string="Folio Final Anular",
        )
    api_folio_ini = fields.Integer(
            string="Folio inicial CAF",
        )
    api_folio_fin = fields.Integer(
            string="Folio Final CAF",
        )
    motivo = fields.Char(
        string="Motivo de anulación",
    )

    @api.onchange('lineas_disponibles')
    def selected_caf(self):
        caf = False
        for r in self.lineas_disponibles:
            if r.sequence != -1:
                r.selected = False
                r.sequence = 0
            else:
                r.sequence = 1
            if r.selected:
                caf = True
        if not caf or not self.id_peticion or self.operacion != 'anular':
            return
        self.an_etapa = 'an_confirmar'
        return self.obtener_caf()

    @api.onchange('jdc_id')
    def _set_cod_docto(self):
        if not self.documentos:
            return
        self.cod_docto = self.jdc_id.sii_document_class_id.id
        self.sequence_id = self.jdc_id.sequence_id.id

    def listar(self):
        if not self.id_peticion:
            return
        self.etapa = 'listar'
        etapa = 'listar'
        if self.operacion == 'reobtener':
            etapa = 'reob_' + etapa
            self.reob_etapa = etapa
        elif self.operacion == 'anular':
            etapa = 'an_' + etapa
            self.an_etapa = etapa
        ICPSudo = self.env['ir.config_parameter'].sudo()
        url = ICPSudo.get_param('dte.url_apicaf')
        token = ICPSudo.get_param('dte.token_apicaf')
        params = {
                'token': token,
                'etapa': etapa,
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
                _logger.warning(message)
            else:
                message = str(resp.data)
            self.env['bus.bus'].sendone((
                self._cr.dbname, 'dte.caf.apicaf',
                self.env.user.partner_id.id),
                {
                    'title': "Error en conexión con apicaf",
                    'message': message,
                    'url': {'name': 'ir a apicaf.cl',
                            'uri': 'https://apicaf.cl'},
                    'type': 'dte_notif',
                })
            return
        data = json.loads(resp.data.decode('ISO-8859-1'))

    @api.onchange('cod_docto')
    def get_disp(self):
        if not self.id_peticion:
            return
        ICPSudo = self.env['ir.config_parameter'].sudo()
        url = ICPSudo.get_param('dte.url_apicaf')
        token = ICPSudo.get_param('dte.token_apicaf')
        self.etapa = 'disponibles'
        etapa = 'disponibles'
        if self.operacion == 'reobtener':
            etapa = 'reob_' + etapa
            self.reob_etapa = etapa
        elif self.operacion == 'anular':
            etapa = 'an_' + etapa
            self.an_etapa = etapa
        params = {
                'token': token,
                'etapa': etapa,
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
                _logger.warning(message)
            else:
                message = str(resp.data)
            self.env['bus.bus'].sendone((
                self._cr.dbname, 'dte.caf.apicaf',
                self.env.user.partner_id.id),
                {
                    'title': "Error en conexión con apicaf",
                    'message': message,
                    'url': {'name': 'ir a apicaf.cl',
                            'uri': 'https://apicaf.cl'},
                    'type': 'dte_notif',
                })
            return
        data = json.loads(resp.data.decode('ISO-8859-1'))
        if self.operacion == 'obtener':
            max_autor = int(data.get('max_autor', 0))
            self.api_folios_disp = data.get('folios_disp', 0)
            self.api_max_autor = max_autor
            self.cant_doctos = max_autor if max_autor >= 0 else 1
            self.etapa = data['etapa']
        elif self.operacion in ['anular', 'reobtener']:
            if self.operacion == 'anular':
                self.an_etapa = data['etapa']
            else:
                self.reob_etapa = data['etapa']
            folios = []
            for f in data.get('folios', []):
                folios.append(
                    (0, 0, dict(
                        fecha="%s-%s-%s" % (f['ano'], f['mes'], f['dia']),
                        cantidad=f['cantidad'],
                        inicial=f['folio_inicial'],
                        final=f['folio_final'],
                        form_name=f['form_name'],
                        cod_docto=self.cod_docto.id,
                       )
                    )
                )
            self.lineas_disponibles = folios

    @api.multi
    def obtener_caf(self):
        if not self.id_peticion:
            return
        ICPSudo = self.env['ir.config_parameter'].sudo()
        url = ICPSudo.get_param('dte.url_apicaf')
        token = ICPSudo.get_param('dte.token_apicaf')
        peticion = {
                'token': token,
                'id_peticion': self.id_peticion,
        }
        etapa = 'confirmar'
        if self.operacion == 'obtener':
            peticion.update(
                    id_peticion=self.id_peticion,
                    cant_doctos=self.cant_doctos,
                )
            if self.api_max_autor == 0:
                raise UserError("No tiene folios disponibles")
            if(self.api_max_autor > -1 and self.cant_doctos > self.api_max_autor)\
                    or self.cant_doctos < 1:
                raise UserError("Debe ingresar una cantidad mayor a 0 y hasta la cantidad máxima autorizada")
        elif self.operacion in ['anular', 'reobtener']:
            etapa = 'reob_confirmar'
            if self.operacion == 'anular':
                etapa = 'an_confirmar'
            caf = False
            for r in self.lineas_disponibles:
                if r.selected:
                    caf = r
            if not caf:
                raise UserError("Debe seleccionar Uno")
            peticion.update(
                    form_name=caf.form_name
                )
        #   obtener
        peticion['etapa'] = etapa
        resp = pool.request('POST', url, body=json.dumps(peticion))
        if resp.status != 200:
            _logger.warning("Error en conexión con api apicaf %s" % resp.data)
            message = ''
            if resp.status == 403:
                data = json.loads(resp.data.decode('ISO-8859-1'))
                message = data['message']
                _logger.warning(message)
            else:
                message = str(resp.data)
            self.env['bus.bus'].sendone((
                self._cr.dbname, 'dte.caf.apicaf',
                self.env.user.partner_id.id),
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
        if self.operacion == 'obtener':
            self.etapa = data['etapa']
        elif self.operacion == 'reobtener':
            self.reob_etapa = data['etapa']
        elif self.operacion == 'anular':
            self.an_etapa = data['etapa']
            self.api_folio_ini = data['folio_ini']
            self.api_folio_fin = data['folio_fin']
            return
        return self.confirmar()

    @api.multi
    def confirmar(self):
        if not self.id_peticion:
            return
        ICPSudo = self.env['ir.config_parameter'].sudo()
        url = ICPSudo.get_param('dte.url_apicaf')
        token = ICPSudo.get_param('dte.token_apicaf')
        peticion = {
                'token': token,
                'id_peticion': self.id_peticion,
        }
        etapa = "obtener"
        if self.operacion == 'reobtener':
            etapa = "reob_obtener"
        elif self.operacion == 'anular':
            etapa = "an_motivo"
            peticion.update(
                folio_ini_a=self.folio_ini,
                folio_fin_a=self.folio_fin,
                motivo=self.motivo
            )
        peticion['etapa'] = etapa
        resp = pool.request('POST', url, body=json.dumps(peticion))
        if resp.status != 200:
            _logger.warning("Error en conexión con api apicaf %s" % resp.data)
            message = ''
            if resp.status == 403:
                data = json.loads(resp.data.decode('ISO-8859-1'))
                message = data['message']
                _logger.warning(message)
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

        #  archivo

        data = json.loads(resp.data.decode('ISO-8859-1'))
        nombre = data.get('nombre')
        peticion2 = {
                'token': token,
                'id_peticion': self.id_peticion,
                'etapa': data['etapa'],
            }
        if self.operacion == 'obtener':
            self.etapa = data['etapa']
        elif self.operacion == 'reobtener':
            self.reob_etapa = data['etapa']
        elif self.operacion == 'anular':
            self.an_etapa = data['etapa']
            return
        resp = pool.request('POST', url, body=json.dumps(peticion2))
        if resp.status != 200:
            _logger.warning("Error en conexión con api apicaf %s" % resp.data)
            message = ''
            if resp.status == 403:
                data = json.loads(resp.data.decode('ISO-8859-1'))
                message = data['message']
                _logger.warning(message)
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
                'filename': nombre,
            })
        caf._compute_data()
