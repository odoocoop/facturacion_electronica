# -*- coding: utf-8 -*-
from odoo import models, api
from lxml import etree
from base64 import b64decode
import logging
_logger = logging.getLogger(__name__)

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


class ProcessMails(models.Model):
    _inherit = "mail.message"

    def _parse_xml(self, string_xml):
        string_xml = b64decode(string_xml).decode('ISO-8859-1')
        xml = string_xml\
            .replace('<?xml version="1.0" encoding="ISO-8859-1"?>', '')\
            .replace('<?xml version="1.0" encoding="ISO-8859-1" ?>', '')
        xml = xml.replace(' xmlns="http://www.sii.cl/SiiDte"', '')
        parser = etree.XMLParser(remove_blank_text=True)
        return etree.fromstring(xml, parser=parser)

    def _format_rut(self, text):
            rut = text.replace('-', '')
            if int(rut[:-1]) < 10000000:
                rut = '0' + str(rut)
            return 'CL' + rut

    def _process_recepcion_comercial(self, doc, company_id, att):
        id_respuesta = doc.getparent().find('Caratula/IdRespuesta').text
        partner_id = self.env['res.partner'].search([
                ('vat', '=', self._format_rut(
                                    doc.find('RUTRecep').text)),
                ('parent_id', '=', False),
            ])
        inv = self.env['account.invoice'].sudo().search([
            ('document_class_id.sii_code', '=', doc.find(
                                    'TipoDTE').text),
            ('sii_document_number', '=', doc.find('Folio').text),
            ('company_id', '=', company_id.id),
            ('partner_id', '=', partner_id.id)
        ])
        resp = {
            'id_respuesta': id_respuesta,
            'recep_comercial': doc.find('EstadoDTE').text,
            'glosa': doc.find('EstadoDTEGlosa').text,
            'type': doc.tag,
            'attachment_id': att.id,
            'company_id': company_id.id,
            }
        resp_id = self.env['sii.respuesta.cliente'].sudo().create(resp)
        inv.respuesta_ids += resp_id

    def _process_recepcion_envio(self, el_root, company_id, att):
        el = el_root.find('ResultadoDTE')
        if el is not None:
            return self._process_recepcion_comercial(el, company_id, att)
        el = el_root.find('RecepcionEnvio')
        caratula = el_root.find('Caratula')
        resp_id = self.env['sii.respuesta.cliente'].sudo().search([
                ('exchange_id.name', '=',  el.find('NmbEnvio').text),
                ('company_id', '=', company_id.id),
            ])
        data = {
            'id_respuesta': caratula.find('IdRespuesta').text,
            'recep_envio': el.find('EstadoRecepEnv').text,
            'glosa': el.find('RecepEnvGlosa').text,
            'attachment_id': att.id
        }
        resp_id.write(data)
        for doc in el.findall('RecepcionDTE'):
            partner_id = self.env['res.partner'].search([
                ('vat', '=', self._format_rut(
                                    doc.find('RUTRecep').text)),
                ('parent_id', '=', False),
            ])
            inv = self.env['account.invoice'].sudo().search([
                ('document_class_id.sii_code', '=', doc.find(
                                        'TipoDTE').text),
                ('sii_document_number', '=', doc.find('Folio').text),
                ('company_id', '=', company_id.id),
                ('partner_id', '=', partner_id.id)
            ])
            resp = {
                'recep_dte': doc.find('EstadoRecepDTE').text,
                'glosa': doc.find('RecepDTEGlosa').text,
                'type': doc.tag,
                'company_id': company_id.id,
                }
            resp_id = self.env['sii.respuesta.cliente'].sudo().create(resp)
            inv.respuesta_ids += resp_id

    def _process_recepcion_mercaderias(self, el, company_id, att):
        for recibo in el.findall('Recibo'):
            doc = recibo.find("DocumentoRecibo")
            partner_id = self.env['res.partner'].search([
                ('vat', '=', self._format_rut(
                                    doc.find('RUTRecep').text)),
                ('parent_id', '=', False),
            ])
            inv = self.env['account.invoice'].sudo().search([
                ('document_class_id.sii_code', '=', doc.find(
                                        'TipoDTE').text),
                ('sii_document_number', '=', doc.find('Folio').text),
                ('company_id', '=', company_id.id),
                ('partner_id', '=', partner_id.id)
            ])
            resp = {
                'merc_recinto': doc.find('Recinto').text,
                'merc_fecha': doc.find('FchEmis').text,
                'merc_declaracion': doc.find('Declaracion').text,
                'merc_rut': doc.find('RutFirma').text,
                'type': doc.tag,
                'attachment_id': att.id,
                'company_id': company_id.id,
                }
            resp_id = self.env['sii.respuesta.cliente'].sudo().create(resp)
            inv.respuesta_ids += resp_id

    def _proccess_respuesta(self, el_root, att):
        el = el_root.find('Resultado')
        if el is None:
            el = el_root.find('SetRecibos')
        caratula = el.find('Caratula')
        rut_company = self._format_rut(caratula.find('RutRecibe').text)
        company_id = self.env['res.company'].sudo().search([
            ('vat', '=', rut_company),
        ])
        if el.tag == 'Resultado':
            self._process_recepcion_envio(el,
                                          company_id, att)
        elif el.tag == 'SetRecibo':
            self._process_recepcion_mercaderias(el,
                                                company_id, att)

    def _process_xml(self, att):
        el = self._parse_xml(att.datas)
        data = {
            'mail_id': self.id,
            'name': att.name,
            'attachment_id': att.id,
        }
        if el.tag == 'EnvioDTE':
            val = self.env['mail.message.dte'].sudo().create(data)
            val.pre_process()
        elif el.tag in ['RespuestaDTE', 'EnvioRecibos']:
            self._proccess_respuesta(el, att)

    @api.multi
    def process_mess(self):
        for att in self.attachment_ids:
            if not att.name:
                continue
            name = att.name.upper()
            if att.mimetype in ['text/plain'] and name.find('.XML') > -1:
                if not self.env['mail.message.dte'].search([
                                        ('name', '=', name)]):
                    self._process_xml(att)

    @api.model
    def create(self, vals):
        mail = super(ProcessMails, self).create(vals)
        if mail.message_type in ['email'] and mail.attachment_ids and \
                not mail.mail_server_id and mail.author_id != self.env.ref('base.partner_root'):
            mail.process_mess()
        return mail
