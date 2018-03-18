# -*- coding: utf-8 -*-
from openerp import fields, models, api, _
from openerp.exceptions import UserError
from datetime import datetime, timedelta, date
import os
import logging
from lxml import etree
from lxml.etree import Element, SubElement
from openerp import SUPERUSER_ID

import pytz
import collections

_logger = logging.getLogger(__name__)

try:
    import xmltodict
except ImportError:
    _logger.warning('Cannot import xmltodict library')

try:
    import dicttoxml
except ImportError:
    _logger.warning('Cannot import dicttoxml library')

try:
    import base64
except ImportError:
    _logger.warning('Cannot import base64 library')

try:
    from suds.client import Client
except ImportError:
    _logger.warning('Cannot import suds')

server_url = {
    'SIIHOMO':'https://maullin.sii.cl/DTEWS/',
    'SII':'https://palena.sii.cl/DTEWS/',
}

BC = '''-----BEGIN CERTIFICATE-----\n'''
EC = '''\n-----END CERTIFICATE-----\n'''


class CesionDTE(models.Model):
    _inherit = "account.invoice"

    cesion_number = fields.Integer(
        copy=False,
        string='Cesion Number',
        help='',
        default=1,
    )
    declaracion_jurada = fields.Text(
        copy=False,
        string='Declaración Jurada',
        help='',
    )
    cesionario_id = fields.Many2one(
        'res.partner',
        string="Cesionario",
        help='',
    )
    sii_cesion_result = fields.Selection([
        ('', 'n/a'),
        ('NoEnviado', 'No Enviado'),
        ('EnCola','En cola de envío'),
        ('Enviado', 'Enviado'),
        ('Aceptado', 'Aceptado'),
        ('Rechazado', 'Rechazado'),
        ('Reparo', 'Reparo'),
        ('Procesado', 'Procesado'),
        ('Cedido', 'Cedido'),
        ('Reenviar', 'Reenviar'),
        ('Anulado', 'Anulado')],
        string='Resultado Cesion',
        copy=False,
        help="SII request result",
    )
    sii_cesion_request = fields.Text(
        string='SII XML Request',
        copy=False)
    sii_cesion_receipt = fields.Text(
        string='SII XML Reception',
        copy=False)
    sii_cesion_message = fields.Text(
        string='SII Message',
        copy=False,
    )
    sii_xml_cesion_response = fields.Text(
        string='SII XML Response',
        copy=False)
    sii_cesion_send_ident = fields.Text(
        string='SII Send Identification',
        copy=False)
    imagen_ar_ids = fields.One2many(
        'account.invoice.imagen_ar',
        'invoice_id',
        string="Imagenes de acuse de recibo",
    )

    @api.onchange('cesionario_id')
    def set_declaracion(self):
        if self.cesionario_id:
            declaracion_jurada = u'''Se declara bajo juramento que {0}, RUT {1} \
ha puesto a disposicion del cesionario {2}, RUT {3}, el o los documentos donde constan los recibos de las mercaderías entregadas o servicios prestados, \
entregados por parte del deudor de la factura {4}, RUT {5}, de acuerdo a lo establecido en la Ley No. 19.983'''.format(
                self.company_id.partner_id.name,
                self.format_vat(self.company_id.partner_id.vat),
                self.cesionario_id.name,
                self.format_vat(self.cesionario_id.vat),
                self.commercial_partner_id.name,
                self.format_vat(self.commercial_partner_id.vat),
            )
            self.declaracion_jurada = declaracion_jurada

    def _get_xsd_types(self):
        xsd_types = super(CesionDTE, self)._get_xsd_types()
        xsd_types.update({
            'aec': 'AEC_v10.xsd',
            'dte_cedido': 'DTECedido_v10.xsd',
            'cesion': 'Cesion_v10.xsd',
        })
        return xsd_types

    def _get_xsd_file(self, validacion, path=False):
        if validacion in [ 'aec', 'dte_cedido', 'cesion']:
            path = os.path.dirname(os.path.realpath(__file__)).replace('/models','/static/xsd/')
        return super(CesionDTE, self)._get_xsd_file(validacion, path)

    def _caratula_aec(self, cesiones):
        xml = '''<DocumentoAEC ID="Doc1">
    <Caratula version="1.0">
    <RutCedente>{0}</RutCedente>
    <RutCesionario>{1}</RutCesionario>
    <NmbContacto>{2}</NmbContacto>
    <FonoContacto>{3}</FonoContacto>
    <MailContacto>{4}</MailContacto>
    <TmstFirmaEnvio>{5}</TmstFirmaEnvio>
</Caratula>
    <Cesiones>
        {6}
    </Cesiones>
</DocumentoAEC>
'''.format(
            self.format_vat(self.company_id.vat),
            self.format_vat(self.cesionario_id.commercial_partner_id.vat),
            self.responsable_envio.name,
            self.responsable_envio.phone or self.company_id.phone,
            self.responsable_envio.email or self.company_id.email,
            self.time_stamp(),
            cesiones,
        )
        return xml

    def crear_doc_cedido(self, id):
        xml = '''<DocumentoDTECedido ID="{0}">
{1}
<TmstFirma>{2}</TmstFirma>
</DocumentoDTECedido>
    '''.format(
            id,
            self.sii_xml_dte,
            self.time_stamp(),
        )
        return xml

    def crear_dte_cedido(self, doc):
        xml = '''<DTECedido xmlns="http://www.sii.cl/SiiDte" version="1.0">
{}
</DTECedido>'''.format(doc)
        return xml

    def _crear_info_trans_elec_aec(self, doc, id):
        xml = '''<DocumentoCesion ID="{0}">
{1}
</DocumentoCesion>
'''.format(
            id,
            doc,
        )
        return xml

    def _crear_info_cesion(self, doc):
        xml = '''<Cesion xmlns="http://www.sii.cl/SiiDte" version="1.0">
{1}
</Cesion>
'''.format(
            id,
            doc,
        )
        return xml

    def _crear_envio_aec(self, doc):
        xml = '''<?xml version="1.0" encoding="ISO-8859-1"?>
<AEC xmlns="http://www.sii.cl/SiiDte" \
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" \
xsi:schemaLocation="http://www.sii.cl/SiiDte AEC_v10.xsd" \
version="1.0">
    {}
</AEC>'''.format(doc)
        return xml

    def _append_sig(self, type, msg, message):
        tag = False
        if type in ['aec']:
            tag = 'AEC'
        if type in ['cesion']:
            tag = 'Cesion'
        if type in ['dte_cedido']:
            tag = 'DTECedido'
        if tag:
            xml = message.replace('</'+ tag + '>', msg.decode() + '</'+ tag + '>')
            return xml
        return super(CesionDTE, self)._append_sig(type, msg, message)

    @api.multi
    def get_cesion_xml_file(self):
        url_path = '/download/xml/cesion/%s' % (self.id)
        return {
            'type' : 'ir.actions.act_url',
            'url': url_path,
            'target': 'self',
        }

    def init_params(self, signature_d, company_id, file_name, envio_dte):
        params = collections.OrderedDict()
        if "AEC_" in file_name:
            params['emailNotif'] = self.responsable_envio.email
        else:
            params['rutSender'] = signature_d['subject_serial_number'][:8]
            params['dvSender'] = signature_d['subject_serial_number'][-1]
        params['rutCompany'] = company_id.vat[2:-1]
        params['dvCompany'] = company_id.vat[-1]
        params['archivo'] = (file_name,envio_dte, "text/xml")
        return params

    def procesar_recepcion(self, retorno, respuesta_dict ):
        if not 'RECEPCIONAEC' in respuesta_dict:
            return super(CesionDTE, self).procesar_recepcion(retorno, respuesta_dict)
        if respuesta_dict['RECEPCIONAEC']['STATUS'] != '0':
            _logger.warning(connection_status[respuesta_dict['RECEPCIONDTE']['STATUS']])
        else:
            retorno.update({'sii_result': 'Enviado','sii_send_ident':respuesta_dict['RECEPCIONAEC']['TRACKID']})
        return retorno

    def _id_dte(self):
        IdDoc = collections.OrderedDict()
        IdDoc['TipoDTE'] = self.sii_document_class_id.sii_code
        IdDoc['RUTEmisor'] = self.format_vat(self.company_id.vat)
        if not self.partner_id.commercial_partner_id.vat:
            raise UserError("Debe Ingresar RUT Receptor")
        IdDoc['RUTReceptor'] = self.format_vat(self.partner_id.commercial_partner_id.vat)
        IdDoc['Folio'] = self.get_folio()
        IdDoc['FchEmis'] = self.date_invoice
        IdDoc['MntTotal'] = self.currency_id.round(self.amount_total )
        return IdDoc

    def _cedente(self):
        Emisor = collections.OrderedDict()
        Emisor['RUT'] = self.format_vat(self.company_id.vat)
        Emisor['RazonSocial'] = self.company_id.partner_id.name
        Emisor['Direccion'] = self._acortar_str(self.company_id.street + ' ' +(self.company_id.street2 or ''), 70)
        Emisor['eMail'] = self.company_id.email or ''
        Emisor['RUTAutorizado'] = collections.OrderedDict()
        Emisor['RUTAutorizado']['RUT'] = self.format_vat(self.responsable_envio.vat)
        Emisor['RUTAutorizado']['Nombre'] = self.responsable_envio.name
        Emisor['DeclaracionJurada'] = self.declaracion_jurada
        return Emisor

    def _cesionario(self):
        Receptor = collections.OrderedDict()
        if not self.cesionario_id.commercial_partner_id.vat:
            raise UserError("Debe Ingresar RUT Cesionario")
        Receptor['RUT'] = self.format_vat(self.cesionario_id.commercial_partner_id.vat)
        Receptor['RazonSocial'] = self._acortar_str(self.cesionario_id.commercial_partner_id.name, 100)
        Receptor['Direccion'] = self._acortar_str((self.cesionario_id.street or self.cesionario_id.commercial_partner_id.street) + ' ' + (self.cesionario_id.street2 or self.cesionario_id.commercial_partner_id.street2 or ''),70)
        Receptor['eMail'] = self.cesionario_id.commercial_partner_id.email
        return Receptor

    def _cesion_dte(self, certp, priv_key):
        id = "DocCed_" + str(self.sii_document_number)
        xml = self.crear_doc_cedido(id)
        xml_cedido = self.crear_dte_cedido(xml)
        dte_cedido = self.sign_full_xml(
            xml_cedido,
            priv_key,
            certp,
            id,
            'dte_cedido',
        )
        return dte_cedido

    def _monto_cesion(self):
        return self.currency_id.round(self.amount_total)

    def _cesion(self, certp, priv_key):
        id = 'CesDoc1'
        data = collections.OrderedDict()
        data['SeqCesion'] = self.cesion_number
        data['IdDTE'] = self._id_dte()
        data['Cedente'] = self._cedente()
        data['Cesionario'] = self._cesionario()
        data['MontoCesion'] = self._monto_cesion()
        data['UltimoVencimiento'] = self.date_invoice
        data['TmstCesion'] = self.time_stamp()
        xml = dicttoxml.dicttoxml(
            {'item':data}, root=False, attr_type=False).decode() \
            .replace('<item>','').replace('</item>','')
        doc_cesion_xml =  self._crear_info_trans_elec_aec(xml, id)
        cesion_xml =  self._crear_info_cesion(doc_cesion_xml)
        root = etree.XML( cesion_xml )
        xml_formated = etree.tostring(root).decode()
        cesion = self.sign_full_xml(
            xml_formated,
            priv_key,
            certp,
            id,
            'cesion',
        )
        return cesion.replace('<?xml version="1.0" encoding="ISO-8859-1"?>\n','')

    def _crear_envio_cesion(self):
        dicttoxml.set_debug(False)
        try:
            signature_d = self.get_digital_signature(self.company_id)
        except:
            raise UserError(_('''There is no Signer Person with an \
        authorized signature for you in the system. Please make sure that \
        'user_signature_key' module has been installed and enable a digital \
        signature, for you or make the signer to authorize you to use his \
        signature.'''))
        certp = signature_d['cert'].replace(
            BC, '').replace(EC, '').replace('\n', '')
        file_name = "AEC_1"
        file_name += ".xml"
        DTECedido = self._cesion_dte(certp, signature_d['priv_key'])
        Cesion = self._cesion(certp, signature_d['priv_key'])
        caratulado  = self._caratula_aec(
            DTECedido + '\n' + Cesion,
        )
        envio_cesion_dte = self._crear_envio_aec(caratulado)
        envio_dte = self.sign_full_xml(
            envio_cesion_dte,
            signature_d['priv_key'],
            certp,
            'Doc1',
            'aec',
        )
        return envio_dte, file_name

    @api.multi
    def validate_cesion(self):
        for inv in self.with_context(lang='es_CL'):
            inv.sii_cesion_result = 'NoEnviado'
            inv.responsable_envio = self.env.user.id
            if inv.type in ['out_invoice' ] and inv.sii_document_class_id.sii_code in [ 33, 34]:
                if inv.journal_id.restore_mode:
                    inv.sii_result = 'Proceso'
                else:
                    inv._crear_envio_cesion()
                    inv.sii_cesion_result = 'EnCola'
                    self.env['sii.cola_envio'].create({
                                                'doc_ids':[inv.id],
                                                'model':'account.invoice',
                                                'user_id':self.env.user.id,
                                                'tipo_trabajo': 'cesion',
                                                })
    @api.multi
    def cesion_dte_send(self):
        envio_dte, file_name = self._crear_envio_cesion()
        result = self.send_xml_file(envio_dte, file_name, self.company_id, post='/cgi_rtc/RTC/RTCAnotEnvio.cgi')
        for inv in self:
            inv.write({
                'sii_xml_cesion_response':result['sii_xml_response'],
                'sii_cesion_send_ident':result['sii_send_ident'],
                'sii_cesion_result': result['sii_result'],
                'sii_cesion_request':envio_dte,
                })

    @api.multi
    def do_cesion_dte_send(self):
        ids = []
        for inv in self.with_context(lang='es_CL'):
            if inv.sii_cesion_result in ['','NoEnviado','Rechazado'] and inv.type in ['out_invoice' ] and inv.sii_document_class_id.sii_code in [ 33, 34]:
                if inv.sii_cesion_result in ['Rechazado']:
                    inv._crear_envio_cesion()
                inv.sii_cesion_result = 'EnCola'
                ids.append(inv.id)
        if ids:
            self.env['sii.cola_envio'].create({
                                    'doc_ids': ids,
                                    'model':'account.invoice',
                                    'user_id': self.env.user.id,
                                    'tipo_trabajo': 'cesion',
                                    })

    def _get_cesion_send_status(self, track_id, signature_d,token):
        url = server_url[self.company_id.dte_service_provider] + 'services/wsRPETCConsulta?wsdl'
        _server = Client(url)
        rut = self.format_vat(self.company_id.vat, con_cero=True)
        respuesta = _server.service.getEstEnvio(
            token,
            track_id,
        )
        self.sii_cesion_receipt = respuesta
        resp = xmltodict.parse(respuesta)
        status = False
        sii_result = False
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['SII:ESTADO'] == "-11":
            if resp['SII:RESPUESTA']['SII:RESP_HDR']['ERR_CODE'] == "2":
                status =  {'warning':{'title':_('Estado -11'), 'message': _("Estado -11: Espere a que sea aceptado por el SII, intente en 5s más")}}
            else:
                status =  {'warning':{'title':_('Estado -11'), 'message': _("Estado -11: error Algo a salido mal, revisar carátula")}}
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['SII:ESTADO'] == '0':
            if resp['SII:RESPUESTA']['SII:RESP_BODY']['ESTADO_ENVIO'] in ["EPR", "EOK"]:
                sii_result = "Procesado"
            elif resp['SII:RESPUESTA']['SII:RESP_HDR']['SII:ESTADO'] in ["RCT", 'RDC'] or \
                resp['SII:RESPUESTA']['SII:RESP_BODY']['ESTADO_ENVIO'] in ["RDC"]:
                sii_result = "Rechazado"
                status = {'warning':{'title':_('Error RCT'), 'message': _(resp['SII:RESPUESTA']['SII:RESP_BODY']['DESC_ESTADO'])}}
        else:
            sii_result = "Rechazado"
            _logger.warning("rechazado %s" %resp)
            status = {'warning':{'title':_('Error RCT'), 'message': _(resp['SII:RESPUESTA']['SII:RESP_BODY']['DESC_ESTADO'])}}
        if sii_result:
            self.sii_cesion_result = sii_result
        return status

    def _get_cesion_dte_status(self, signature_d, token):
        url = server_url[self.company_id.dte_service_provider] + 'services/wsRPETCConsulta?wsdl'
        _server = Client(url)
        rut = signature_d['subject_serial_number']
        respuesta = _server.service.getEstCesion(
            token,
            rut[:8],
            str(rut[-1]),
            str(self.sii_document_class_id.sii_code),
            str(self.sii_document_number),
        )
        self.sii_cesion_message = respuesta
        resp = xmltodict.parse(respuesta)
        sii_result = 'Procesado'
        status = False
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['SII:ESTADO'] in ['2', '-13']:
            status = {'warning':{'title':_("Error code: 2"), 'message': _(resp['SII:RESPUESTA']['SII:RESP_HDR']['SII:GLOSA'])}}
            sii_result = "Rechazado"
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['SII:ESTADO'] == "0":
            sii_result = "Cedido"
        elif resp['SII:RESPUESTA']['SII:RESP_HDR']['SII:ESTADO'] == "FAU":
            sii_result = "Rechazado"
        self.sii_cesion_result = sii_result
        return status

    def _get_datos_cesion_dte(self, signature_d, token):
        url = server_url[self.company_id.dte_service_provider] + 'services/wsRPETCConsulta?wsdl'
        _server = Client(url)
        rut = signature_d['subject_serial_number']
        tenedor_rut = self.company_id.vat if self.sii_cesion_result == 'Cedido' else self.cesionario_id.vat
        respuesta = _server.service.getEstCesionRelac(
            token,
            rut[:8],
            str(rut[-1]),
            str(self.sii_document_class_id.sii_code),
            str(self.sii_document_number),
            tenedor_rut[2:-1],
            tenedor_rut[-1],
        )
        #self.sii_message = respuesta
        resp = xmltodict.parse(respuesta)
        status =  False
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == '2':
            status = {'warning':{'title':_("Error code: 2"), 'message': _(resp['SII:RESPUESTA']['SII:RESP_HDR']['GLOSA'])}}
            return status
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "EPR":
            sii_result = "Procesado"
            if resp['SII:RESPUESTA']['SII:RESP_BODY']['RECHAZADOS'] == "1":
                sii_result = "Rechazado"
            if resp['SII:RESPUESTA']['SII:RESP_BODY']['REPARO'] == "1":
                sii_result = "Reparo"
        elif resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "FAU":
            sii_result = "Rechazado"
        #self.sii_cesion_result = result

    @api.multi
    def ask_for_cesion_dte_status(self):
        try:
            signature_d = self.get_digital_signature_pem(
                self.company_id)
            seed = self.get_seed(self.company_id)
            template_string = self.create_template_seed(seed)
            seed_firmado = self.sign_seed(
                template_string,
                signature_d['priv_key'],
                signature_d['cert'],
            )
            token = self.get_token(
                seed_firmado,
                self.company_id,
            )
        except AssertionError as e:
            raise UserError(str(e))
        if not self.sii_send_ident:
            raise UserError('No se ha enviado aún el documento, aún está en cola de envío interna en odoo')
        #if self.sii_cesion_result == 'Cedido':
        #    return self._get_datos_cesion_dte(
        #        signature_d,
        #        token,
        #    )
        if self.sii_cesion_result == 'Enviado':
            status = self._get_cesion_send_status(
                self.sii_cesion_send_ident,
                signature_d,
                token,
            )
            if self.sii_cesion_result != 'Procesado':
                return status
        return self._get_cesion_dte_status(signature_d, token)

class CesionDTEAR(models.Model):
    _name = 'account.invoice.imagen_ar'

    name = fields.Char(
        string='File Name',
    )
    image = fields.Binary(
        string='Imagen',
        filters='*.pdf,*.png, *.jpg',
        store=True,
        help='Upload Image',
    )
    invoice_id = fields.Many2one(
        'account.invoice',
        string="Factura",
    )
