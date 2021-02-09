import logging
from lxml import etree
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _
import json

_logger = logging.getLogger(__name__)

try:
    from facturacion_electronica import facturacion_electronica as fe
except Exception as e:
    _logger.warning("no se ha cargado FE %s" % str(e))


status_dte = [
    ("no_revisado", "No Revisado"),
    ("0", "Conforme"),
    ("1", "Error de Schema"),
    ("2", "Error de Firma"),
    ("3", "RUT Receptor No Corresponde"),
    ("90", "Archivo Repetido"),
    ("91", "Archivo Ilegible"),
    ("99", "Envio Rechazado - Otros"),
]


class SIIXMLEnvio(models.Model):
    _name = "sii.xml.envio"
    _description = "XML de envío DTE"

    name = fields.Char(string="Nombre de envío", required=True, readonly=True, states={"draft": [("readonly", False)]},)
    xml_envio = fields.Text(string="XML Envío", required=True, readonly=True, states={"draft": [("readonly", False)]},)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("NoEnviado", "No Enviado"),
            ("Enviado", "Enviado"),
            ("Aceptado", "Aceptado"),
            ("Rechazado", "Rechazado"),
        ],
        default="draft",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañia",
        required=True,
        default=lambda self: self.env.user.company_id.id,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    sii_xml_response = fields.Text(
        string="SII XML Response", copy=False, readonly=True, states={"NoEnviado": [("readonly", False)]},
    )
    sii_send_ident = fields.Text(
        string="SII Send Identification", copy=False, readonly=True, states={"draft": [("readonly", False)]},
    )
    sii_receipt = fields.Text(
        string="SII Mensaje de recepción",
        copy=False,
        readonly=False,
        states={"Aceptado": [("readonly", False)], "Rechazado": [("readonly", False)]},
    )
    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        helps="Usuario que envía el XML",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    invoice_ids = fields.One2many(
        "account.invoice", "sii_xml_request", string="Facturas", readonly=True, states={"draft": [("readonly", False)]},
    )
    attachment_id = fields.Many2one("ir.attachment", string="XML Recepción", readonly=True,)
    email_respuesta = fields.Text(string="Email SII", readonly=True,)
    email_estado = fields.Selection(status_dte, string="Respuesta Envío", readonly=True,)
    email_glosa = fields.Text(string="Glosa Recepción", readonly=True,)
    boleta_voucher_ids = fields.One2many(
            'account.move.boleta_voucher',
            'sii_xml_request',
            string="NC Boleta Voucher",
            readonly=True,
            states={'draft': [('readonly', False)]},
        )

    @api.multi
    def name_get(self):
        result = []
        for r in self:
            name = r.name + " Código Envío: %s" % r.sii_send_ident if r.sii_send_ident else r.name
            result.append((r.id, name))
        return result

    @api.multi
    def unlink(self):
        for r in self:
            if r.state in ["Aceptado", "Enviado"]:
                raise UserError(_("You can not delete a valid document on SII"))
        return super(SIIXMLEnvio, self).unlink()

    def _emisor(self):
        Emisor = {}
        Emisor["RUTEmisor"] = self.company_id.partner_id.rut()
        Emisor["RznSoc"] = self.company_id.name
        Emisor["Modo"] = "produccion" if self.company_id.dte_service_provider == "SII" else "certificacion"
        Emisor["NroResol"] = self.company_id.dte_resolution_number
        Emisor["FchResol"] = self.company_id.dte_resolution_date.strftime("%Y-%m-%d")
        Emisor["ValorIva"] = 19
        return Emisor

    def _get_datos_empresa(self, company_id):
        signature_id = self.env.user.get_digital_signature(company_id)
        if not signature_id:
            raise UserError(
                _(
                    """There are not a Signature Cert Available for this user, please upload your signature or tell to someelse."""
                )
            )
        emisor = self._emisor()
        return {
            "Emisor": emisor,
            "firma_electronica": signature_id.parametros_firma(),
        }

    def send_xml(self):
        if self.sii_send_ident:
            _logger.warning("XML %s ya enviado" % self.name)
            return
        datos = self._get_datos_empresa(self.company_id)
        datos.update(
            {"sii_xml_request": self.xml_envio, "filename": self.name, "api": "EnvioBOLETA" in self.xml_envio,}
        )
        res = fe.enviar_xml(datos)
        if type(res) is str:
            self.state = "NoEnviado"
        else:
            self.write(
                {
                    "state": res.get("status", "NoEnviado"),
                    "sii_send_ident": res.get("sii_send_ident", ""),
                    "sii_xml_response": res.get("sii_xml_response", ""),
                }
            )
        self.set_states()

    @api.multi
    def do_send_xml(self):
        self.send_xml()

    def object_receipt(self):
        if '<?xml' in self.sii_receipt:
            return etree.XML(
                self.sii_receipt.replace('<?xml version="1.0" encoding="UTF-8"?>', "")
                .replace("SII:", "")
                .replace(' xmlns="http://www.sii.cl/XMLSchema"', "")
            )
        return json.loads(self.sii_receipt)

    def get_send_status(self, user_id=False):
        datos = self._get_datos_empresa(self.company_id)
        api = "EnvioBOLETA" in self.xml_envio
        if self._context.get("set_pruebas", False):
            api = False
        datos.update(
            {"codigo_envio": self.sii_send_ident, "api": api,}
        )
        res = fe.consulta_estado_dte(datos)
        self.write(
            {"state": res["status"], "sii_receipt": res.get("xml_resp", False),}
        )
        self.set_states()

    @api.multi
    def ask_for(self):
        self.get_send_status(self.user_id)

    def set_childs(self, state):
        for r in self.invoice_ids:
            r.sii_result = state
        for r in self.boleta_voucher_ids:
            r.sii_result = state

    @api.onchange('state')
    def set_states(self):
        state = self.state
        if state in ['draft', 'NoEnviado']:
            return
        if self.sii_receipt:
            receipt = self.object_receipt()
            if type(receipt) is dict:
                if not receipt.get('estadistica'):
                    state = 'Aceptado'
            elif receipt.find("RESP_HDR") is not None:
                state = "Aceptado"
        self.set_childs(state)
