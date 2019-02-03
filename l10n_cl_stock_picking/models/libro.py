# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging
from lxml import etree
from lxml.etree import Element, SubElement
from lxml import objectify
from lxml.etree import XMLSyntaxError
from odoo import SUPERUSER_ID

import pytz

import collections

_logger = logging.getLogger(__name__)

try:
    from suds.client import Client
except:
    pass

try:
    import urllib3
except:
    pass

pool = urllib3.PoolManager()
import textwrap

try:
    import xmltodict
except ImportError:
    _logger.info('Cannot import xmltodict library')

try:
    import dicttoxml
    dicttoxml.set_debug(False)
except ImportError:
    _logger.info('Cannot import dicttoxml library')

try:
    import base64
except ImportError:
    _logger.info('Cannot import base64 library')

try:
    import hashlib
except ImportError:
    _logger.info('Cannot import hashlib library')

try:
    import cchardet
except ImportError:
    _logger.info('Cannot import cchardet library')

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    import OpenSSL
    from OpenSSL import crypto
    type_ = crypto.FILETYPE_PEM
except:
    _logger.warning('Cannot import OpenSSL library')

server_url = {'SIICERT':'https://maullin.sii.cl/DTEWS/','SII':'https://palena.sii.cl/DTEWS/'}

BC = '''-----BEGIN CERTIFICATE-----\n'''
EC = '''\n-----END CERTIFICATE-----\n'''

# hardcodeamos este valor por ahora
import os
xsdpath = os.path.dirname(os.path.realpath(__file__)).replace('/models','/static/xsd/')

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
'''
Extensión del modelo de datos para contener parámetros globales necesarios
 para todas las integraciones de factura electrónica.
 @author: Daniel Blanco Martin (daniel[at]blancomartin.cl)
 @version: 2016-06-11
'''

