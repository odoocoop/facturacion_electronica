# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _
from lxml import etree
import collections
import logging
_logger = logging.getLogger(__name__)
try:
    from facturacion_electronica import facturacion_electronica as fe
except Exception as e:
    _logger.warning('No se puede importar Facturación Electrónica %s' %str(e))


class SIIXMLEnvio(models.Model):
    _inherit = 'sii.xml.envio'

    def get_cesion_send_status(self):
        datos = self._get_datos_empresa(self.company_id)
        datos.update({
            'codigo_envio':self.sii_send_ident,
            'cesion': True
        })
        res = fe.consulta_estado_dte(datos)
        self.write({
            'state': res['status'],
            'sii_xml_response': res['xml_resp'],
        })
