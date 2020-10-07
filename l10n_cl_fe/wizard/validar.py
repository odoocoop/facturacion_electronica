import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ValidarDTEWizard(models.TransientModel):
    _name = "sii.dte.validar.wizard"
    _description = "SII XML from Provider"

    def _get_docs(self):
        context = dict(self._context or {})
        if self.tipo != "mail.message.dte.document" != context.get("active_model"):
            return self.env["mail.message.dte.document"]
        active_ids = context.get("active_ids", []) or []
        return [(6, 0, active_ids)]

    def _get_invs(self):
        context = dict(self._context or {})
        if self.tipo != "account.invoice" != context.get("active_model"):
            return self.env["account.invoice"]
        active_ids = context.get("active_ids", []) or []
        return [(6, 0, active_ids)]

    action = fields.Selection(
        [
            ("receipt", "Recibo de mercaderías"),
            ("validate", "Aprobar comercialmente"),
            ("ambas", "Realizar ambas operacioness"),
        ],
        string="Respuesta a Emitir",
        default="validate",
    )
    invoice_ids = fields.Many2many("account.invoice", string="Facturas", default=lambda self: self._get_invs(),)
    document_ids = fields.Many2many(
        "mail.message.dte.document", string="Documentos Dte", default=lambda self: self._get_docs(),
    )
    estado_dte = fields.Selection(
        [("0", "DTE Recibido Ok"), ("1", "DTE Aceptado con Discrepancia."), ("2", "DTE Rechazado"),],
        string="Estado de Recepción Documento",
        default="0",
    )
    claim = fields.Selection(
        [
            ("N/D", "No enviar reclamo al SII"),
            ("ACD", "Acepta Contenido del Documento"),
            ("RCD", "Reclamo al  Contenido del Documento "),
            ("ERM", "Otorga  Recibo  de  Mercaderías  o Servicios"),
            ("RFP", "Reclamo por Falta Parcial de Mercaderías"),
            ("RFT", "Reclamo por Falta Total de Mercaderías"),
            ("PAG", "DTE Pagado al Contado"),
        ],
        string="Reclamo",
        required=True,
        default="ACD",
    )
    claim_description = fields.Char(string="Glosa Reclamo",)
    tipo = fields.Char(string="Model destino")

    @api.onchange("action")
    def marcar_reclamo(self):
        if self.action == "receipt":
            if self.claim not in ["N/D", "ERM", "RFP", "RFT"]:
                self.claim = "ERM"
        elif self.action == "validate":
            if self.estado_dte == "0" and self.claim not in ["N/D", "ACD"]:
                self.claim = "ACD"
            # elif self.estado_dte == '1' and self.claim not in ['N/D', 'RCD']:

    @api.multi
    def confirm(self):
        """
        if self.action == 'receipt' and self.claim not in ['N/D', 'ERM', 'RFP', 'RFT']:
            raise UserError("Para recepción de mercadería, reclamo solo debe ser ERM, RFP, RFT")
        elif self.action == 'validate' and self.claim not in ['N/D', 'ACD', 'RCD']:
            raise UserError("Para validación Comercial, reclamo solo debe ser ACD, RCD")
        """
        if self.action in ["receipt", "ambas"]:
            self.do_receipt()
        if self.action in ["validate", "ambas"]:
            self.do_validar_comercial()
        if self.document_ids and self.estado_dte in ["0", "1"]:
            for r in self.document_ids:
                if not r.invoice_id:
                    vals = {
                        "xml_file": r.xml.encode("ISO-8859-1"),
                        "filename": r.dte_id.name,
                        "pre_process": False,
                        "document_id": r.id,
                        "option": False,
                    }
                    wiz = self.env["sii.dte.upload_xml.wizard"].create(vals)
                    resp = wiz.confirm(ret=True)
                    if resp:
                        r.invoice_id = resp[0]

    def do_reject(self, document_ids):
        docs = self.invoice_ids or self.document_ids
        for doc in docs:
            claims = 1
            datos = {
                "claim": self.claim,
                "date": fields.Datetime.now(),
                "user_id": self.env.uid,
                "claim_description": self.claim_description,
                "sequence": claims,
                "estado_dte": self.estado_dte,
            }
            if self.tipo == "account.invoice":
                datos["invoice_id"] = doc.id
            else:
                datos["document_id"] = doc.id
            claim = self.env["sii.dte.claim"].sudo().create(datos)
            claim.do_reject(doc)

    def do_validar_comercial(self):
        docs = self.invoice_ids or self.document_ids
        for doc in docs:
            claims = 1
            datos = {
                "claim": self.claim,
                "date": fields.Datetime.now(),
                "user_id": self.env.uid,
                "claim_description": self.claim_description,
                "sequence": claims,
                "estado_dte": self.estado_dte,
            }
            if self.tipo == "account.invoice":
                datos["invoice_id"] = doc.id
            else:
                datos["document_id"] = doc.id
            claim = self.env["sii.dte.claim"].sudo().create(datos)
            claim.do_validar_comercial()

    @api.multi
    def do_receipt(self):
        docs = self.invoice_ids or self.document_ids
        for doc in docs:
            claims = 1
            datos = {
                "claim": "ERM",
                "date": fields.Datetime.now(),
                "user_id": self.env.uid,
                "claim_description": self.claim_description,
                "sequence": claims,
                "estado_dte": self.estado_dte,
            }
            if self.tipo == "account.invoice":
                datos["invoice_id"] = doc.id
            else:
                datos["document_id"] = doc.id
            claim = self.env["sii.dte.claim"].sudo().create(datos)
            if self.tipo == "account.invoice":
                claim.invoice_id = doc.id
            else:
                claim.document_id = doc.id
            claim.do_recep_mercaderia()