class LibroGuia(models.Model):
    _name = "stock.picking.book"

    @api.multi
    def unlink(self):
        for libro in self:
            if libro.state not in ('draft', 'cancel'):
                raise UserError(_('You cannot delete a Validated book.'))
        return super(LibroGuia, self).unlink()

    def split_cert(self, cert):
        certf, j = '', 0
        for i in range(0, 29):
            certf += cert[76 * i:76 * (i + 1)] + '\n'
        return certf

    def create_template_envio(self, RutEmisor, PeriodoTributario, FchResol, NroResol, EnvioDTE,signature_d,TipoLibro='MENSUAL',TipoEnvio='TOTAL',FolioNotificacion="123", IdEnvio='SetDoc'):
        if TipoLibro in ['ESPECIAL']:
            FolioNotificacion = '<FolioNotificacion>{0}</FolioNotificacion>'.format(FolioNotificacion)
        else:
            FolioNotificacion = ''
        xml = '''<EnvioLibro ID="{9}">
<Caratula>
<RutEmisorLibro>{0}</RutEmisorLibro>
<RutEnvia>{1}</RutEnvia>
<PeriodoTributario>{2}</PeriodoTributario>
<FchResol>{3}</FchResol>
<NroResol>{4}</NroResol>
<TipoLibro>{5}</TipoLibro>
<TipoEnvio>{6}</TipoEnvio>
{7}
</Caratula>
{8}
</EnvioLibro>
'''.format(RutEmisor, signature_d['subject_serial_number'], PeriodoTributario,
           FchResol, NroResol, TipoLibro,TipoEnvio,FolioNotificacion, EnvioDTE,IdEnvio)
        return xml

    def time_stamp(self, formato='%Y-%m-%dT%H:%M:%S'):
        tz = pytz.timezone('America/Santiago')
        return datetime.now(tz).strftime(formato)

    '''
    Funcion auxiliar para conversion de codificacion de strings
     proyecto experimentos_dte
     @author: Daniel Blanco Martin (daniel[at]blancomartin.cl)
     @version: 2014-12-01
    '''
    def convert_encoding(self, data, new_coding = 'UTF-8'):
        encoding = cchardet.detect(data)['encoding']
        if new_coding.upper() != encoding.upper():
            data = data.decode(encoding, data).encode(new_coding)
        return data

    def xml_validator(self, some_xml_string, validacion='doc'):
        validacion_type = {
            'doc': 'DTE_v10.xsd',
            'env': 'EnvioDTE_v10.xsd',
            'sig': 'xmldsignature_v10.xsd',
            'libro': 'LibroGuia_v10.xsd',
            'libroS': 'LibroCVS_v10.xsd',
        }
        xsd_file = xsdpath+validacion_type[validacion]
        try:
            xmlschema_doc = etree.parse(xsd_file)
            xmlschema = etree.XMLSchema(xmlschema_doc)
            xml_doc = etree.fromstring(some_xml_string)
            result = xmlschema.validate(xml_doc)
            if not result:
                xmlschema.assert_(xml_doc)
            return result
        except AssertionError as e:
            raise UserError(_('XML Malformed Error:  %s') % e.args)

    def get_seed(self, company_id):
        return self.env['account.invoice'].get_seed(company_id)

    def create_template_seed(self, seed):
        xml = u'''<getToken>
<item>
<Semilla>{}</Semilla>
</item>
</getToken>
'''.format(seed)
        return xml

    def create_template_env(self, doc,simplificado=False):
        simp = 'http://www.sii.cl/SiiDte LibroGuia_v10.xsd'
        if simplificado:
            simp ='http://www.sii.cl/SiiDte LibroCVS_v10.xsd'
        xml = '''<LibroGuia xmlns="http://www.sii.cl/SiiDte" \
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" \
xsi:schemaLocation="{0}" \
version="1.0">
{1}</LibroGuia>'''.format(simp, doc)
        return xml

    def sign_seed(self, message, privkey, cert):
        return self.env['account.invoice'].sign_seed(message, privkey, cert)

    def get_token(self, seed_file, company_id):
        return self.env['account.invoice'].get_token(seed_file, company_id)

    def ensure_str(self,x, encoding="utf-8", none_ok=False):
        if none_ok is True and x is None:
            return x
        if not isinstance(x, str):
            x = x.decode(encoding)
        return x

    def sign_full_xml(self, message, privkey, cert, uri, type='libro'):
        doc = etree.fromstring(message)
        string = etree.tostring(doc[0])
        mess = etree.tostring(etree.fromstring(string), method="c14n")
        digest = base64.b64encode(self.digest(mess))
        reference_uri='#'+uri
        signed_info = Element("SignedInfo")
        c14n_method = SubElement(signed_info, "CanonicalizationMethod", Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
        sign_method = SubElement(signed_info, "SignatureMethod", Algorithm='http://www.w3.org/2000/09/xmldsig#rsa-sha1')
        reference = SubElement(signed_info, "Reference", URI=reference_uri)
        transforms = SubElement(reference, "Transforms")
        SubElement(transforms, "Transform", Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        digest_method = SubElement(reference, "DigestMethod", Algorithm="http://www.w3.org/2000/09/xmldsig#sha1")
        digest_value = SubElement(reference, "DigestValue")
        digest_value.text = digest
        signed_info_c14n = etree.tostring(signed_info,method="c14n",exclusive=False,with_comments=False,inclusive_ns_prefixes=None)
        att = 'xmlns="http://www.w3.org/2000/09/xmldsig#" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        #@TODO Find better way to add xmlns:xsi attrib
        signed_info_c14n = signed_info_c14n.decode().replace("<SignedInfo>", "<SignedInfo %s>" % att )
        xmlns = 'http://www.w3.org/2000/09/xmldsig#'
        sig_root = Element("Signature",attrib={'xmlns':xmlns})
        sig_root.append(etree.fromstring(signed_info_c14n))
        signature_value = SubElement(sig_root, "SignatureValue")
        key = crypto.load_privatekey(type_,privkey.encode('ascii'))
        signature = crypto.sign(key,signed_info_c14n,'sha1')
        signature_value.text =textwrap.fill(base64.b64encode(signature).decode(),64)
        key_info = SubElement(sig_root, "KeyInfo")
        key_value = SubElement(key_info, "KeyValue")
        rsa_key_value = SubElement(key_value, "RSAKeyValue")
        modulus = SubElement(rsa_key_value, "Modulus")
        key = load_pem_private_key(privkey.encode('ascii'),password=None, backend=default_backend())
        longs = self.env['account.invoice'].long_to_bytes(key.public_key().public_numbers().n)
        modulus.text =  textwrap.fill(base64.b64encode(longs).decode(),64)
        exponent = SubElement(rsa_key_value, "Exponent")
        longs = self.env['account.invoice'].long_to_bytes(key.public_key().public_numbers().e)
        exponent.text = self.ensure_str(base64.b64encode(longs))
        x509_data = SubElement(key_info, "X509Data")
        x509_certificate = SubElement(x509_data, "X509Certificate")
        x509_certificate.text = '\n'+textwrap.fill(cert,64)
        msg = etree.tostring(sig_root)
        msg = msg if self.xml_validator(msg, 'sig') else ''
        fulldoc = message.replace('</LibroGuia>','%s\n</LibroGuia>' % msg.decode())
        fulldoc = fulldoc if self.xml_validator(fulldoc, type) else ''
        return fulldoc

    def get_digital_signature_pem(self, comp_id):
        obj = user = False
        if 'responsable_envio' in self and self._ids:
            obj = user = self[0].responsable_envio
        if not obj:
            obj = user = self.env.user
        if not obj.cert:
            obj = self.env['res.users'].search([("authorized_users_ids","=", user.id)])
            if not obj or not obj.cert:
                obj = self.env['res.company'].browse([comp_id.id])
                if not obj.cert or not user.id in obj.authorized_users_ids.ids:
                    return False
        signature_data = {
            'subject_name': obj.name,
            'subject_serial_number': obj.subject_serial_number,
            'priv_key': obj.priv_key,
            'cert': obj.cert,
            'rut_envia': obj.subject_serial_number
            }
        return signature_data

    def get_digital_signature(self, comp_id):
        obj = user = False
        if 'responsable_envio' in self and self._ids:
            obj = user = self[0].responsable_envio
        if not obj:
            obj = user = self.env.user
        _logger.info(obj.name)
        if not obj.cert:
            obj = self.env['res.users'].search([("authorized_users_ids","=", user.id)])
            if not obj or not obj.cert:
                obj = self.env['res.company'].browse([comp_id.id])
                if not obj.cert or not user.id in obj.authorized_users_ids.ids:
                    return False
        signature_data = {
            'subject_name': obj.name,
            'subject_serial_number': obj.subject_serial_number,
            'priv_key': obj.priv_key,
            'cert': obj.cert}
        return signature_data

    def get_resolution_data(self, comp_id):
        resolution_data = {
            'dte_resolution_date': comp_id.dte_resolution_date,
            'dte_resolution_number': comp_id.dte_resolution_number}
        return resolution_data

    @api.multi
    def send_xml_file(self, envio_dte=None, file_name="envio",company_id=False):
        signature_d = self.env.user.get_digital_signature(company_id)
        if not signature_d:
            raise UserError(_('''There is no Signer Person with an \
        authorized signature for you in the system. Please make sure that \
        'user_signature_key' module has been installed and enable a digital \
        signature, for you or make the signer to authorize you to use his \
        signature.'''))
        if not company_id.dte_service_provider:
            raise UserError(_("Not Service provider selected!"))
        token = self.env['sii.xml.envio'].get_token( self.env.user, company_id )
        url = 'https://palena.sii.cl'
        if company_id.dte_service_provider == 'SIICERT':
            url = 'https://maullin.sii.cl'
        post = '/cgi_dte/UPL/DTEUpload'
        headers = {
            'Accept': 'image/gif, image/x-xbitmap, image/jpeg, image/pjpeg, application/vnd.ms-powerpoint, application/ms-excel, application/msword, */*',
            'Accept-Language': 'es-cl',
            'Accept-Encoding': 'gzip, deflate',
            'User-Agent': 'Mozilla/4.0 (compatible; PROG 1.0; Windows NT 5.0; YComp 5.0.2.4)',
            'Referer': '{}'.format(company_id.website),
            'Connection': 'Keep-Alive',
            'Cache-Control': 'no-cache',
            'Cookie': 'TOKEN={}'.format(token),
        }
        params = collections.OrderedDict()
        params['rutSender'] = signature_d['subject_serial_number'][:8]
        params['dvSender'] = signature_d['subject_serial_number'][-1]
        params['rutCompany'] = company_id.vat[2:-1]
        params['dvCompany'] = company_id.vat[-1]
        file_name = file_name + '.xml'
        params['archivo'] = (file_name,'<?xml version="1.0" encoding="ISO-8859-1"?>\n'+envio_dte,"text/xml")
        multi  = urllib3.filepost.encode_multipart_formdata(params)
        headers.update({'Content-Length': '{}'.format(len(multi[0]))})
        response = pool.request_encode_body('POST', url+post, params, headers)
        retorno = {'sii_xml_response': response.data, 'sii_result': 'NoEnviado','sii_send_ident':''}
        if response.status != 200:
            return retorno
        respuesta_dict = xmltodict.parse(response.data)
        if respuesta_dict['RECEPCIONDTE']['STATUS'] != '0':
            _logger.info('l736-status no es 0')
            _logger.info(connection_status[respuesta_dict['RECEPCIONDTE']['STATUS']])
        else:
            retorno.update({'sii_result': 'Enviado','sii_send_ident':respuesta_dict['RECEPCIONDTE']['TRACKID']})
        return retorno

    @api.multi
    def get_xml_file(self):
        return {
            'type' : 'ir.actions.act_url',
            'url': '/download/xml/libro_guia%s' % (self.id),
            'target': 'self',
        }

    def format_vat(self, value):
        return value[2:10] + '-' + value[10:]

    def digest(self, data):
        sha1 = hashlib.new('sha1', data)
        return sha1.digest()

    @api.onchange('periodo_tributario','tipo_operacion')
    def _setName(self):
        if self.name:
            return
        if self.periodo_tributario and self.name:
            self.name += " " + self.periodo_tributario

    sii_message = fields.Text(
        string='SII Message',
        copy=False)
    sii_xml_request = fields.Text(
        string='SII XML Request',
        copy=False)
    sii_xml_response = fields.Text(
        string='SII XML Response',
        copy=False)
    sii_send_ident = fields.Text(
        string='SII Send Identification',
        copy=False)
    state = fields.Selection(
            [
                ('draft', 'Borrador'),
                ('NoEnviado', 'No Enviado'),
                ('Enviado', 'Enviado'),
                ('Aceptado', 'Aceptado'),
                ('Rechazado', 'Rechazado'),
                ('Reparo', 'Reparo'),
                ('Proceso', 'Proceso'),
                ('Reenviar', 'Reenviar'),
                ('Anulado', 'Anulado')
            ],
            string='Resultado',
            index=True,
            readonly=True,
            default='draft',
            track_visibility='onchange', copy=False,
            help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed Invoice.\n"
             " * The 'Pro-forma' status is used the invoice does not have an invoice number.\n"
             " * The 'Open' status is used when user create invoice, an invoice number is generated. Its in open status till user does not pay invoice.\n"
             " * The 'Paid' status is set automatically when the invoice is paid. Its related journal entries may or may not be reconciled.\n"
             " * The 'Cancelled' status is used when user cancel invoice.",
        )
    move_ids = fields.Many2many(
            'stock.picking',
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    tipo_libro = fields.Selection(
            [
                    ('ESPECIAL','Especial'),
            ],
            string="Tipo de Libro",
            default='ESPECIAL',
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    tipo_envio = fields.Selection(
            [
                    ('AJUSTE','Ajuste'),
                    ('TOTAL','Total'),
                    ('PARCIAL','Parcial'),
                    ('TOTAL','Total')
            ],
            string="Tipo de Envío",
            default="TOTAL",
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    folio_notificacion = fields.Char(string="Folio de Notificación",
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    #total_afecto = fields.Char(string="Total Afecto")
    #total_exento = fields.Char(string="Total Exento")
    periodo_tributario = fields.Char(
            string='Periodo Tributario',
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]},
            default=lambda *a: datetime.now().strftime('%Y-%m'),
        )
    company_id = fields.Many2one('res.company',
            required=True,
            default=lambda self: self.env.user.company_id.id,
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    name = fields.Char(
            string="Detalle",
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]},
        )

    @api.multi
    def validar_libro(self):
        self._crear_libro()
        return self.write({'state': 'NoEnviado'})

    def _acortar_str(self, texto, size=1):
        c = 0
        cadena = ""
        while c < size and c < len(texto):
            cadena += texto[c]
            c += 1
        return cadena

    def getResumen(self, rec):
        referencia =False
        if rec.reference:
            ob = self.env['account.invoice']
            ref = ob.search([('number','=',rec.sii_document_number)])
            referencia = self.env['account.move'].search([('document_number','=',ref.origin)])
        det = collections.OrderedDict()
        det['Folio'] = int(rec.sii_document_number)
        if rec.canceled and rec.sii_xml_request and rec.sii_xml_request.sii_send_ident: #cancelada y enviada al sii
            det['Anulado'] = 2
        elif rec.canceled: # para anular folio
            det['Anulado'] = 1
        #det['Operacion'] =[1,2]
        det['TpoOper'] = rec.move_reason
        det['FchDoc'] = rec.date[:10]
        det['RUTDoc'] = self.format_vat(rec.partner_id.vat or self.company_id.partner_id.vat)
        name =  rec.partner_id.name or self.company_id.name
        det['RznSoc'] = name[:50]
        tasa = '19.00'
        if rec.move_reason == '5':
            rec.amount_untaxed = rec.amount_tax = rec.amount_total = 0
        if rec.amount_untaxed > 0:
            det['MntNeto'] = int(round(rec.amount_untaxed))
            det['TasaImp'] = tasa
        if rec.amount_tax:
            det['IVA'] = int(round(rec.amount_tax))
        det['MntTotal'] = int(round(rec.amount_total,0))
        if referencia:
            det['TpoDocRef'] = referencia.journal_document_class_id.sii_code
            det['FolioDocRef'] = referencia.origin
            det['FchDocRef'] = referencia.date[:10]
        if rec.reference:
            for r in rec.reference:##reparar para que no sobreescriba
                det['TpoDocRef'] = r.sii_referencia_TpoDocRef.sii_code
                det['FolioDocRef'] = r.origen
                det['FchDocRef'] = r.date
        return det

    def _setResumenPeriodo(self,resumen,resumenP):
        if not 'TotFolAnulado' in resumenP and 'Anulado' in resumen:
            if resumen['Anulado'] == 1:
                resumenP['TotFolAnulado'] = 1
            else:
                resumenP['TotGuiaAnulada'] = 1
            return resumenP
        elif 'Anulado' in resumen:
            if resumen['Anulado'] == 1 and 'TotFolAnulado':
                resumenP['TotFolAnulado'] += 1
            elif resumen['Anulado'] == '1':
                resumenP['TotFolAnulado'] = 1
            elif 'TotGuiaAnulada' in resumenP:
                resumenP['TotGuiaAnulada'] += 1
            else:
                resumenP['TotGuiaAnulada'] = 1
            return resumenP
        if resumen['TpoOper'] in ["1","2"] and not 'TotGuiaVenta' in resumenP:
            resumenP['TotGuiaVenta'] = 1
            resumenP['TotMntGuiaVta'] = resumen['MntTotal']
        elif 'TotGuiaVenta' in resumenP and resumen['TpoOper'] in ["1","2"]:
            resumenP['TotGuiaVenta'] += 1
            resumenP['TotMntGuiaVta'] += resumen['MntTotal']
        else:
            TotTraslado = []
            if not 'itemTraslado' in resumenP:
                tras = collections.OrderedDict()
                tras['TpoTraslado'] = resumen['TpoOper']
                tras['CantGuia'] = 1
                tras['MntGuia'] = resumen['MntTotal']
                TotTraslado.extend( [{'TotTraslado': tras}])
                resumenP['itemTraslado'] = TotTraslado
            else:
                new = []
                seted= False
                for tpo in resumenP['itemTraslado']:
                    if resumen['TpoOper'] == tpo['TotTraslado']['TpoTraslado']:
                        tpo['TotTraslado']['CantGuia'] +=1
                        tpo['TotTraslado']['MntGuia'] += resumen['MntTotal']
                        seted=True
                    new.extend([tpo])
                if not seted:
                    tras = collections.OrderedDict()
                    tras['TpoTraslado'] = resumen['TpoOper']
                    tras['CantGuia'] = 1
                    tras['MntGuia'] = resumen['MntTotal']
                    new.extend( [{'TotTraslado': tras}])
                resumenP['itemTraslado'] = new
        return resumenP

    def _crear_libro(self):
        company_id = self.company_id
        dte_service = company_id.dte_service_provider
        try:
            signature_d = self.get_digital_signature(company_id)
        except:
            raise UserError(_('''There is no Signer Person with an \
        authorized signature for you in the system. Please make sure that \
        'user_signature_key' module has been installed and enable a digital \
        signature, for you or make the signer to authorize you to use his \
        signature.'''))
        certp = signature_d['cert'].replace(
            BC, '').replace(EC, '').replace('\n', '')
        resumenes = []
        resumenPeriodo = {}
        for rec in self.with_context(lang='es_CL').move_ids:
            resumen = self.getResumen(rec)
            resumenes.extend([{'Detalle':resumen}])
            resumenPeriodo = self._setResumenPeriodo(resumen, resumenPeriodo)
        rPeriodo = collections.OrderedDict()
        fields = ['TotFolAnulado', 'TotGuiaAnulada', 'TotGuiaVenta','TotMntGuiaVta','TotMntModificado',
                    'itemTraslado']
        for f in fields:
            if f in resumenPeriodo:
                rPeriodo[f] = resumenPeriodo[f]
        dte = collections.OrderedDict()
        dte['ResumenPeriodo'] = rPeriodo
        dte['item'] = resumenes
        dte['TmstFirma'] = self.time_stamp()

        resol_data = self.get_resolution_data(company_id)
        RUTEmisor = self.format_vat(company_id.vat)
        RUTRecep = "60803000-K" # RUT SII
        xml = dicttoxml.dicttoxml(
            dte, root=False, attr_type=False).decode()
        doc_id =  'GUIA_'+self.periodo_tributario
        libro = self.create_template_envio( RUTEmisor, self.periodo_tributario,
            resol_data['dte_resolution_date'],
            resol_data['dte_resolution_number'],
            xml, signature_d,self.tipo_libro,self.tipo_envio,self.folio_notificacion, doc_id)
        xml  = self.create_template_env(libro)
        root = etree.XML( xml )
        envio_dte = etree.tostring(root, pretty_print=True).decode()\
                .replace('<item>','\n').replace('</item>','').replace('<itemTraslado>','').replace('</itemTraslado>','\n')
        envio_dte = self.sign_full_xml(
            envio_dte,
            signature_d['priv_key'],
            certp,
            doc_id,
            'libro')
        return envio_dte, doc_id

    @api.multi
    def do_dte_send_book(self):
        company_id = self.company_id
        envio_dte, doc_id = self._crear_libro()
        result = self.send_xml_file(envio_dte, doc_id+'.xml', company_id)
        self.write({
            'sii_xml_response':result['sii_xml_response'],
            'sii_send_ident':result['sii_send_ident'],
            'state': result['sii_result'],
            'sii_xml_request':envio_dte})

    def _get_send_status(self, track_id, signature_d,token):
        url = server_url[self.company_id.dte_service_provider] + 'QueryEstUp.jws?WSDL'
        ns = 'urn:'+ server_url[self.company_id.dte_service_provider] + 'QueryEstUp.jws'
        _server = Client(url, ns)
        rut = self.format_vat(self.company_id.vat)
        respuesta = _server.getEstUp(rut[:8], str(rut[-1]),track_id,token)
        self.sii_message = respuesta
        resp = xmltodict.parse(respuesta)
        status = False
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "-11":
            status =  {'warning':{'title':_('Error -11'), 'message': _("Error -11: Espere a que sea aceptado por el SII, intente en 5s más")}}
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "EPR":
            self.state = "Proceso"
            if resp['SII:RESPUESTA']['SII:RESP_BODY']['RECHAZADOS'] == "1":
                self.sii_result = "Rechazado"
        elif resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "RCT":
            self.state = "Rechazado"
            status = {'warning':{'title':_('Error RCT'), 'message': _(resp['SII:RESPUESTA']['GLOSA'])}}
        return status

    def _get_dte_status(self, signature_d, token):
        url = server_url[self.company_id.dte_service_provider] + 'QueryEstDte.jws?WSDL'
        ns = 'urn:'+ server_url[self.company_id.dte_service_provider] + 'QueryEstDte.jws'
        _server = Client(url, ns)
        receptor = self.format_vat(self.partner_id.vat or self.company_id.partner_id.vat)
        date_invoice = datetime.strptime(self.date_invoice, "%Y-%m-%d").strftime("%d-%m-%Y")
        respuesta = _server.getEstDte(signature_d['subject_serial_number'][:8], str(signature_d['subject_serial_number'][-1]),
                self.company_id.vat[2:-1],self.company_id.vat[-1], receptor[:8],receptor[2:-1],str(self.document_class_id.sii_code), str(self.sii_document_number),
                date_invoice, str(self.amount_total),token)
        self.sii_message = respuesta
        resp = xmltodict.parse(respuesta)
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == '2':
            status = {'warning':{'title':_("Error code: 2"), 'message': _(resp['SII:RESPUESTA']['SII:RESP_HDR']['GLOSA'])}}
            return status
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "EPR":
            self.state = "Proceso"
            if resp['SII:RESPUESTA']['SII:RESP_BODY']['RECHAZADOS'] == "1":
                self.state = "Rechazado"
            if resp['SII:RESPUESTA']['SII:RESP_BODY']['REPARO'] == "1":
                self.state = "Reparo"
        elif resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "RCT":
            self.state = "Rechazado"

    @api.multi
    def ask_for_dte_status(self):
        try:
            signature_d = self.get_digital_signature_pem(
                self.company_id)
            seed = self.get_seed(self.company_id)
            template_string = self.create_template_seed(seed)
            seed_firmado = self.sign_seed(
                template_string, signature_d['priv_key'],
                signature_d['cert'])
            token = self.get_token(seed_firmado,self.company_id)
        except:
            raise UserError(connection_status[response.e])
        xml_response = xmltodict.parse(self.sii_xml_response)
        if self.state == 'Enviado':
            status = self._get_send_status(self.sii_send_ident, signature_d, token)
            if self.state != 'Proceso':
                return status
        return self._get_dte_status(signature_d, token)
