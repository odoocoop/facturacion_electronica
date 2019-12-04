# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _
from lxml import etree
import collections
import logging
_logger = logging.getLogger(__name__)
try:
    from suds.client import Client
except ImportError:
    _logger.warning('Cannot import suds')

server_url = {
    'SIICERT': 'https://maullin.sii.cl/DTEWS/',
    'SII': 'https://palena.sii.cl/DTEWS/',
}

class SIIXMLEnvio(models.Model):
    _inherit = 'sii.xml.envio'

    def init_params(self, ):
        signature_id = self.user_id.get_digital_signature(self.company_id)
        if not signature_id:
            raise UserError(_('''There is no Signer Person with an \
        authorized signature for you in the system. Please make sure that \
        'user_signature_key' module has been installed and enable a digital \
        signature, for you or make the signer to authorize you to use his \
        signature.'''))
        params = collections.OrderedDict()
        if "AEC_" in self.name:
            params['emailNotif'] = self.env.user.email
        else:
            params['rutSender'] = signature_id.subject_serial_number[:8]
            params['dvSender'] = signature_id.subject_serial_number[-1]
        params['rutCompany'] = self.company_id.vat[2:-1]
        params['dvCompany'] = self.company_id.vat[-1]
        params['archivo'] = (self.name, self.xml_envio, "text/xml")
        return params

    def procesar_recepcion(self, retorno, respuesta_dict):
        if respuesta_dict.get('RECEPCIONAEC') and respuesta_dict['RECEPCIONAEC']['STATUS'] != '0':
            _logger.warning(connection_status[respuesta_dict['RECEPCIONDTE']['STATUS']])
        elif respuesta_dict.get('RECEPCIONAEC'):
            retorno.update({
                        'state': 'Enviado',
                        'sii_send_ident': respuesta_dict['RECEPCIONAEC']['TRACKID']
            })
        else:
            super(SIIXMLEnvio, self).procesar_recepcion(retorno, respuesta_dict)
        return retorno

    def get_cesion_send_status(self):
        token = self.get_token(self.env.user, self.company_id)
        url = server_url[self.company_id.dte_service_provider] + 'services/wsRPETCConsulta?wsdl'
        _server = Client(url)
        rut = self.env['account.invoice'].format_vat(self.company_id.vat, con_cero=True)
        respuesta = _server.service.getEstEnvio(
            token,
            self.sii_send_ident,
        )
        self.sii_receipt = respuesta
        resp = etree.XML(respuesta.replace(
                '<?xml version="1.0" encoding="UTF-8"?>', '')\
            .replace('SII:', '')\
            .replace(' xmlns="http://www.sii.cl/XMLSchema"', ''))
        status = False
        sii_result = False
        if resp.find('RESP_HDR/ESTADO').text == "-11":
            if resp.find('RESP_HDR/ERR_CODE').text == "2":
                status =  {'warning':{'title':_('Estado -11'), 'message': _("Estado -11: Espere a que sea aceptado por el SII, intente en 5s más")}}
            else:
                status =  {'warning':{'title':_('Estado -11'), 'message': _("Estado -11: error Algo a salido mal, revisar carátula")}}
        if resp.find('RESP_HDR/ESTADO').text == '0':
            if resp.find('RESP_BODY/ESTADO_ENVIO').text in ["EPR", "EOK"]:
                sii_result = "Procesado"
                self.state = "Aceptado"
            elif resp.find('RESP_HDR/ESTADO').text in ["RCT", 'RDC'] or \
                resp.find('RESP_BODY/ESTADO_ENVIO').text in ["RDC"]:
                sii_result = "Rechazado"
                self.state = "Rechazado"
                status = {'warning':{'title':_('Error RCT'), 'message': _(resp.find('RESP_BODY/DESC_ESTADO').text)}}
        else:
            sii_result = "Rechazado"
            _logger.warning("rechazado %s" %resp)
            status = {'warning':{'title':_('Error RCT'), 'message': _(resp.find('RESP_BODY/DESC_ESTADO').text)}}
            self.state = "Rechazado"
        return status
