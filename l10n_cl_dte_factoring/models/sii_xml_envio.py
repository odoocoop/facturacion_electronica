# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _
import collections
import logging
_logger = logging.getLogger(__name__)

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
        _logger.warning(respuesta_dict)
        if respuesta_dict.get('RECEPCIONAEC') and respuesta_dict['RECEPCIONAEC']['STATUS'] != '0':
            _logger.warning(connection_status[respuesta_dict['RECEPCIONDTE']['STATUS']])
        elif respuesta_dict.get('RECEPCIONAEC'):
            retorno.update({'state': 'Enviado','sii_send_ident': respuesta_dict['RECEPCIONAEC']['TRACKID']})
        else:
            super(SIIXMLEnvio, self).procesar_recepcion(retorno, respuesta_dict)
        return retorno
