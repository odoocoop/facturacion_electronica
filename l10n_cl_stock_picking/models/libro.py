# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging
from lxml import etree
import pytz
_logger = logging.getLogger(__name__)

try:
    from facturacion_electronica import facturacion_electronica as fe
except Exception as e:
    _logger.warning("Problema al cargar Facturación electrónica: %s" % str(e))

try:
    from suds.client import Client
except:
    pass

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

    @api.multi
    def get_xml_file(self):
        return {
            'type' : 'ir.actions.act_url',
            'url': '/download/xml/libro_guia%s' % (self.id),
            'target': 'self',
        }

    @api.onchange('periodo_tributario')
    def _setName(self):
        if self.name:
            return
        if self.periodo_tributario and self.name:
            self.name += " " + self.periodo_tributario

    sii_xml_request = fields.Many2one(
            'sii.xml.envio',
            string='SII XML Request',
            copy=False)
    state = fields.Selection(
            [
                ('draft', 'Borrador'),
                ('NoEnviado', 'No Enviado'),
                ('EnCola', 'En Cola'),
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
    sii_result = fields.Selection(
            [
                ('draft', 'Borrador'),
                ('NoEnviado', 'No Enviado'),
                ('EnCola', 'En Cola'),
                ('Enviado', 'Enviado'),
                ('Aceptado', 'Aceptado'),
                ('Rechazado', 'Rechazado'),
                ('Reparo', 'Reparo'),
                ('Proceso', 'Proceso'),
                ('Reenviar', 'Reenviar'),
                ('Anulado', 'Anulado')
            ],
            related="state",
        )

    @api.multi
    def validar_libro(self):
        self._validar()
        return self.write({'state': 'NoEnviado'})

    def format_vat(self, value):
        if not value or value=='' or value == 0:
            value ="CL666666666"
            #@TODO opción de crear código de cliente en vez de rut genérico
        rut = value[:10] + '-' + value[10:]
        rut = rut.replace('CL0','').replace('CL','')
        return rut

    def _emisor(self):
        Emisor = {}
        Emisor['RUTEmisor'] = self.format_vat(self.company_id.vat)
        Emisor['RznSoc'] = self.company_id.name
        Emisor["Modo"] = "produccion" if self.company_id.dte_service_provider == 'SII'\
                  else 'certificacion'
        Emisor["NroResol"] = self.company_id.dte_resolution_number
        Emisor["FchResol"] = self.company_id.dte_resolution_date
        Emisor["ValorIva"] = 19
        return Emisor

    def _get_datos_empresa(self, company_id):
        signature_id = self.env.user.get_digital_signature(company_id)
        if not signature_id:
            raise UserError(_('''There are not a Signature Cert Available for this user, please upload your signature or tell to someelse.'''))
        emisor = self._emisor()
        return {
            "Emisor": emisor,
            "firma_electronica": signature_id.parametros_firma(),
        }

    def _validar(self):
        datos = self._get_datos_empresa(self.company_id)
        grupos = {}
        recs = self.with_context(lang='es_CL').move_ids
        for rec in recs:
            grupos.setdefault(rec.document_class_id.sii_code, [])
            grupos[rec.document_class_id.sii_code].append(rec._dte())
        datos['Libro'] = {
            "PeriodoTributario": self.periodo_tributario,
            "TipoOperacion": 'GUIA',
            "TipoLibro": self.tipo_libro,
            "FolioNotificacion": self.folio_notificacion,
            "TipoEnvio": self.tipo_envio,
            "Documento": [{'TipoDTE': k, 'documentos': v} for k, v in grupos.items()]
        }
        datos['test'] = True
        result = fe.libro(datos)
        envio_dte = result['sii_xml_request']
        doc_id = '%s_%s' % ('GUIA', self.periodo_tributario)
        self.sii_xml_request = self.env['sii.xml.envio'].create({
            'xml_envio': envio_dte,
            'name': doc_id,
            'company_id': self.company_id.id,
        }).id

    @api.multi
    def do_dte_send_book(self):
        if self.state not in ['draft', 'NoEnviado', 'Rechazado']:
            raise UserError("El Libro ya ha sido enviado")
        if not self.sii_xml_request or self.sii_xml_request.state == "Rechazado":
            if self.sii_xml_request:
                self.sii_xml_request.unlink()
            self._validar()
        self.env['sii.cola_envio'].create(
                    {
                        'company_id': self.company_id.id,
                        'doc_ids': [self.id],
                        'model': 'stock.picking.book',
                        'user_id': self.env.user.id,
                        'tipo_trabajo': 'envio',
                    })
        self.state = 'EnCola'

    def do_dte_send(self, n_atencion=''):
        if self.sii_xml_request and self.sii_xml_request.state == "Rechazado":
            self.sii_xml_request.unlink()
            self._validar()
            self.sii_xml_request.state = 'NoEnviado'
        if self.state in ['NoEnviado', 'EnCola']:
            self.sii_xml_request.send_xml()
        return self.sii_xml_request

    def _get_send_status(self):
        self.sii_xml_request.get_send_status()
        if self.sii_xml_request.state == 'Aceptado':
            self.state = "Proceso"
        else:
            self.state = self.sii_xml_request.state

    @api.multi
    def ask_for_dte_status(self):
        self._get_send_status()

    def get_sii_result(self):
        for r in self:
            if r.sii_xml_request.state == 'NoEnviado':
                r.state = 'EnCola'
                continue
            r.state = r.sii_xml_request.state
