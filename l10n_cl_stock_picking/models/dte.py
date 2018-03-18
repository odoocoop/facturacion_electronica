# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta, date
import logging
from lxml import etree
from lxml.etree import Element, SubElement
from lxml import objectify
from lxml.etree import XMLSyntaxError
from odoo import SUPERUSER_ID

import pytz
from six import string_types

import collections

_logger = logging.getLogger(__name__)

try:
    from io import BytesIO
except:
    _logger.warning("no se ha cargado io")

try:
    from suds.client import Client
except:
    pass

try:
    import urllib3
except:
    pass

try:
    urllib3.disable_warnings()
except:
    pass

try:
    pool = urllib3.PoolManager()
except:
    pass

try:
    import xmltodict
except ImportError:
    _logger.info('Cannot import xmltodict library')

try:
    import dicttoxml
except ImportError:
    _logger.info('Cannot import dicttoxml library')

try:
    import pdf417gen
except ImportError:
    _logger.info('Cannot import pdf417gen library')

try:
    import base64
except ImportError:
    _logger.info('Cannot import base64 library')

# timbre patrón. Permite parsear y formar el
# ordered-dict patrón corespondiente al documento
timbre  = """<TED version="1.0"><DD><RE>99999999-9</RE><TD>11</TD><F>1</F>\
<FE>2000-01-01</FE><RR>99999999-9</RR><RSR>\
XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX</RSR><MNT>10000</MNT><IT1>IIIIIII\
</IT1><CAF version="1.0"><DA><RE>99999999-9</RE><RS>YYYYYYYYYYYYYYY</RS>\
<TD>10</TD><RNG><D>1</D><H>1000</H></RNG><FA>2000-01-01</FA><RSAPK><M>\
DJKFFDJKJKDJFKDJFKDJFKDJKDnbUNTAi2IaDdtAndm2p5udoqFiw==</M><E>Aw==</E></RSAPK>\
<IDK>300</IDK></DA><FRMA algoritmo="SHA1withRSA">\
J1u5/1VbPF6ASXkKoMOF0Bb9EYGVzQ1AMawDNOy0xSuAMpkyQe3yoGFthdKVK4JaypQ/F8\
afeqWjiRVMvV4+s4Q==</FRMA></CAF><TSTED>2014-04-24T12:02:20</TSTED></DD>\
<FRMT algoritmo="SHA1withRSA">jiuOQHXXcuwdpj8c510EZrCCw+pfTVGTT7obWm/\
fHlAa7j08Xff95Yb2zg31sJt6lMjSKdOK+PQp25clZuECig==</FRMT></TED>"""
result = xmltodict.parse(timbre)

server_url = {'SIICERT':'https://maullin.sii.cl/DTEWS/','SII':'https://palena.sii.cl/DTEWS/'}

BC = '''-----BEGIN CERTIFICATE-----\n'''
EC = '''\n-----END CERTIFICATE-----\n'''

# hardcodeamos este valor por ahora
import os, sys
USING_PYTHON2 = True if sys.version_info < (3, 0) else False
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

