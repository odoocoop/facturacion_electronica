# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _
from odoo.exceptions import UserError
from .account_invoice import server_url
from lxml import etree
import collections
import logging
_logger = logging.getLogger(__name__)
try:
    import urllib3
    urllib3.disable_warnings()
    pool = urllib3.PoolManager()
except:
    _logger.warning("no se ha cargado urllib3")

try:
    from suds.client import Client
except:
    _logger.warning("no se ha cargado suds")
try:
    import xmltodict
except ImportError:
    _logger.warning('Cannot import xmltodict library')

connection_status = {
    '0': 'Upload OK',
    '1': 'El Sender no tiene permiso para enviar',
    '2': 'Error en tamaño del archivo (muy grande o muy chico)',
    '3': 'Archivo cortado (tamaño <> al parámetro size)',
    '5': 'No está autenticado',
    '6': 'Empresa no autorizada a enviar archivos',
    '7': 'Esquema Invalido',
    '8': 'Firma del Documento',
    '9': 'Sistema Bloqueado',
    'Otro': 'Error Interno.',
}

status_dte = [
    ('no_revisado', 'No Revisado'),
    ('0', 'Conforme'),
    ('1', 'Error de Schema'),
    ('2', 'Error de Firma'),
    ('3', 'RUT Receptor No Corresponde'),
    ('90', 'Archivo Repetido'),
    ('91', 'Archivo Ilegible'),
    ('99', 'Envio Rechazado - Otros')
]


