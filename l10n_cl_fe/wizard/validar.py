# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError
import logging
import base64
_logger = logging.getLogger(__name__)

try:
    from facturacion_electronica import facturacion_electronica as fe
except:
    _logger.warning('No se ha podido cargar fe')

class ValidarDTEWizard(models.TransientModel):
    _name = 'sii.dte.validar.wizard'
    _description = 'SII XML from Provider'

    def _get_docs(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        return [(6, 0, active_ids)]

    action = fields.Selection(
        [
            ('receipt', 'Recibo de mercaderías'),
            ('validate', 'Aprobar comercialmente'),
        ],
        string="Acción",
        default="validate",
    )
    invoice_ids = fields.Many2many(
        'account.invoice',
        string="Facturas",
        default=_get_docs,
    )
    option = fields.Selection(
        [
            ('accept', 'Aceptar'),
            ('reject', 'Rechazar'),
        ],
        string="Opción",
    )

    @api.multi
    def confirm(self):
        #if self.action == 'validate':
        self.do_receipt()
        self.do_validar_comercial()
        #   _logger.info("ee")

    def send_message(self, message="RCT"):
        id = self.document_id.number or self.inv.ref
        sii_document_class = self.document_id.document_class_id or self.inv.document_class_id.sii_code

    def _create_attachment(self, xml, name, id=False, model='account.invoice'):
        data = base64.b64encode(xml.encode('ISO-8859-1'))
        filename = (name).replace(' ', '')
        url_path = '/web/binary/download_document?model=' + model + '\
    &field=sii_xml_request&id=%s&filename=%s' % (id, filename)
        att = self.env['ir.attachment'].search(
            [
                ('name', '=', filename),
                ('res_id', '=', id),
                ('res_model', '=',model)
            ],
            limit=1,
        )
        if att:
            return att
        values = dict(
                        name=filename,
                        datas_fname=filename,
                        url=url_path,
                        res_model=model,
                        res_id=id,
                        type='binary',
                        datas=data,
                    )
        att = self.env['ir.attachment'].create(values)
        return att

    def _emisor(self, company_id):
        Emisor = {}
        Emisor['RUTEmisor'] = company_id.document_number
        Emisor['RznSoc'] = company_id.partner_id.name
        Emisor['GiroEmis'] = company_id.activity_description.name
        if company_id.phone:
            Emisor['Telefono'] = company_id.phone
        Emisor['CorreoEmisor'] = company_id.dte_email_id.name_get()[0][1]
        #Emisor['Actecos'] = self._actecos_emisor()
        Emisor['DirOrigen'] = company_id.street + ' ' + (company_id.street2 or '')
        if not company_id.city_id:
            raise UserError("Debe ingresar la Comuna de compañía emisora")
        Emisor['CmnaOrigen'] = company_id.city_id.name
        if not company_id.city:
            raise UserError("Debe ingresar la Ciudad de compañía emisora")
        Emisor['CiudadOrigen'] = company_id.city
        Emisor["Modo"] = "produccion" if company_id.dte_service_provider == 'SII'\
                  else 'certificacion'
        Emisor["NroResol"] = company_id.dte_resolution_number
        Emisor["FchResol"] = company_id.dte_resolution_date
        return Emisor

    def _get_datos_empresa(self, company_id):
        signature_id = self.env.user.get_digital_signature(company_id)
        if not signature_id:
            raise UserError(_('''There are not a Signature Cert Available for this user, please upload your signature or tell to someelse.'''))
        emisor = self._emisor(company_id)
        return {
            "Emisor": emisor,
            "firma_electronica": signature_id.parametros_firma(),
        }

    def do_reject(self, document_ids):
        inv_obj = self.env['account.invoice']
        id_seq = self.env.ref('l10n_cl_fe.response_sequence')
        IdRespuesta = id_seq.next_by_id()
        NroDetalles = 1
        for doc in document_ids:
            datos = self._get_datos_empresa(doc.company_id)
            ''' @TODO separar estos dos'''
            dte = {
                'xml': doc.xml,
                'CodEnvio': IdRespuesta,
            }
            datos['filename'] = 'rechazo_comercial_%s.xml' % str(IdRespuesta)
            datos["ValidacionCom"] = {
                'IdRespuesta': IdRespuesta,
                'NroDetalles': NroDetalles,
                "RutResponde": doc.company_id.document_number,
                'NmbContacto': self.env.user.partner_id.name,
                'FonoContacto': self.env.user.partner_id.phone,
                'MailContacto': self.env.user.partner_id.email,
                "xml_dte": dte,
                'EstadoDTE': 2,
                'EstadoDTEGlosa': 'Rechazo Absoluto',
                'CodRchDsc': -1,
            }
            resp = fe.validacion_comercial(datos)
            att = self._create_attachment(
                resp['respuesta_xml'],
                resp['nombre_xml'],
            )
            partners = doc.partner_id.ids
            dte_email_id = doc.company_id.dte_email_id or self.env.user.company_id.dte_email_id
            values = {
                        'res_id': doc.id,
                        'email_from': dte_email_id.name_get()[0][1],
                        'email_to': doc.dte_id.sudo().mail_id.email_from ,
                        'auto_delete': False,
                        'model': "mail.message.dte.document",
                        'body': 'XML de Respuesta DTE, Estado: %s , Glosa: %s ' % (resp['EstadoDTE'], resp['EstadoDTEGlosa']),
                        'subject': 'XML de Respuesta DTE',
                        'attachment_ids': [[6, 0, att.ids]],
                    }
            send_mail = self.env['mail.mail'].create(values)
            send_mail.send()
            doc.set_dte_claim(claim='RCD')

    def do_validar_comercial(self):
        id_seq = self.env.ref('l10n_cl_fe.response_sequence')
        IdRespuesta = id_seq.next_by_id()
        NroDetalles = 1
        for inv in self.invoice_ids:
            if inv.claim in ['ACD', 'RCD'] or inv.type in ['out_invoice', 'out_refund']:
                continue
            datos = inv._get_datos_empresa(inv.company_id)
            dte = inv._dte()
            ''' @TODO separar estos dos'''
            dte['CodEnvio'] = IdRespuesta
            datos['filename'] = 'validacion_comercial_%s.xml' % str(IdRespuesta)
            datos["ValidacionCom"] = {
                'IdRespuesta': IdRespuesta,
                'NroDetalles': NroDetalles,
                "RutResponde": inv.format_vat(
                                inv.company_id.vat),
                "RutRecibe": inv.partner_id.commercial_partner_id.document_number,
                'NmbContacto': self.env.user.partner_id.name,
                'FonoContacto': self.env.user.partner_id.phone,
                'MailContacto': self.env.user.partner_id.email,
                "Receptor": {
                	    "RUTRecep": inv.partner_id.commercial_partner_id.document_number,
                },
                "DTEs": [dte],
            }
            resp = fe.validacion_comercial(datos)
            inv.sii_message = resp['respuesta_xml']
            att = self._create_attachment(
                resp['respuesta_xml'],
                resp['nombre_xml'],
            )
            dte_email_id = inv.company_id.dte_email_id or self.env.user.company_id.dte_email_id
            values = {
                        'res_id': inv.id,
                        'email_from': dte_email_id.name_get()[0][1],
                        'email_to': inv.partner_id.commercial_partner_id.dte_email,
                        'auto_delete': False,
                        'model': "account.invoice",
                        'body': 'XML de Validación Comercial, Estado: %s, Glosa: %s' % (resp['EstadoDTE'], resp['EstadoDTEGlosa']),
                        'subject': 'XML de Validación Comercial',
                        'attachment_ids': [[6, 0, att.ids]],
                    }
            send_mail = self.env['mail.mail'].create(values)
            send_mail.send()
            try:
                inv.set_dte_claim(claim='ACD')
            except Exception as e:
                _logger.warning("Error al setear Reclamo %s" %str(e))
            try:
                inv.get_dte_claim()
            except:
                _logger.warning("@TODO crear código que encole la respuesta")

    @api.multi
    def do_receipt(self):
        message = ""
        for inv in self.invoice_ids:
            if inv.claim in ['ACD', 'RCD']:
                continue
            datos = inv._get_datos_empresa(inv.company_id)
            datos["RecepcionMer"] = {
                "RutResponde": inv.format_vat(
                                inv.company_id.vat),
                "RutRecibe": inv.partner_id.commercial_partner_id.document_number,
                'Recinto': inv.company_id.street,
                'NmbContacto': self.env.user.partner_id.name,
                'FonoContacto': self.env.user.partner_id.phone,
                'MailContacto': self.env.user.partner_id.email,
                "Receptor": {
                	    "RUTRecep": inv.partner_id.commercial_partner_id.document_number,
                },
                "DTEs": [inv._dte()],
            }
            resp = fe.recepcion_mercaderias(datos)
            inv.sii_message = resp['respuesta_xml']
            att = self._create_attachment(
                resp['respuesta_xml'],
                resp['nombre_xml'],
            )
            dte_email_id = inv.company_id.dte_email_id or self.env.user.company_id.dte_email_id
            values = {
                        'res_id': inv.id,
                        'email_from': dte_email_id.name_get()[0][1],
                        'email_to': inv.partner_id.commercial_partner_id.dte_email,
                        'auto_delete': False,
                        'model': "account.invoice",
                        'body': 'XML de Recepción de Mercaderías\n %s' % (message),
                        'subject': 'XML de Recepción de Documento',
                        'attachment_ids': [[6, 0, att.ids]],
                    }
            send_mail = self.env['mail.mail'].create(values)
            send_mail.send()
            try:
                inv.set_dte_claim(claim='ERM')
            except Exception as e:
                _logger.warning("Error al setear Reclamo %s" %str(e))
            try:
                inv.get_dte_claim()
            except:
                _logger.warning("@TODO crear código que encole la respuesta")