class stock_picking(models.Model):
    _inherit = "stock.picking"

    def split_cert(self, cert):
        certf, j = '', 0
        for i in range(0, 29):
            certf += cert[76 * i:76 * (i + 1)] + '\n'
        return certf

    def create_template_envio(self, RutEmisor, RutReceptor, FchResol, NroResol,
                              TmstFirmaEnv, EnvioDTE,signature_d,SubTotDTE):
        xml = '''<SetDTE ID="SetDoc">
<Caratula version="1.0">
<RutEmisor>{0}</RutEmisor>
<RutEnvia>{1}</RutEnvia>
<RutReceptor>{2}</RutReceptor>
<FchResol>{3}</FchResol>
<NroResol>{4}</NroResol>
<TmstFirmaEnv>{5}</TmstFirmaEnv>
{6}</Caratula>
{7}
</SetDTE>
'''.format(RutEmisor, signature_d['subject_serial_number'], RutReceptor,
           FchResol, NroResol, TmstFirmaEnv, SubTotDTE, EnvioDTE)
        return xml

    def time_stamp(self, formato='%Y-%m-%dT%H:%M:%S'):
        tz = pytz.timezone('America/Santiago')
        return datetime.now(tz).strftime(formato)

    def xml_validator(self, some_xml_string, validacion='doc'):
        validacion_type = {
            'doc': 'DTE_v10.xsd',
            'env': 'EnvioDTE_v10.xsd',
            'recep' : 'Recibos_v10.xsd',
            'env_recep' : 'EnvioRecibos_v10.xsd',
            'env_resp': 'RespuestaEnvioDTE_v10.xsd',
            'sig': 'xmldsignature_v10.xsd'
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

    def create_template_doc(self, doc):
        xml = '''<DTE xmlns="http://www.sii.cl/SiiDte" version="1.0">
{}</DTE>'''.format(doc)
        return xml

    def create_template_env(self, doc):
        xml = '''<?xml version="1.0" encoding="ISO-8859-1"?>
<EnvioDTE xmlns="http://www.sii.cl/SiiDte" \
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" \
xsi:schemaLocation="http://www.sii.cl/SiiDte EnvioDTE_v10.xsd" \
version="1.0">
{}</EnvioDTE>'''.format(doc)
        return xml

    def create_template_doc1(self, doc, sign):
        xml = doc.replace('</DTE>',  sign.decode() + '</DTE>')
        return xml

    def create_template_env1(self, doc, sign):
        xml = doc.replace('</EnvioDTE>', sign.decode() + '</EnvioDTE>')
        return xml

    def create_template_seed(self, seed):
        return self.env['account.invoice'].create_template_seed(seed)

    def get_seed(self, company_id):
        return self.env['account.invoice'].get_seed(company_id)

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

    def get_digital_signature_pem(self, comp_id):
        obj = user = self[0].responsable_envio
        if not obj:
            obj = user = self.env.user
        if not obj.cert:
            obj = self.env['res.company'].browse([comp_id.id])
            if not obj or not obj.cert:
                obj = self.env['res.users'].search([("authorized_users_ids","=", user.id)])
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
        if not obj.cert:
            obj = self.env['res.company'].browse([comp_id.id])
            if not obj or not obj.cert:
                obj = self.env['res.users'].search([("authorized_users_ids","=", user.id)])
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
    def send_xml_file(self, envio_dte=None, file_name="envio.xml",company_id=False):
        if not company_id.dte_service_provider:
            raise UserError(_("Not Service provider selected!"))
        #try:
        signature_d = self.get_digital_signature_pem(
            company_id)
        seed = self.get_seed(company_id)
        template_string = self.create_template_seed(seed)
        seed_firmado = self.sign_seed(
            template_string,
            signature_d['priv_key'],
            signature_d['cert'])
        token = self.get_token(seed_firmado,company_id)
        #except:
        #    _logger.warning('error')
        #    return
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
        params['archivo'] = (file_name,'<?xml version="1.0" encoding="ISO-8859-1"?>\n'+envio_dte,"text/xml")
        multi  = urllib3.filepost.encode_multipart_formdata(params)
        headers.update({'Content-Length': '{}'.format(len(multi[0]))})
        try:
            response = pool.request_encode_body('POST', url+post, params, headers)
            retorno = {'sii_xml_response': response.data, 'sii_result': 'NoEnviado','sii_send_ident':''}
        except:
            retorno = {'sii_xml_response': 'error', 'sii_result': 'NoEnviado','sii_send_ident':''}
            return retorno
        if response.status != 200:
            return retorno
        respuesta_dict = xmltodict.parse(response.data)
        if respuesta_dict['RECEPCIONDTE']['STATUS'] != '0':
            _logger.info(connection_status[respuesta_dict['RECEPCIONDTE']['STATUS']])
        else:
            retorno.update({'sii_result': 'Enviado','sii_send_ident':respuesta_dict['RECEPCIONDTE']['TRACKID']})
        return retorno

    @api.multi
    def get_xml_file(self):
        return {
            'type' : 'ir.actions.act_url',
            'url': '/download/xml/guia/%s' % (self.id),
            'target': 'self',
        }

    def get_folio(self):
        # saca el folio directamente de la secuencia
        return int(self.sii_document_number)

    def format_vat(self, value, con_cero=False):
        ''' Se Elimina el 0 para prevenir problemas con el sii, ya que las muestras no las toma si va con
        el 0 , y tambien internamente se generan problemas, se mantiene el 0 delante, para cosultas, o sino retorna "error de datos"'''
        if not value or value=='' or value == 0:
            value ="CL666666666"
            #@TODO opción de crear código de cliente en vez de rut genérico
        rut = value[:10] + '-' + value[10:]
        if not con_cero:
            rut = rut.replace('CL0','')
        rut = rut.replace('CL','')
        return rut

    def pdf417bc(self, ted):
        bc = pdf417gen.encode(
            ted,
            security_level=5,
            columns=13,
        )
        image = pdf417gen.render_image(
            bc,
            padding=15,
            scale=1,
        )
        return image

    def signmessage(self, texto, key):
        return self.env['account.invoice'].signmessage(texto, key)

    sii_batch_number = fields.Integer(
        copy=False,
        string='Batch Number',
        readonly=True,
        help='Batch number for processing multiple invoices together')
    sii_barcode = fields.Char(
        copy=False,
        string=_('SII Barcode'),
        readonly=True,
        help='SII Barcode Name')
    sii_barcode_img = fields.Binary(
        copy=False,
        string=_('SII Barcode Image'),
        help='SII Barcode Image in PDF417 format')
    sii_receipt = fields.Text(
        string='SII Mensaje de recepción',
        copy=False)
    sii_message = fields.Text(
        string='SII Message',
        copy=False)
    sii_xml_dte = fields.Text(
            string='SII XML DTE',
            copy=False,
        )
    sii_xml_request = fields.Text(
            string='SII XML Request',
            copy=False,
        )
    sii_xml_response = fields.Text(
            string='SII XML Response',
            copy=False,
        )
    sii_send_ident = fields.Text(
            string='SII Send Identification',
            copy=False,
        )
    sii_result = fields.Selection(
            [
                ('', 'n/a'),
                ('NoEnviado', 'No Enviado'),
                ('EnCola','En cola de envío'),
                ('Enviado', 'Enviado'),
                ('Aceptado', 'Aceptado'),
                ('Rechazado', 'Rechazado'),
                ('Reparo', 'Reparo'),
                ('Proceso', 'Proceso'),
                ('Reenviar', 'Reenviar'),
                ('Anulado', 'Anulado'),
            ],
            string='Resultado',
            readonly=True,
            states={'draft': [('readonly', False)]},
            copy=False,
            help="SII request result",
            default = '',
        )
    canceled = fields.Boolean(string="Is Canceled?")
    estado_recep_dte = fields.Selection(
        [
            ('no_revisado','No Revisado'),
            ('0','Conforme'),
            ('1','Error de Schema'),
            ('2','Error de Firma'),
            ('3','RUT Receptor No Corresponde'),
            ('90','Archivo Repetido'),
            ('91','Archivo Ilegible'),
            ('99','Envio Rechazado - Otros')
        ],string="Estado de Recepcion del Envio")
    estado_recep_glosa = fields.Char(string="Información Adicional del Estado de Recepción")
    sii_send_file_name = fields.Char(string="Send File Name")
    responsable_envio = fields.Many2one('res.users')

    def _acortar_str(self, texto, size=1):
        c = 0
        cadena = ""
        while c < size and c < len(texto):
            cadena += texto[c]
            c += 1
        return cadena

    @api.multi
    def action_done(self):
        res = super(stock_picking, self).action_done()
        for s in self:
            if not s.use_documents:
                continue
            if not s.sii_document_number and s.location_id.sequence_id.is_dte:
                s.sii_document_number = s.location_id.sequence_id.next_by_id()
                document_number = (s.location_id.sii_document_class_id.doc_code_prefix or '') + s.sii_document_number
                s.name = document_number
            if s.picking_type_id.code in ['outgoing', 'internal']: # @TODO diferenciar si es de salida o entrada para internal
                s.responsable_envio = self.env.uid
                s.sii_result = 'NoEnviado'
                s._timbrar()
                self.env['sii.cola_envio'].create({
                                            'doc_ids': [s.id],
                                            'model': 'stock.picking',
                                            'user_id': self.env.uid,
                                            'tipo_trabajo': 'pasivo',
                                            'date_time': (datetime.now() + timedelta(hours=12)),
                                            })
        return res

    @api.multi
    def do_dte_send_picking(self, n_atencion=None):
        ids = []
        if not isinstance(n_atencion, string_types):
            n_atencion = ''
        for rec in self:
            rec.responsable_envio = self.env.uid
            if rec.sii_result in ['', 'NoEnviado', 'Rechazado']:
                if not rec.sii_xml_request or rec.sii_result in [ 'Rechazado' ]:
                    rec._timbrar(n_atencion)
                rec.sii_result = "EnCola"
                ids.append(rec.id)
        if ids:
            self.env['sii.cola_envio'].create({
                                    'doc_ids': ids,
                                    'model':'stock.picking',
                                    'user_id':self.env.uid,
                                    'tipo_trabajo':'envio',
                                    'n_atencion': n_atencion
                                    })
    def _giros_emisor(self):
        giros_emisor = []
        for turn in self.company_id.company_activities_ids:
            giros_emisor.extend([{'Acteco': turn.code}])
        return giros_emisor

    def _id_doc(self, taxInclude=False, MntExe=0):
        IdDoc= collections.OrderedDict()
        IdDoc['TipoDTE'] = self.location_id.sii_document_class_id.sii_code
        IdDoc['Folio'] = self.get_folio()
        IdDoc['FchEmis'] = self.scheduled_date[:10]
        if self.transport_type and self.transport_type not in ['0']:
            IdDoc['TipoDespacho'] = self.transport_type
        IdDoc['IndTraslado'] = self.move_reason
        #if self.print_ticket:
        #    IdDoc['TpoImpresion'] = "N" #@TODO crear opcion de ticket
        if taxInclude and MntExe == 0 :
            IdDoc['MntBruto'] = 1
        #IdDoc['FmaPago'] = self.forma_pago or 1
        #IdDoc['FchVenc'] = self.date_due or datetime.strftime(datetime.now(), '%Y-%m-%d')
        return IdDoc

    def _emisor(self):
        Emisor= collections.OrderedDict()
        Emisor['RUTEmisor'] = self.format_vat(self.company_id.vat)
        Emisor['RznSoc'] = self.company_id.partner_id.name
        Emisor['GiroEmis'] = self._acortar_str(self.company_id.activity_description.name, 80)
        Emisor['Telefono'] = self._acortar_str(self.company_id.phone or '', 20)
        Emisor['CorreoEmisor'] = self.company_id.dte_email
        Emisor['item'] = self._giros_emisor()
        if self.location_id.sii_code:
            Emisor['CdgSIISucur'] = self.location_id.sii_code
        Emisor['DirOrigen'] = self.company_id.street + ' ' +(self.company_id.street2 or '')
        Emisor['CmnaOrigen'] = self.company_id.city_id.name or ''
        Emisor['CiudadOrigen'] = self.company_id.city or ''
        return Emisor

    def _receptor(self):
        Receptor = collections.OrderedDict()
        partner_id = self.partner_id or self.company_id.partner_id
        if not partner_id.commercial_partner_id.vat :
            raise UserError("Debe Ingresar RUT Receptor")
        Receptor['RUTRecep'] = self.format_vat(partner_id.commercial_partner_id.vat)
        Receptor['RznSocRecep'] = self._acortar_str(partner_id.commercial_partner_id.name, 100)
        activity_description = self.activity_description or partner_id.activity_description
        if not activity_description:
            raise UserError(_('Seleccione giro del partner'))
        Receptor['GiroRecep'] = self._acortar_str(activity_description.name, 40)
        if partner_id.commercial_partner_id.phone:
            Receptor['Contacto'] = partner_id.commercial_partner_id.phone
        if partner_id.commercial_partner_id.dte_email:
            Receptor['CorreoRecep'] = partner_id.commercial_partner_id.dte_email
        Receptor['DirRecep'] = (partner_id.commercial_partner_id.street) + ' ' + ((partner_id.commercial_partner_id.street2) or '')
        Receptor['CmnaRecep'] = partner_id.commercial_partner_id.city_id.name
        Receptor['CiudadRecep'] = partner_id.commercial_partner_id.city
        return Receptor

    def _transporte(self):
        Transporte = collections.OrderedDict()
        if self.patente:
            Transporte['Patente'] = self.patente[:8]
        elif self.vehicle:
            Transporte['Patente'] = self.vehicle.matricula or ''
        if self.transport_type in ['2','3'] and self.chofer:
            if not self.chofer.vat:
                raise UserError("Debe llenar los datos del chofer")
            if self.transport_type == '2':
                Transporte['RUTTrans'] = self.format_vat(self.company_id.vat)
            else:
                if not self.carrier_id.partner_id.vat:
                    raise UserError("Debe especificar el RUT del transportista, en su ficha de partner")
                Transporte['RUTTrans'] = self.format_vat(self.carrier_id.partner_id.vat)
            if self.chofer:
                Transporte['Chofer'] = collections.OrderedDict()
                Transporte['Chofer']['RUTChofer'] = self.format_vat(self.chofer.vat)
                Transporte['Chofer']['NombreChofer'] = self.chofer.name[:30]
        partner_id = self.partner_id or self.company_id.partner_id
        Transporte['DirDest'] = (partner_id.street or '')+ ' '+ (partner_id.street2 or '')
        Transporte['CmnaDest'] = partner_id.state_id.name or ''
        Transporte['CiudadDest'] = partner_id.city or ''
        #@TODO SUb Area Aduana
        return Transporte

    def _totales(self, MntExe=0, no_product=False, taxInclude=False):
        Totales = collections.OrderedDict()
        IVA = 19
        for line in self.move_lines:
            if line.move_line_tax_ids:
                for t in line.move_line_tax_ids:
                    IVA = t.amount
        if IVA > 0 and not no_product:
            Totales['MntNeto'] = int(round(self.amount_untaxed, 0))
            Totales['TasaIVA'] = round(IVA,2)
            Totales['IVA'] = int(round(self.amount_tax, 0))

        monto_total = int(round(self.amount_total, 0))
        if no_product:
            monto_total = 0
        Totales['MntTotal'] = monto_total
        return Totales

    def _encabezado(self, MntExe=0, no_product=False, taxInclude=False):
        Encabezado = collections.OrderedDict()
        Encabezado['IdDoc'] = self._id_doc(taxInclude, MntExe)
        Encabezado['Emisor'] = self._emisor()
        Encabezado['Receptor'] = self._receptor()
        Encabezado['Transporte'] = self._transporte()
        Encabezado['Totales'] = self._totales(MntExe, no_product)
        return Encabezado

    @api.multi
    def get_barcode(self, no_product=False):
        partner_id = self.partner_id or self.company_id.partner_id
        ted = False
        RutEmisor = self.format_vat(self.company_id.vat)
        result['TED']['DD']['RE'] = RutEmisor
        result['TED']['DD']['TD'] = self.location_id.sii_document_class_id.sii_code
        result['TED']['DD']['F']  = self.get_folio()
        result['TED']['DD']['FE'] = self.scheduled_date[:10]
        if not partner_id.commercial_partner_id.vat:
            raise UserError(_("Fill Partner VAT"))
        result['TED']['DD']['RR'] = self.format_vat(partner_id.commercial_partner_id.vat)
        result['TED']['DD']['RSR'] = self._acortar_str(partner_id.commercial_partner_id.name,40)
        result['TED']['DD']['MNT'] = int(round(self.amount_total))
        if no_product:
            result['TED']['DD']['MNT'] = 0
        for line in self.move_lines:
            result['TED']['DD']['IT1'] = self._acortar_str(line.product_id.name,40)
            if line.product_id.default_code:
                result['TED']['DD']['IT1'] = self._acortar_str(line.product_id.name.replace('['+line.product_id.default_code+'] ',''),40)
            break

        resultcaf = self.location_id.sequence_id.get_caf_file()
        result['TED']['DD']['CAF'] = resultcaf['AUTORIZACION']['CAF']
        if RutEmisor != result['TED']['DD']['CAF']['DA']['RE']:
            raise UserError(_('NO coincide el Dueño del CAF : %s con el emisor Seleccionado: %s' %(result['TED']['DD']['CAF']['DA']['RE'], RutEmisor)))
        dte = result['TED']['DD']
        timestamp = self.time_stamp()
        if date( int(timestamp[:4]), int(timestamp[5:7]), int(timestamp[8:10])) < date(int(self.date[:4]), int(self.date[5:7]), int(self.date[8:10])):
            raise UserError("La fecha de timbraje no puede ser menor a la fecha de emisión del documento")
        dte['TSTED'] = timestamp
        dicttoxml.set_debug(False)
        ddxml = '<DD>'+dicttoxml.dicttoxml(
            dte, root=False, attr_type=False).decode().replace(
            '<key name="@version">1.0</key>','',1).replace(
            '><key name="@version">1.0</key>',' version="1.0">',1).replace(
            '><key name="@algoritmo">SHA1withRSA</key>',
            ' algoritmo="SHA1withRSA">').replace(
            '<key name="#text">','').replace(
            '</key>','').replace('<CAF>','<CAF version="1.0">')+'</DD>'
        keypriv = resultcaf['AUTORIZACION']['RSASK'].replace('\t','')
        root = etree.XML( ddxml )
        ddxml = etree.tostring(root)
        frmt = self.signmessage(ddxml, keypriv)
        ted = (
            '''<TED version="1.0">{}<FRMT algoritmo="SHA1withRSA">{}\
</FRMT></TED>''').format(ddxml.decode(), frmt)
        self.sii_barcode = ted
        image = False
        if ted:
            barcodefile = BytesIO()
            image = self.pdf417bc(ted)
            image.save(barcodefile,'PNG')
            data = barcodefile.getvalue()
            self.sii_barcode_img = base64.b64encode(data)
        ted  += '<TmstFirma>{}</TmstFirma>'.format(timestamp)
        return ted

    def _picking_lines(self):
        line_number = 1
        picking_lines = []
        MntExe = 0
        for line in self.move_lines:
            no_product = False
            if line.product_id.default_code == 'NO_PRODUCT':
                no_product = True
            lines = collections.OrderedDict()
            lines['NroLinDet'] = line_number
            if line.product_id.default_code and not no_product:
                lines['CdgItem'] = collections.OrderedDict()
                lines['CdgItem']['TpoCodigo'] = 'INT1'
                lines['CdgItem']['VlrCodigo'] = line.product_id.default_code
            taxInclude = False
            if line.move_line_tax_ids:
                for t in line.move_line_tax_ids:
                    taxInclude = t.price_include
                    if t.amount == 0 or t.sii_code in [0]:#@TODO mejor manera de identificar exento de afecto
                        lines['IndExe'] = 1
                        MntExe += int(round(line.subtotal, 0))
            lines['NmbItem'] = self._acortar_str(line.product_id.name,80) #
            lines['DscItem'] = self._acortar_str(line.name, 1000) #descripción más extenza
            if line.product_id.default_code:
                lines['NmbItem'] = self._acortar_str(line.product_id.name.replace('['+line.product_id.default_code+'] ',''),80)
            qty = round(line.quantity_done, 4)
            if qty <=0:
                qty = round(line.product_uom_qty, 4)
                if qty <=0:
                    raise UserError("¡No puede ser menor o igual que 0!, tiene líneas con cantidad realiada 0")
            if not no_product:
                lines['QtyItem'] = qty
            if self.move_reason in ['5']:
                no_product = True
            if not no_product:
                lines['UnmdItem'] = line.product_uom.name[:4]
                if line.precio_unitario > 0:
                    lines['PrcItem'] = round(line.precio_unitario, 4)
            if line.discount > 0:
                lines['DescuentoPct'] = line.discount
                lines['DescuentoMonto'] = int(round((((line.discount / 100) * lines['PrcItem'])* qty)))
            if not no_product :
                lines['MontoItem'] = int(round(line.subtotal,0))
            if no_product:
                lines['MontoItem'] = 0
            line_number += 1
            picking_lines.extend([{'Detalle': lines}])
            if 'IndExe' in lines:
                taxInclude = False
        if len(picking_lines) == 0:
            raise UserError(_('No se puede emitir una guía sin líneas'))
        return {
                'picking_lines': picking_lines,
                'MntExe':MntExe,
                'no_product':no_product,
                'tax_include': taxInclude,
                }

    def _dte(self, n_atencion=None):
        dte = collections.OrderedDict()
        picking_lines = self._picking_lines()
        dte['Encabezado'] = self._encabezado(picking_lines['MntExe'], picking_lines['no_product'], picking_lines['tax_include'])
        count = 0
        lin_ref = 1
        ref_lines = []
        if self.company_id.dte_service_provider == 'SIICERT' and isinstance(n_atencion, string_types):
            ref_line = {}
            ref_line = collections.OrderedDict()
            ref_line['NroLinRef'] = lin_ref
            count = count +1
            ref_line['TpoDocRef'] = "SET"
            ref_line['FolioRef'] = self.get_folio()
            ref_line['FchRef'] = datetime.strftime(datetime.now(), '%Y-%m-%d')
            ref_line['RazonRef'] = "CASO "+n_atencion+"-" + str(self.sii_batch_number)
            lin_ref = 2
            ref_lines.extend([{'Referencia':ref_line}])
        for ref in self.reference:
            if ref.sii_referencia_TpoDocRef.sii_code in ['33','34']:#@TODO Mejorar Búsqueda
                inv = self.env["account.invoice"].search([('sii_document_number','=',str(ref.origen))])
            ref_line = {}
            ref_line = collections.OrderedDict()
            ref_line['NroLinRef'] = lin_ref
            if  ref.sii_referencia_TpoDocRef:
                ref_line['TpoDocRef'] = ref.sii_referencia_TpoDocRef.sii_code
                ref_line['FolioRef'] = ref.origen
                ref_line['FchRef'] = datetime.strftime(datetime.now(), '%Y-%m-%d')
                if ref.date:
                    ref_line['FchRef'] = ref.date
            ref_lines.extend([{'Referencia':ref_line}])
        dte['item'] = picking_lines['picking_lines']
        dte['reflines'] = ref_lines
        dte['TEDd'] = self.get_barcode(picking_lines['no_product'])
        return dte

    def _tpo_dte(self):
        tpo_dte = "Documento"
        return tpo_dte

    def _timbrar(self, n_atencion=None):
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
        dte = collections.OrderedDict()

        folio = self.get_folio()
        tpo_dte = self._tpo_dte()
        dte = collections.OrderedDict()
        doc_id_number = "F{}T{}".format(
            folio, self.location_id.sii_document_class_id.sii_code)
        doc_id = '<Documento ID="{}">'.format(doc_id_number)
        dte['Documento ID'] = self._dte(n_atencion)
        xml = self.env['account.invoice']._dte_to_xml(dte, tpo_dte)
        root = etree.XML( xml )
        xml_pret = etree.tostring(
                root,
                pretty_print=True
            ).decode().replace(
                    '<' + tpo_dte + '_ID>',
                    doc_id
                ).replace('</' + tpo_dte + '_ID>', '</' + tpo_dte + '>')
        envelope_efact = self.create_template_doc(xml_pret)
        einvoice = self.env['account.invoice'].sign_full_xml(
                envelope_efact,
                signature_d['priv_key'],
                self.split_cert(certp),
                doc_id_number,
            )
        self.sii_xml_dte = einvoice

    @api.multi
    def do_dte_send(self, n_atencion=False):
        DTEs = {}
        count = 0
        company_id = False
        for rec in self.with_context(lang='es_CL'):
            try:
                signature_d = self.get_digital_signature(rec.company_id)
            except:
                raise UserError(_('''There is no Signer Person with an \
            authorized signature for you in the system. Please make sure that \
            'user_signature_key' module has been installed and enable a digital \
            signature, for you or make the signer to authorize you to use his \
            signature.'''))
            certp = signature_d['cert'].replace(
                BC, '').replace(EC, '').replace('\n', '')
            if rec.company_id.dte_service_provider == 'SIICERT': # si ha sido timbrado offline, no se puede volver a timbrar
                rec._timbrar(n_atencion)
            DTEs.update( {str(rec.sii_document_number): rec.sii_xml_dte})
            if not company_id:
                company_id = rec.company_id
            elif company_id.id != rec.company_id.id:
                raise UserError("Está combinando compañías")
            company_id = rec.company_id
        file_name = 'T52'
        dtes=""
        SubTotDTE = ''
        resol_data = self.get_resolution_data(company_id)
        signature_d = self.get_digital_signature(company_id)
        RUTEmisor = self.format_vat(company_id.vat)
        NroDte = 0
        for rec_id,  documento in DTEs.items():
            dtes += '\n'+documento
            NroDte += 1
            file_name += 'F' + rec_id
        SubTotDTE += '<SubTotDTE>\n<TpoDTE>52</TpoDTE>\n<NroDTE>'+str(NroDte)+'</NroDTE>\n</SubTotDTE>\n'
        RUTRecep = "60803000-K" # RUT SII
        dtes = self.create_template_envio( RUTEmisor, RUTRecep,
            resol_data['dte_resolution_date'],
            resol_data['dte_resolution_number'],
            self.time_stamp(), dtes, signature_d,SubTotDTE )
        envio_dte  = self.create_template_env(dtes)
        envio_dte = self.env['account.invoice'].sign_full_xml(
            envio_dte.replace('<?xml version="1.0" encoding="ISO-8859-1"?>\n', ''),
            signature_d['priv_key'],
            certp,
            'SetDoc',
            'env')
        result = self.send_xml_file(envio_dte, file_name, company_id)
        if result:
            for rec in self:
                rec.write({
                        'sii_xml_response':result['sii_xml_response'],
                        'sii_send_ident':result['sii_send_ident'],
                        'sii_result': result['sii_result'],
                        'sii_xml_request':envio_dte,
                        'sii_send_file_name' : file_name,
                        })

    def _get_send_status(self, track_id, signature_d,token):
        url = server_url[self.company_id.dte_service_provider] + 'QueryEstUp.jws?WSDL'
        _server = Client(url)
        rut = self.format_vat(self.company_id.vat, True)
        respuesta = _server.service.getEstUp(rut[:8], str(rut[-1]),track_id,token)
        self.sii_receipt = respuesta
        resp = xmltodict.parse(respuesta)
        status = False
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "-11":
            status =  {'warning':{'title':_('Error -11'), 'message': _("Error -11: Espere a que sea aceptado por el SII, intente en 5s más")}}
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "EPR":
            self.sii_result = "Proceso"
            if resp['SII:RESPUESTA']['SII:RESP_BODY']['RECHAZADOS'] == "1":
                self.sii_result = "Rechazado"
        elif resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "RCT":
            self.sii_result = "Rechazado"
            status = {'warning':{'title':_('Error RCT'), 'message': _(resp['SII:RESPUESTA']['GLOSA'])}}
        return status

    def _get_dte_status(self, signature_d, token):
        partner_id = self.partner_id or self.company_id.partner_id
        url = server_url[self.company_id.dte_service_provider] + 'QueryEstDte.jws?WSDL'
        _server = Client(url)
        receptor = self.format_vat(partner_id.commercial_partner_id.vat, True)
        scheduled_date = datetime.strptime(self.scheduled_date[:10], "%Y-%m-%d").strftime("%d-%m-%Y")
        total = str(int(round(self.amount_total,0)))
        sii_code = str(self.location_id.sii_document_class_id.sii_code)
        respuesta = _server.service.getEstDte(signature_d['subject_serial_number'][:8],
                                      str(signature_d['subject_serial_number'][-1]),
                                      self.company_id.vat[2:-1],
                                      self.company_id.vat[-1],
                                      receptor[:8],
                                      receptor[-1],
                                      sii_code,
                                      str(self.sii_document_number),
                                      scheduled_date,
                                      total,token)
        self.sii_message = respuesta
        resp = xmltodict.parse(respuesta)
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == '2':
            status = {'warning':{'title':_("Error code: 2"), 'message': _(resp['SII:RESPUESTA']['SII:RESP_HDR']['GLOSA'])}}
            return status
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "EPR":
            self.sii_result = "Proceso"
            if resp['SII:RESPUESTA']['SII:RESP_BODY']['RECHAZADOS'] == "1":
                self.sii_result = "Rechazado"
            if resp['SII:RESPUESTA']['SII:RESP_BODY']['REPARO'] == "1":
                self.sii_result = "Reparo"
        elif resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "RCT":
            self.sii_result = "Rechazado"

    @api.multi
    def ask_for_dte_status(self, silent=False):
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
            if silent:
                _logger.info("Error Creación de token")
                return
            raise UserError(connection_status[response.e])
        if not self.sii_send_ident:
            _logger.info(self.sii_document_number)
            msg = 'No se ha enviado aún el documento %s, aún está en cola de envío interna en odoo'
            if silent:
                _logger.info(msg)
                return
            raise UserError( msg )
        xml_response = xmltodict.parse(self.sii_xml_response)
        if self.sii_result == 'Enviado':
            status = self._get_send_status(self.sii_send_ident, signature_d, token)
            if self.sii_result != 'Proceso':
                return status
        return self._get_dte_status(signature_d, token)
