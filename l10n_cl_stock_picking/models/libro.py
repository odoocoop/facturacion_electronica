# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging
from lxml import etree
from lxml.etree import Element, SubElement
from lxml import objectify
from lxml.etree import XMLSyntaxError
import pytz
import collections

_logger = logging.getLogger(__name__)

try:
    from suds.client import Client
except:
    pass
try:
    import urllib3
    pool = urllib3.PoolManager()
except:
    pass
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

server_url = {'SIICERT':'https://maullin.sii.cl/DTEWS/','SII':'https://palena.sii.cl/DTEWS/'}

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

    def create_template_envio(self, RutEmisor, PeriodoTributario, FchResol, NroResol, EnvioDTE,subject_serial_number,TipoLibro='MENSUAL',TipoEnvio='TOTAL',FolioNotificacion="123", IdEnvio='SetDoc'):
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
'''.format(RutEmisor, subject_serial_number, PeriodoTributario,
           FchResol, NroResol, TipoLibro,TipoEnvio,FolioNotificacion, EnvioDTE,IdEnvio)
        return xml

    def time_stamp(self, formato='%Y-%m-%dT%H:%M:%S'):
        tz = pytz.timezone('America/Santiago')
        return datetime.now(tz).strftime(formato)

    def get_seed(self, company_id):
        return self.env['account.invoice'].get_seed(company_id)

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

    def sign_full_xml(self, message, uri, type='libro'):
        user_id = self.env.user
        signature_id = user_id.get_digital_signature(self.company_id)
        if not signature_id:
            raise UserError(_('''There are not a Signature Cert Available for this user, please upload your signature or tell to someelse.'''))
        return signature_id.firmar(message, uri, type)

    def get_resolution_data(self, comp_id):
        resolution_data = {
            'dte_resolution_date': comp_id.dte_resolution_date,
            'dte_resolution_number': comp_id.dte_resolution_number}
        return resolution_data

    @api.multi
    def send_xml_file(self, envio_dte=None, file_name="envio",company_id=False):
        signature_id = self.env.user.get_digital_signature(company_id)
        if not signature_id:
            raise UserError(_('''There are not a Signature Cert Available for this user, pleaseupload your signature or tell to someelse.'''))
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
        params['rutSender'] = signature_id.subject_serial_number[:8]
        params['dvSender'] = signature_id.subject_serial_number[-1]
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

    @api.onchange('periodo_tributario')
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
        signature_id = self.env.user.get_digital_signature(company_id)
        if not signature_id:
            raise UserError(_('''There are not a Signature Cert Available for this user, pleaseupload your signature or tell to someelse.'''))
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
            xml, signature_id.subject_serial_number,
            self.tipo_libro,self.tipo_envio,self.folio_notificacion, doc_id)
        xml  = self.create_template_env(libro)
        root = etree.XML( xml )
        envio_dte = etree.tostring(root, pretty_print=True).decode()\
                .replace('<item>','\n').replace('</item>','').replace('<itemTraslado>','').replace('</itemTraslado>','\n')
        envio_dte = self.sign_full_xml(
            envio_dte,
            doc_id,
            'libro_guia')
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

    def _get_send_status(self, track_id, token):
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

    def _get_dte_status(self, token):
        signature_id = self.env.user.get_digital_signature(self.company_id)
        url = server_url[self.company_id.dte_service_provider] + 'QueryEstDte.jws?WSDL'
        ns = 'urn:'+ server_url[self.company_id.dte_service_provider] + 'QueryEstDte.jws'
        _server = Client(url, ns)
        receptor = self.format_vat(self.partner_id.vat or self.company_id.partner_id.vat)
        date_invoice = datetime.strptime(self.date_invoice, "%Y-%m-%d").strftime("%d-%m-%Y")
        respuesta = _server.getEstDte(signature_id.subject_serial_number[:8], str(signature_id.subject_serial_number[-1]),
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
            signature_id = self.env.user.get_digital_signature(self.company_id)
            seed = self.get_seed(self.company_id)
            template_string = self.create_template_seed(seed)
            seed_firmado = self.sign_seed(
                template_string, signature_id.priv_key,
                signature_id.cert)
            token = self.get_token(seed_firmado,self.company_id)
        except:
            raise UserError(connection_status[response.e])
        xml_response = xmltodict.parse(self.sii_xml_response)
        if self.state == 'Enviado':
            status = self._get_send_status(self.sii_send_ident, token)
            if self.state != 'Proceso':
                return status
        return self._get_dte_status(token)
