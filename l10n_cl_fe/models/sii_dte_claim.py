# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import _
import base64
import logging
_logger = logging.getLogger(__name__)
try:
    from suds.client import Client
except Exception as e:
    _logger.warning("Problemas al cargar suds %s" %str(e))
try:
    from facturacion_electronica import facturacion_electronica as fe
except:
    _logger.warning('No se ha podido cargar fe')


class DTEClaim(models.Model):
    _name = 'sii.dte.claim'
    _description = "DTE CLAIM"
    _inherit = ['mail.thread']

    document_id = fields.Many2one(
        'mail.message.dte.document',
        string="Documento",
        ondelete='cascade',
    )
    invoice_id = fields.Many2one(
        'account.invoice',
        string="Documento",
        ondelete='cascade',
    )
    order_id = fields.Many2one(
        'pos.order',
        string="Documento",
        ondelete='cascade',
    )
    sequence = fields.Integer(
        string="Número de línea",
        default=1
    )
    claim = fields.Selection(
        [
            ('N/D', "No definido"),
            ('ACD', 'Acepta Contenido del Documento'),
            ('RCD', 'Reclamo al  Contenido del Documento '),
            ('ERM', 'Otorga  Recibo  de  Mercaderías  o Servicios'),
            ('RFP', 'Reclamo por Falta Parcial de Mercaderías'),
            ('RFT', 'Reclamo por Falta Total de Mercaderías'),
        ],
        string="Reclamo",
        copy=False,
        default="N/D",
    )
    estado_dte = fields.Selection([
            ('0', 'DTE Recibido Ok'),
            ('1', 'DTE Aceptado con Discrepancia.'),
            ('2', 'DTE Rechazado'),
        ],
        string="Estado de Recepción Documento"
    )
    date = fields.Datetime(
        string="Fecha Reclamo",
    )
    user_id = fields.Many2one(
        'res.users'
    )
    claim_description = fields.Char(
        string="Detalle Reclamo",
    )

    def send_claim(self):
        token = self.env['sii.xml.envio'].get_token(self.env.user, self.company_id)
        url = claim_url[self.company_id.dte_service_provider] + '?wsdl'
        _server = Client(
            url,
            headers= {
                'Cookie': 'TOKEN=' + token,
                },
        )
        try:
            respuesta = _server.service.ingresarAceptacionReclamoDoc(
                rut_emisor[:-2],
                rut_emisor[-1],
                str(self.document_class_id.sii_code),
                str(self.number),
                claim,
            )
        except Exception as e:
                msg = "Error al ingresar Reclamo DTE"
                _logger.warning("%s: %s" % (msg, str(e)))
                if e.args[0][0] == 503:
                    raise UserError('%s: Conexión al SII caída/rechazada o el SII está temporalmente fuera de línea, reintente la acción' % (msg))
                raise UserError(("%s: %s" % (msg, str(e))))


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

    def do_reject(self):
        inv_obj = self.env['account.invoice']
        id_seq = self.env.ref('l10n_cl_fe.response_sequence')
        IdRespuesta = id_seq.next_by_id()
        NroDetalles = 1
        doc = self.invoice_id or self.document_id
        datos = doc._get_datos_empresa(doc.company_id)
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
            'EstadoDTEGlosa': self.claim_description,
            'CodRchDsc': -1,
        }
        resp = fe.validacion_comercial(datos)
        att = self._create_attachment(
            resp['respuesta_xml'],
            resp['nombre_xml'],
            doc.id,
            tipo
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
        if self.claim != 'N/D':
            doc.set_dte_claim(claim=self.claim)

    def do_validar_comercial(self):
        if self.estado_dte == '0':
            self.claim_description = 'DTE Recibido Ok'
        id_seq = self.env.ref('l10n_cl_fe.response_sequence')
        IdRespuesta = id_seq.next_by_id()
        NroDetalles = 1
        doc = self.invoice_id
        tipo = "account.invoice"
        if not doc:
            tipo = 'mail.message.dte.document'
            doc = self.document_id
        if doc.claim in ['ACD'] or (self.invoice_id and doc.type in ['out_invoice', 'out_refund']):
            return
        datos = doc._get_datos_empresa(doc.company_id) if self.invoice_id else self._get_datos_empresa(doc.company_id)
        dte = doc._dte()
        ''' @TODO separar estos dos'''
        dte['CodEnvio'] = IdRespuesta
        datos['filename'] = 'validacion_comercial_%s.xml' % str(IdRespuesta)
        datos["ValidacionCom"] = {
            'IdRespuesta': IdRespuesta,
            'NroDetalles': NroDetalles,
            "RutResponde": doc.company_id.partner_id.rut(),
            "RutRecibe": doc.partner_id.commercial_partner_id.document_number,
            'NmbContacto': self.env.user.partner_id.name,
            'FonoContacto': self.env.user.partner_id.phone,
            'MailContacto': self.env.user.partner_id.email,
            'EstadoDTE': self.estado_dte,
            'EstadoDTEGlosa': self.claim_description,
            "Receptor": {
            	    "RUTRecep": doc.partner_id.commercial_partner_id.document_number,
            },
            "DTEs": [dte],
        }

        if self.estado_dte != '0':
            datos["ValidacionCom"]['CodRchDsc'] = -2
        resp = fe.validacion_comercial(datos)
        doc.sii_message = resp['respuesta_xml']
        att = self._create_attachment(
            resp['respuesta_xml'],
            resp['nombre_xml'],
            doc.id,
            tipo
        )
        dte_email_id = doc.company_id.dte_email_id or self.env.user.company_id.dte_email_id
        values = {
                    'res_id': doc.id,
                    'email_from': dte_email_id.name_get()[0][1],
                    'email_to': doc.partner_id.commercial_partner_id.dte_email,
                    'auto_delete': False,
                    'model': tipo,
                    'body': 'XML de Validación Comercial, Estado: %s, Glosa: %s' % (resp['EstadoDTE'], resp['EstadoDTEGlosa']),
                    'subject': 'XML de Validación Comercial',
                    'attachment_ids': [[6, 0, att.ids]],
                }
        send_mail = self.env['mail.mail'].create(values)
        send_mail.send()
        if self.claim == 'N/D':
            return
        try:
            doc.set_dte_claim(claim=self.claim)
        except Exception as e:
            _logger.warning("Error al setear Reclamo %s" %str(e))
        try:
            doc.get_dte_claim()
        except:
            _logger.warning("@TODO crear código que encole la respuesta")

    @api.multi
    def do_recep_mercaderia(self):
        message = ""
        doc = self.invoice_id
        tipo = "account.invoice"
        if not doc:
            tipo = 'mail.message.dte.document'
            doc = self.document_id
        if doc.claim in ['ACD']:
            return
        if self.claim == 'ERM':
            datos = doc._get_datos_empresa(doc.company_id) if self.invoice_id else self._get_datos_empresa(doc.company_id)
            datos["RecepcionMer"] = {
                'EstadoRecepDTE': self.estado_dte,
                'RecepDTEGlosa': self.claim_description,
                "RutResponde": doc.company_id.partner_id.rut(),
                "RutRecibe": doc.partner_id.commercial_partner_id.document_number,
                'Recinto': doc.company_id.street,
                'NmbContacto': self.env.user.partner_id.name,
                'FonoContacto': self.env.user.partner_id.phone,
                'MailContacto': self.env.user.partner_id.email,
                "Receptor": {
                	    "RUTRecep": doc.partner_id.commercial_partner_id.document_number,
                },
                "DTEs": [doc._dte()],
            }
            resp = fe.recepcion_mercaderias(datos)
            doc.sii_message = resp['respuesta_xml']
            att = self._create_attachment(
                resp['respuesta_xml'],
                resp['nombre_xml'],
                doc.id,
                tipo
            )
            dte_email_id = doc.company_id.dte_email_id or self.env.user.company_id.dte_email_id
            values = {
                        'res_id': doc.id,
                        'email_from': dte_email_id.name_get()[0][1],
                        'email_to': doc.partner_id.commercial_partner_id.dte_email,
                        'auto_delete': False,
                        'model': tipo,
                        'body': 'XML de Recepción de Mercaderías\n %s' % (message),
                        'subject': 'XML de Recepción de Documento',
                        'attachment_ids': [[6, 0, att.ids]],
                    }
            send_mail = self.env['mail.mail'].create(values)
            send_mail.send()
        if self.claim == 'N/D':
            return
        try:
            doc.set_dte_claim(claim=self.claim)
        except Exception as e:
            _logger.warning("Error al setear Reclamo  Recep Mercadería %s" %str(e))
        try:
            doc.get_dte_claim()
        except:
            _logger.warning("@TODO crear código que encole la respuesta")
