import base64
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)
try:
    from facturacion_electronica import facturacion_electronica as fe
except ImportError:
    _logger.warning("No se ha podido cargar fe")


class DTEClaim(models.Model):
    _name = "sii.dte.claim"
    _description = "DTE CLAIM"
    _inherit = ["mail.thread"]

    document_id = fields.Many2one("mail.message.dte.document", string="Documento", ondelete="cascade",)
    invoice_id = fields.Many2one("account.invoice", string="Documento", ondelete="cascade",)
    sequence = fields.Integer(string="Número de línea", default=1)
    claim = fields.Selection(
        [
            ("N/D", "No definido"),
            ("ACD", "Acepta Contenido del Documento"),
            ("RCD", "Reclamo al  Contenido del Documento "),
            ("ERM", "Otorga  Recibo  de  Mercaderías  o Servicios"),
            ("RFP", "Reclamo por Falta Parcial de Mercaderías"),
            ("RFT", "Reclamo por Falta Total de Mercaderías"),
            ("PAG", "DTE Pagado al Contado"),
        ],
        string="Reclamo",
        copy=False,
        default="N/D",
    )
    estado_dte = fields.Selection(
        [("0", "DTE Recibido Ok"), ("1", "DTE Aceptado con Discrepancia."), ("2", "DTE Rechazado"),],
        string="Estado de Recepción Documento",
    )
    date = fields.Datetime(string="Fecha Reclamo",)
    user_id = fields.Many2one("res.users")
    claim_description = fields.Char(string="Detalle Reclamo",)

    def _emisor(self, company_id):
        Emisor = {}
        Emisor["RUTEmisor"] = company_id.document_number
        Emisor["RznSoc"] = company_id.partner_id.name
        Emisor["GiroEmis"] = company_id.activity_description.name
        if company_id.phone:
            Emisor["Telefono"] = company_id.phone
        Emisor["CorreoEmisor"] = company_id.dte_email_id.name_get()[0][1]
        # Emisor['Actecos'] = self._actecos_emisor()
        Emisor["DirOrigen"] = company_id.street + " " + (company_id.street2 or "")
        if not company_id.city_id:
            raise UserError("Debe ingresar la Comuna de compañía emisora")
        Emisor["CmnaOrigen"] = company_id.city_id.name
        if not company_id.city:
            raise UserError("Debe ingresar la Ciudad de compañía emisora")
        Emisor["CiudadOrigen"] = company_id.city
        Emisor["Modo"] = "produccion" if company_id.dte_service_provider == "SII" else "certificacion"
        Emisor["NroResol"] = company_id.dte_resolution_number
        Emisor["FchResol"] = company_id.dte_resolution_date.strftime("%Y-%m-%d")
        return Emisor

    def _get_datos_empresa(self, company_id):
        signature_id = self.env.user.get_digital_signature(company_id)
        if not signature_id:
            raise UserError(
                _(
                    """There are not a Signature Cert Available for this user, please upload your signature or tell to someelse."""
                )
            )
        emisor = self._emisor(company_id)
        return {
            "Emisor": emisor,
            "firma_electronica": signature_id.parametros_firma(),
        }

    def send_claim(self):
        doc = self.invoice_id
        if doc:
            doc.set_dte_claim(self.claim)
            return
        doc = self.document_id
        folio = doc.number
        tipo_dte = doc.document_class_id.sii_code
        datos = doc._get_datos_empresa(doc.company_id)
        rut_emisor = doc.get_doc_rut()
        datos["DTEClaim"] = [
            {
                "RUTEmisor": rut_emisor,
                "TipoDTE": tipo_dte,
                "Folio": folio,
                "Claim": self.claim
            }
        ]
        try:
            respuesta = fe.ingreso_reclamo_documento(datos)
        except Exception as e:
                msg = "Error al ingresar Reclamo DTE"
                _logger.warning("%s: %s" % (msg, str(e)))
                if e.args[0][0] == 503:
                    raise UserError('%s: Conexión al SII caída/rechazada o el SII está temporalmente fuera de línea, reintente la acción' % (msg))
                raise UserError(("%s: %s" % (msg, str(e))))

    def _create_attachment(self, xml, name, id=False, model="account.invoice"):
        data = base64.b64encode(xml.encode("ISO-8859-1"))
        filename = (name).replace(" ", "")
        url_path = (
            "/web/binary/download_document?model="
            + model
            + "\
    &field=sii_xml_request&id=%s&filename=%s"
            % (id, filename)
        )
        att = self.env["ir.attachment"].search(
            [("name", "=", filename), ("res_id", "=", id), ("res_model", "=", model)], limit=1,
        )
        if att:
            return att
        values = dict(
            name=filename, datas_fname=filename, url=url_path, res_model=model, res_id=id, type="binary", datas=data,
        )
        att = self.env["ir.attachment"].create(values)
        return att

    def do_reject(self):
        id_seq = self.env.ref("l10n_cl_fe.response_sequence")
        IdRespuesta = id_seq.next_by_id()
        NroDetalles = 1
        doc = self.invoice_id or self.document_id
        datos = doc._get_datos_empresa(doc.company_id)
        """ @TODO separar estos dos"""
        dte = {
            "xml": doc.xml,
            "CodEnvio": IdRespuesta,
        }
        datos["filename"] = "rechazo_comercial_%s.xml" % str(IdRespuesta)
        datos["ValidacionCom"] = {
            "IdRespuesta": IdRespuesta,
            "NroDetalles": NroDetalles,
            "RutResponde": doc.company_id.document_number,
            "NmbContacto": self.env.user.partner_id.name,
            "FonoContacto": self.env.user.partner_id.phone,
            "MailContacto": self.env.user.partner_id.email,
            "xml_dte": dte,
            "EstadoDTE": 2,
            "EstadoDTEGlosa": self.claim_description,
            "CodRchDsc": -1,
        }
        resp = fe.validacion_comercial(datos)
        att = self._create_attachment(resp["respuesta_xml"], resp["nombre_xml"], doc.id, tipo)
        dte_email_id = doc.company_id.dte_email_id or self.env.user.company_id.dte_email_id
        values = {
            "res_id": doc.id,
            "email_from": dte_email_id.name_get()[0][1],
            "email_to": doc.dte_id.sudo().mail_id.email_from,
            "auto_delete": False,
            "model": "mail.message.dte.document",
            "body": "XML de Respuesta DTE, Estado: {} , Glosa: {} ".format(resp["EstadoDTE"], resp["EstadoDTEGlosa"]),
            "subject": "XML de Respuesta DTE",
            "attachment_ids": [[6, 0, att.ids]],
        }
        send_mail = self.env["mail.mail"].create(values)
        send_mail.send()
        if self.claim != "N/D":
            doc.set_dte_claim(claim=self.claim)

    def do_validar_comercial(self):
        if self.estado_dte == "0":
            self.claim_description = "DTE Recibido Ok"
        id_seq = self.env.ref("l10n_cl_fe.response_sequence")
        IdRespuesta = id_seq.next_by_id()
        NroDetalles = 1
        doc = self.invoice_id
        tipo = "account.invoice"
        if not doc:
            tipo = "mail.message.dte.document"
            doc = self.document_id
        if doc.claim in ["ACD"] or (self.invoice_id and doc.type in ["out_invoice", "out_refund"]):
            return
        datos = doc._get_datos_empresa(doc.company_id) if self.invoice_id else self._get_datos_empresa(doc.company_id)
        dte = doc._dte()
        """ @TODO separar estos dos"""
        dte["CodEnvio"] = IdRespuesta
        datos["filename"] = "validacion_comercial_%s.xml" % str(IdRespuesta)
        receptor = doc._receptor()
        datos["ValidacionCom"] = {
            "IdRespuesta": IdRespuesta,
            "NroDetalles": NroDetalles,
            "RutResponde": doc.company_id.partner_id.rut(),
            "RutRecibe": receptor["RUTRecep"],
            "NmbContacto": self.env.user.partner_id.name,
            "FonoContacto": self.env.user.partner_id.phone,
            "MailContacto": self.env.user.partner_id.email,
            "EstadoDTE": self.estado_dte,
            "EstadoDTEGlosa": self.claim_description,
            "Receptor": {"RUTRecep": receptor["RUTRecep"],},
            "DTEs": [dte],
        }

        if self.estado_dte in ["2"]:
            datos["filename"] = "validacion_comercial_%s.xml" % str(IdRespuesta)
            datos["ValidacionCom"]["CodRchDsc"] = -1
        elif self.estado_dte != "0":
            datos["ValidacionCom"]["CodRchDsc"] = -2
        resp = fe.validacion_comercial(datos)
        doc.sii_message = resp["respuesta_xml"]
        att = self._create_attachment(resp["respuesta_xml"], resp["nombre_xml"], doc.id, tipo)
        dte_email_id = doc.company_id.dte_email_id or self.env.user.company_id.dte_email_id
        values = {
            "res_id": doc.id,
            "email_from": dte_email_id.name_get()[0][1],
            "email_to": doc.partner_id.commercial_partner_id.dte_email,
            "auto_delete": False,
            "model": tipo,
            "body": "XML de Validación Comercial, Estado: {}, Glosa: {}".format(
                resp["EstadoDTE"], resp["EstadoDTEGlosa"]
            ),
            "subject": "XML de Validación Comercial",
            "attachment_ids": [[6, 0, att.ids]],
        }
        send_mail = self.env["mail.mail"].create(values)
        send_mail.send()
        if self.claim == "N/D":
            return
        try:
            doc.set_dte_claim(claim=self.claim)
        except Exception as e:
            _logger.warning("Error al setear Reclamo %s" % str(e))
        try:
            doc.get_dte_claim()
        except Exception:
            _logger.warning("@TODO crear código que encole la respuesta")

    @api.multi
    def do_recep_mercaderia(self):
        message = ""
        doc = self.invoice_id
        tipo = "account.invoice"
        if not doc:
            tipo = "mail.message.dte.document"
            doc = self.document_id
        if doc.claim in ["ACD"]:
            return
        if self.claim == "ERM":
            datos = (
                doc._get_datos_empresa(doc.company_id) if self.invoice_id else self._get_datos_empresa(doc.company_id)
            )
            receptor = doc._receptor()
            datos["RecepcionMer"] = {
                "EstadoRecepDTE": self.estado_dte,
                "RecepDTEGlosa": self.claim_description,
                "RutResponde": doc.company_id.partner_id.rut(),
                "RutRecibe": receptor["RUTRecep"],
                "Recinto": doc.company_id.street,
                "NmbContacto": self.env.user.partner_id.name,
                "FonoContacto": self.env.user.partner_id.phone,
                "MailContacto": self.env.user.partner_id.email,
                "Receptor": {"RUTRecep": receptor["RUTRecep"],},
                "DTEs": [doc._dte()],
            }
            resp = fe.recepcion_mercaderias(datos)
            doc.sii_message = resp["respuesta_xml"]
            att = self._create_attachment(resp["respuesta_xml"], resp["nombre_xml"], doc.id, tipo)
            dte_email_id = doc.company_id.dte_email_id or self.env.user.company_id.dte_email_id
            values = {
                "res_id": doc.id,
                "email_from": dte_email_id.name_get()[0][1],
                "email_to": doc.partner_id.commercial_partner_id.dte_email,
                "auto_delete": False,
                "model": tipo,
                "body": "XML de Recepción de Mercaderías\n %s" % (message),
                "subject": "XML de Recepción de Documento",
                "attachment_ids": [[6, 0, att.ids]],
            }
            send_mail = self.env["mail.mail"].create(values)
            send_mail.send()
        if self.claim == "N/D":
            return
        try:
            doc.set_dte_claim(claim=self.claim)
        except Exception as e:
            _logger.warning("Error al setear Reclamo  Recep Mercadería %s" % str(e))
        try:
            doc.get_dte_claim()
        except Exception:
            _logger.warning("@TODO crear código que encole la respuesta")