class SIIXMLEnvio(models.Model):
    _name = 'sii.xml.envio'
    _description = 'XML de envío DTE'

    name = fields.Char(
            string='Nombre de envío',
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    xml_envio = fields.Text(
            string='XML Envío',
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    state = fields.Selection(
            [
                    ('draft', 'Borrador'),
                    ('NoEnviado', 'No Enviado'),
                    ('Enviado', 'Enviado'),
                    ('Aceptado', 'Aceptado'),
                    ('Rechazado', 'Rechazado'),
            ],
            default='draft',
        )
    company_id = fields.Many2one(
            'res.company',
            string='Compañia',
            required=True,
            default=lambda self: self.env.user.company_id.id,
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    sii_xml_response = fields.Text(
            string='SII XML Response',
            copy=False,
            readonly=True,
            states={'NoEnviado': [('readonly', False)]},
        )
    sii_send_ident = fields.Text(
            string='SII Send Identification',
            copy=False,
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    sii_receipt = fields.Text(
            string='SII Mensaje de recepción',
            copy=False,
            readonly=False,
            states={'Aceptado': [('readonly', False)],
                    'Rechazado': [('readonly', False)]},
        )
    user_id = fields.Many2one(
            'res.users',
            string="Usuario",
            helps='Usuario que envía el XML',
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    invoice_ids = fields.One2many(
            'account.invoice',
            'sii_xml_request',
            string="Facturas",
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    attachment_id = fields.Many2one(
            'ir.attachment',
            string="XML Recepción",
            readonly=True,
        )
    email_respuesta = fields.Text(
            string="Email SII",
            readonly=True,
        )
    email_estado = fields.Selection(
            status_dte,
            string="Respuesta Envío",
            readonly=True,
        )
    email_glosa = fields.Text(
            string="Glosa Recepción",
            readonly=True,
        )

    @api.multi
    def name_get(self):
        result = []
        for r in self:
            name = r.name + " Código Envío: %s" % r.sii_send_ident if r.sii_send_ident else r.name
            result.append((r.id, name))
        return result

    def get_seed(self, company_id):
        try:
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
        except:
            pass
        url = server_url[company_id.dte_service_provider] + 'CrSeed.jws?WSDL'
        _server = Client(url)
        try:
            resp = _server.service.getSeed().replace('<?xml version="1.0" encoding="UTF-8"?>','')
        except Exception as e:
            msg = "Error al obtener Semilla"
            _logger.warning("%s: %s" % (msg, str(e)))
            if e.args[0][0] == 503:
                raise UserError('%s: Conexión al SII caída/rechazada o el SII está temporalmente fuera de línea, reintente la acción' % (msg))
            raise UserError(("%s: %s" % (msg, str(e))))
        root = etree.fromstring(resp)
        semilla = root[0][0].text
        return semilla

    def sign_seed(self, user_id, company_id):
        seed = self.get_seed(company_id)
        xml_seed = u'<getToken><Semilla>%s</Semilla></getToken>' \
            % (seed)
        signature_id = user_id.get_digital_signature(company_id)
        return signature_id.firmar(xml_seed, type="token")

    def _get_token(self, seed_file, company_id):
        url = server_url[company_id.dte_service_provider] + 'GetTokenFromSeed.jws?WSDL'
        _server = Client(url)
        tree = etree.fromstring(seed_file)
        ss = etree.tostring(tree, pretty_print=True, encoding='iso-8859-1').decode()
        try:
            resp = _server.service.getToken(ss).replace('<?xml version="1.0" encoding="UTF-8"?>','')
        except Exception as e:
            msg = "Error al obtener Token"
            _logger.warning("%s: %s" % (msg, str(e)))
            if e.args[0][0] == 503:
                raise UserError('%s: Conexión al SII caída/rechazada o el SII está temporalmente fuera de línea, reintente la acción' % (msg))
            raise UserError(("%s: %s" % (msg, str(e))))
        respuesta = etree.fromstring(resp)
        token = respuesta[0][0].text
        return token

    def get_token(self, user_id, company_id):
        seed_firmado = self.sign_seed(user_id, company_id)
        return self._get_token(seed_firmado, company_id)

    def init_params(self):
        params = collections.OrderedDict()
        signature_id = self.user_id.get_digital_signature(self.company_id)
        if not signature_id:
            raise UserError(_('''There is no Signer Person with an \
        authorized signature for you in the system. Please make sure that \
        'user_signature_key' module has been installed and enable a digital \
        signature, for you or make the signer to authorize you to use his \
        signature.'''))
        params['rutSender'] = signature_id.subject_serial_number[:8]
        params['dvSender'] = signature_id.subject_serial_number[-1]
        params['rutCompany'] = self.company_id.vat[2:-1]
        params['dvCompany'] = self.company_id.vat[-1]
        params['archivo'] = (self.name, self.xml_envio, "text/xml")
        return params

    def procesar_recepcion(self, retorno, respuesta_dict):
        if respuesta_dict['RECEPCIONDTE']['STATUS'] != '0':
            _logger.warning(connection_status[respuesta_dict['RECEPCIONDTE']['STATUS']])
            if respuesta_dict['RECEPCIONDTE']['STATUS'] in ['7']:
                retorno.update({
                    'state': 'Rechazado'
                    })
        else:
            retorno.update({
                            'state': 'Enviado',
                            'sii_send_ident': respuesta_dict['RECEPCIONDTE']['TRACKID']
                            })
        return retorno

    def send_xml(self, post='/cgi_dte/UPL/DTEUpload'):
        if self.state not in ['draft', 'NoEnviado', 'Rechazado']:
            return
        retorno = {'state': 'NoEnviado'}
        if not self.company_id.dte_service_provider:
            raise UserError(_("Not Service provider selected!"))
        token = self.get_token(self.user_id, self.company_id)
        url = 'https://palena.sii.cl'
        if self.company_id.dte_service_provider == 'SIICERT':
            url = 'https://maullin.sii.cl'
        headers = {
            'Accept': 'image/gif, image/x-xbitmap, image/jpeg, image/pjpeg, application/vnd.ms-powerpoint, application/ms-excel, application/msword, */*',
            'Accept-Language': 'es-cl',
            'Accept-Encoding': 'gzip, deflate',
            'User-Agent': 'Mozilla/4.0 (compatible; PROG 1.0; Windows NT 5.0; YComp 5.0.2.4)',
            'Referer': '{}'.format(self.company_id.website),
            'Connection': 'Keep-Alive',
            'Cache-Control': 'no-cache',
            'Cookie': 'TOKEN={}'.format(token),
        }
        params = self.init_params()
        multi = urllib3.filepost.encode_multipart_formdata(params)
        headers.update({'Content-Length': '{}'.format(len(multi[0]))})
        try:
            response = pool.request_encode_body('POST', url+post, params, headers)
            retorno.update({ 'sii_xml_response': response.data })
            if response.status != 200 or not response.data or response.data == '':
                return retorno
            respuesta_dict = xmltodict.parse(response.data)
            retorno = self.procesar_recepcion(retorno, respuesta_dict)
            self.write(retorno)
        except Exception as e:
            msg = "Error al subir DTE"
            _logger.warning("%s: %s" % (msg, str(e)))
            if e.args[0][0] == 503:
                raise UserError('%s: Conexión al SII caída/rechazada o el SII está temporalmente fuera de línea, reintente la acción' % (msg))
            raise UserError(("%s: %s" % (msg, str(e))))
        return retorno

    @api.multi
    def do_send_xml(self):
        return self.send_xml()

    def get_send_status(self, user_id=False):
        if not self.sii_send_ident:
            self.state = "NoEnviado"
            return
        user_id = user_id or self.user_id
        token = self.get_token(user_id, self.company_id)
        url = server_url[self.company_id.dte_service_provider] + 'QueryEstUp.jws?WSDL'
        _server = Client(url)
        rut = self.invoice_ids.format_vat( self.company_id.vat, con_cero=True)
        try:
            respuesta = _server.service.getEstUp(
                    rut[:8].replace('-', ''),
                    str(rut[-1]),
                    self.sii_send_ident,
                    token,
                )
        except Exception as e:
            msg = "Error al obtener Estado Envío DTE"
            _logger.warning("%s: %s" % (msg, str(e)))
            if e.args[0][0] == 503:
                raise UserError('%s: Conexión al SII caída/rechazada o el SII está temporalmente fuera de línea, reintente la acción' % (msg))
            raise UserError(("%s: %s" % (msg, str(e))))
        result = {"sii_receipt" : respuesta}
        resp = xmltodict.parse(respuesta)
        result.update({"state": "Enviado"})
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "-11":
            if resp['SII:RESPUESTA']['SII:RESP_HDR']['ERR_CODE'] == "2":
                status = {'warning':{'title':_('Estado -11'), 'message': _("Estado -11: Espere a que sea aceptado por el SII, intente en 5s más")}}
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] in ["EPR", "LOK"]:
            result.update({"state": "Aceptado"})
            if resp['SII:RESPUESTA'].get('SII:RESP_BODY') and resp['SII:RESPUESTA']['SII:RESP_BODY']['RECHAZADOS'] == "1":
                result.update({ "state": "Rechazado" })
        elif resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] in ["RCT", "RFR", "LRH", "RCH", "RSC", "LRF", "LNC", "LRS"]:
            result.update({"state": "Rechazado"})
            _logger.warning(resp)
        self.write(result)
