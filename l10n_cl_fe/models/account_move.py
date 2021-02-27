import decimal
import logging
from datetime import date, datetime, timedelta
import pytz
from six import string_types

from odoo import api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools.translate import _
from odoo.addons import decimal_precision as dp

from .bigint import BigInt

_logger = logging.getLogger(__name__)


try:
    from facturacion_electronica import facturacion_electronica as fe
    from facturacion_electronica import clase_util as util
except Exception as e:
    _logger.warning("Problema al cargar Facturación electrónica: %s" % str(e))
try:
    from io import BytesIO
except ImportError:
    _logger.warning("no se ha cargado io")
try:
    import pdf417gen
except ImportError:
    _logger.warning("Cannot import pdf417gen library")
try:
    import base64
except ImportError:
    _logger.warning("Cannot import base64 library")
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    _logger.warning("no se ha cargado PIL")


TYPE2JOURNAL = {
    "out_invoice": "sale",
    "in_invoice": "purchase",
    "out_refund": "sale",
    "in_refund": "purchase",
}


class Referencias(models.Model):
    _name = "account.move.referencias"
    _description = "Línea de referencia de Documentos DTE"

    origen = fields.Char(string="Origin",)
    sii_referencia_TpoDocRef = fields.Many2one("sii.document_class", string="SII Reference Document Type",)
    sii_referencia_CodRef = fields.Selection(
        [("1", "Anula Documento de Referencia"), ("2", "Corrige texto Documento Referencia"), ("3", "Corrige montos")],
        string="SII Reference Code",
    )
    motivo = fields.Char(string="Motivo",)
    move_id = fields.Many2one("account.move", ondelete="cascade", index=True, copy=False, string="Documento",)
    fecha_documento = fields.Date(string="Fecha Documento", required=True,)
    sequence = fields.Integer(string="Secuencia", default=1,)

    _order = "sequence ASC"


class AccountMove(models.Model):
    _inherit = "account.move"

    def _default_journal_document_class_id(self):
        if not self.env["ir.model"].search([("model", "=", "sii.document_class")]) or self.document_class_id:
            return False
        journal = self.env["account.move"].default_get(["journal_id"])["journal_id"]
        default_type = self._context.get("move_type", "out_invoice")
        if default_type in ["in_invoice", "in_refund"]:
            return self.env["account.journal.sii_document_class"]
        dc_type = ["invoice"] if default_type in ["in_invoice", "out_invoice"] else ["credit_note", "debit_note"]
        jdc = self.env["account.journal.sii_document_class"].search(
            [("journal_id", "=", journal), ("sii_document_class_id.document_type", "in", dc_type),], limit=1
        )
        return jdc

    def get_barcode_img(self, columns=13, ratio=3, xml=False):
        barcodefile = BytesIO()
        if not xml:
            xml = self.sii_barcode
        image = self.pdf417bc(xml, columns, ratio)
        image.save(barcodefile, "PNG")
        data = barcodefile.getvalue()
        return base64.b64encode(data)

    def _get_barcode_img(self):
        for r in self:
            sii_barcode_img = False
            if r.sii_barcode:
                sii_barcode_img = r.get_barcode_img()
            r.sii_barcode_img = sii_barcode_img

    @api.onchange("journal_id")
    @api.depends("journal_id")
    def get_dc_ids(self):
        for r in self:
            r.document_class_ids = []
            dc_type = ["invoice"] if r.move_type in ["in_invoice", "out_invoice"] else ["credit_note", "debit_note"]
            ids = []
            if r.move_type in ["in_invoice", "in_refund"]:
                for j in r.journal_id.document_class_ids:
                    if j.document_type in dc_type:
                        ids.append(j.id)
            else:
                jdc_ids = self.env["account.journal.sii_document_class"].search(
                    [("journal_id", "=", r.journal_id.id), ("sii_document_class_id.document_type", "in", dc_type),]
                )
                for dc in jdc_ids:
                    ids.append(dc.sii_document_class_id.id)
            r.document_class_ids = ids

    document_class_ids = fields.Many2many(
        "sii.document_class", compute="get_dc_ids", string="Available Document Classes",
    )
    journal_document_class_id = fields.Many2one(
        "account.journal.sii_document_class",
        string="Documents Type",
        default=lambda self: self._default_journal_document_class_id(),
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    document_class_id = fields.Many2one(
        "sii.document_class", string="Document Type", readonly=True, states={"draft": [("readonly", False)]},
    )
    sii_code = fields.Integer(
        related="document_class_id.sii_code", string="Document Code", copy=False, readonly=True, store=True,
    )
    sii_document_number = BigInt(
        string="Document Number", copy=False, readonly=True, states={"draft": [("readonly", False)]},
    )
    sii_batch_number = fields.Integer(
        copy=False, string="Batch Number", readonly=True, help="Batch number for processing multiple invoices together",
    )
    sii_barcode = fields.Char(
        copy=False,
        string=_("SII Barcode"),
        help="SII Barcode Name",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    sii_barcode_img = fields.Binary(
        string=_("SII Barcode Image"), help="SII Barcode Image in PDF417 format",
        compute="_get_barcode_img"
    )
    sii_message = fields.Text(string="SII Message", copy=False,)
    sii_xml_dte = fields.Text(string="SII XML DTE", copy=False, readonly=True, states={"draft": [("readonly", False)]},)
    sii_xml_request = fields.Many2one("sii.xml.envio", string="SII XML Request", copy=False,)
    sii_result = fields.Selection(
        [
            ("draft", "Borrador"),
            ("NoEnviado", "No Enviado"),
            ("EnCola", "En cola de envío"),
            ("Enviado", "Enviado"),
            ("Aceptado", "Aceptado"),
            ("Rechazado", "Rechazado"),
            ("Reparo", "Reparo"),
            ("Proceso", "Procesado"),
            ("Anulado", "Anulado"),
        ],
        string="Resultado",
        help="SII request result",
        copy=False,
    )
    canceled = fields.Boolean(string="Canceled?", readonly=True, states={"draft": [("readonly", False)]},)
    iva_uso_comun = fields.Boolean(string="Iva Uso Común", readonly=True, states={"draft": [("readonly", False)]},)
    no_rec_code = fields.Selection(
        [
            ("1", "Compras destinadas a IVA a generar operaciones no gravados o exentas."),
            ("2", "Facturas de proveedores registrados fuera de plazo."),
            ("3", "Gastos rechazados."),
            ("4", "Entregas gratuitas (premios, bonificaciones, etc.) recibidos."),
            ("9", "Otros."),
        ],
        string="Código No recuperable",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )  # @TODO select 1 automático si es emisor 2Categoría
    use_documents = fields.Boolean(related="journal_id.use_documents", string="Use Documents?", readonly=True,)
    referencias = fields.One2many(
        "account.move.referencias", "move_id", readonly=True, states={"draft": [("readonly", False)]},
    )
    forma_pago = fields.Selection(
        [("1", "Contado"), ("2", "Crédito"), ("3", "Gratuito")],
        string="Forma de pago",
        readonly=True,
        states={"draft": [("readonly", False)]},
        default="1",
    )
    contact_id = fields.Many2one("res.partner", string="Contacto",)

    canceled = fields.Boolean(string="Canceled?", copy=False,)
    estado_recep_dte = fields.Selection(
        [("recibido", "Recibido en DTE"), ("mercaderias", "Recibido mercaderias"), ("validate", "Validada Comercial")],
        string="Estado de Recepcion del Envio",
        default="recibido",
        copy=False,
    )
    estado_recep_glosa = fields.Char(string="Información Adicional del Estado de Recepción", copy=False,)
    ticket = fields.Boolean(
        string="Formato Ticket", default=False, readonly=True, states={"draft": [("readonly", False)]},
    )
    claim = fields.Selection(
        [
            ("ACD", "Acepta Contenido del Documento"),
            ("RCD", "Reclamo al  Contenido del Documento "),
            ("ERM", " Otorga  Recibo  de  Mercaderías  o Servicios"),
            ("RFP", "Reclamo por Falta Parcial de Mercaderías"),
            ("RFT", "Reclamo por Falta Total de Mercaderías"),
            ("PAG", "DTE Pagado al Contado"),
        ],
        string="Reclamo",
        copy=False,
    )
    claim_description = fields.Char(string="Detalle Reclamo", readonly=True,)
    purchase_to_done = fields.Many2many(
        "purchase.order",
        string="Ordenes de Compra a validar",
        domain=[("state", "not in", ["done", "cancel"])],
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    activity_description = fields.Many2one(
        "sii.activity.description", string="Giro", related="commercial_partner_id.activity_description", readonly=True,
    )
    amount_untaxed_global_discount = fields.Float(
        string="Global Discount Amount", store=True, default=0.00, compute="_compute_amount",
    )
    amount_untaxed_global_recargo = fields.Float(
        string="Global Recargo Amount", store=True, default=0.00, compute="_compute_amount",
    )
    global_descuentos_recargos = fields.One2many(
        "account.move.gdr",
        "move_id",
        string="Descuentos / Recargos globales",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    acteco_ids = fields.Many2many(
        "partner.activities", related="commercial_partner_id.acteco_ids", string="Partner Activities"
    )
    acteco_id = fields.Many2one(
        "partner.activities", string="Partner Activity", readonly=True, states={"draft": [("readonly", False)]},
    )
    respuesta_ids = fields.Many2many("sii.respuesta.cliente", string="Recepción del Cliente", readonly=True,)
    ind_servicio = fields.Selection(
        [
            ('1', "1.- Factura de servicios periódicos domiciliarios 2"),
            ('2', "2.- Factura de otros servicios periódicos"),
            (
                '3',
                "3.- Factura de Servicios. (en caso de Factura de Exportación: Servicios calificados como tal por Aduana)",
            ),
            ('4', "4.- Servicios de Hotelería"),
            ('5', "5.- Servicio de Transporte Terrestre Internacional"),
        ]
    )
    claim_ids = fields.One2many("sii.dte.claim", "move_id", strign="Historial de Reclamos")
    sended = fields.Boolean(
        string="Enviado al SII", default=False, readonly=True, states={"draft": [("readonly", False)]},
    )
    factor_proporcionalidad = fields.Float(
        string="Factor proporcionalidad", default=0.00, readonly=True, states={"draft": [("readonly", False)]},
    )

    def _post(self, soft=True):
        to_post = super(AccountMove, self)._post(soft=soft)
        for inv in to_post:
            if not inv.is_invoice():
                continue
            if inv.purchase_to_done:
                for ptd in inv.purchase_to_done:
                    ptd.write({"state": "done"})
            if not inv.journal_document_class_id:
                continue
            inv._validaciones_uso_dte()
            inv.sii_result = "NoEnviado"
            prefix = inv.document_class_id.doc_code_prefix or ""
            sii_document_number = inv.journal_document_class_id.sequence_id.next_by_id()
            move_name = (prefix + str(sii_document_number)).replace(" ", "")
            inv.sii_document_number = int(sii_document_number)
            if inv.journal_id.restore_mode:
                inv.sii_result = "Proceso"
            else:
                inv._timbrar()
                tiempo_pasivo = datetime.now() + timedelta(
                    hours=int(self.env["ir.config_parameter"].sudo().get_param("account.auto_send_dte", default=1))
                )
                self.env["sii.cola_envio"].create(
                    {
                        "company_id": inv.company_id.id,
                        "doc_ids": [inv.id],
                        "model": "account.move",
                        "user_id": self.env.uid,
                        "tipo_trabajo": "pasivo",
                        "date_time": tiempo_pasivo,
                        "send_email": False
                        if inv.company_id.dte_service_provider == "SIICERT"
                        or not self.env["ir.config_parameter"]
                        .sudo()
                        .get_param("account.auto_send_email", default=True)
                        else True,
                    }
                )
        return to_post



    def _get_move_imps(self):
        imps = {}
        for l in self.line_ids:
            if l.tax_line_id:
                if l.tax_line_id:
                    if l.tax_line_id.id not in imps:
                        imps[l.tax_line_id.id] = {
                            "tax_id": l.tax_line_id.id,
                            "credit": 0,
                            "debit": 0,
                            "code": l.tax_line_id.sii_code,
                        }
                    imps[l.tax_line_id.id]["credit"] += l.credit
                    imps[l.tax_line_id.id]["debit"] += l.debit
            elif l.tax_ids and l.tax_ids[0].amount == 0:  # caso monto exento
                if not l.tax_ids[0].id in imps:
                    imps[l.tax_ids[0].id] = {
                        "tax_id": l.tax_ids[0].id,
                        "credit": 0,
                        "debit": 0,
                        "code": l.tax_ids[0].sii_code,
                    }
                imps[l.tax_ids[0].id]["credit"] += l.credit
                imps[l.tax_ids[0].id]["debit"] += l.debit
        return imps

    def totales_por_movimiento(self):
        move_imps = self._get_move_imps()
        imps = {
            "iva": 0,
            "exento": 0,
            "otros_imps": 0,
        }
        for _key, i in move_imps.items():
            if i["code"] in [14]:
                imps["iva"] += i["credit"] or i["debit"]
            elif i["code"] == 0:
                imps["exento"] += i["credit"] or i["debit"]
            else:
                imps["otros_imps"] += i["credit"] or i["debit"]
        imps["neto"] = self.amount - imps["otros_imps"] - imps["exento"] - imps["iva"]
        return imps

    @api.onchange("invoice_line_ids")
    def _onchange_invoice_line_ids(self):
        i = 0
        for l in self.invoice_line_ids:
            i += 1
            if l.sequence == -1 or l.sequence == 0:
                l.sequence = i
        return super(AccountMove, self)._onchange_invoice_line_ids()

    @api.depends("state", "journal_id", "invoice_date", "document_class_id")
    def _get_sequence_prefix(self):
        for invoice in self:
            if invoice.use_documents and invoice.move_type in ["out_invoice", "out_refund"]:
                invoice.sequence_number_next_prefix = invoice.document_class_id.doc_code_prefix or ""
            else:
                super(AccountMove, self)._get_sequence_prefix()

    @api.depends("state", "journal_id", "document_class_id")
    def _get_sequence_number_next(self):
        for invoice in self:
            if invoice.use_documents and invoice.move_type in ["out_invoice", "out_refund"]:
                invoice.sequence_number_next = invoice.journal_document_class_id.sequence_id.number_next_actual
            else:
                super(AccountMove, self)._get_sequence_number_next()

    def _prepare_refund(
        self, invoice, invoice_date=None, description=None, journal_id=None, tipo_nota=61, mode="1"
    ):
        values = super(AccountMove, self)._prepare_refund(invoice, invoice_date, description, journal_id)
        jdc = self.env["account.journal.sii_document_class"]
        if invoice.move_type in ["in_invoice", "in_refund"]:
            dc = self.env["sii.document_class"].search([("sii_code", "=", tipo_nota),], limit=1,)
        else:
            jdc = self.env["account.journal.sii_document_class"].search(
                [("sii_document_class_id.sii_code", "=", tipo_nota), ("journal_id", "=", invoice.journal_id.id),],
                limit=1,
            )
            dc = jdc.sii_document_class_id
        if invoice.move_type == "out_invoice" and dc.document_type == "credit_note":
            type = "out_refund"
        elif invoice.move_type in ["out_refund", "out_invoice"]:
            type = "out_invoice"
        elif invoice.move_type == "in_invoice" and dc.document_type == "credit_note":
            type = "in_refund"
        elif invoice.move_type in ["in_refund", "in_invoice"]:
            type = "in_invoice"
        values.update(
            {
                "document_class_id": dc.id,
                "move_type": type,
                "journal_document_class_id": jdc.id,
                "referencias": [
                    [
                        0,
                        0,
                        {
                            "origen": invoice.sii_document_number,
                            "sii_referencia_TpoDocRef": invoice.document_class_id.id,
                            "sii_referencia_CodRef": mode,
                            "motivo": description,
                            "fecha_documento": invoice.invoice_date.strftime("%Y-%m-%d"),
                        },
                    ]
                ],
            }
        )
        return values

    @api.onchange("global_descuentos_recargos")
    def _onchange_descuentos(self):
        self._onchange_invoice_line_ids()

    @api.onchange("payment_term_id")
    def _onchange_payment_term(self):
        if self.payment_term_id and self.payment_term_id.dte_sii_code:
            self.forma_pago = self.payment_term_id.dte_sii_code

    @api.returns("self")
    def refund(self, invoice_date=None, description=None, journal_id=None, tipo_nota=61, mode="1"):
        new_invoices = self.browse()
        for invoice in self:
            # create the new invoice
            values = self._prepare_refund(
                invoice,
                invoice_date=invoice_date,
                description=description,
                journal_id=journal_id,
                tipo_nota=tipo_nota,
                mode=mode,
            )
            refund_invoice = self.create(values)
            invoice_type = self.get_invoice_types()
            message = _(
                "This %s has been created from: <a href=# data-oe-model=account.move data-oe-id=%d>%s</a><br>Reason: %s"
            ) % (invoice_type[invoice.move_type], invoice.id, invoice.number, description)
            refund_invoice.message_post(body=message)
            new_invoices += refund_invoice
        return new_invoices

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=100):
        args = args or []
        recs = self.browse()
        if not recs:
            recs = self.search([("name", operator, name)] + args, limit=limit)
        return recs.name_get()

    def action_invoice_cancel(self):
        for r in self:
            if r.sii_xml_request and r.sii_result not in [False, "draft", "NoEnviado", "Anulado"]:
                raise UserError(_("You can not cancel a valid document on SII"))
        return super(AccountMove, self).action_invoice_cancel()


    def unlink(self):
        for r in self:
            if r.sii_xml_request and r.sii_result in ["Aceptado", "Reparo", "Rechazado"]:
                raise UserError(_("You can not delete a valid document on SII"))

    @api.constrains("reference", "partner_id", "company_id", "move_type", "journal_document_class_id")
    def _check_reference_in_invoice(self):
        if self.move_type in ["in_invoice", "in_refund"] and self.sii_document_number:
            domain = [
                ("move_type", "=", self.move_type),
                ("sii_document_number", "=", self.sii_document_number),
                ("partner_id", "=", self.partner_id.id),
                ("journal_document_class_id.sii_document_class_id", "=", self.document_class_id.id),
                ("company_id", "=", self.company_id.id),
                ("id", "!=", self.id),
                ("state", "!=", "cancel"),
            ]
            move_ids = self.search(domain)
            if move_ids:
                raise UserError(
                    u"El numero de factura debe ser unico por Proveedor.\n"
                    u"Ya existe otro documento con el numero: %s para el proveedor: %s"
                    % (self.sii_document_number, self.partner_id.display_name)
                )

    @api.onchange("sii_document_number")
    def set_reference(self):
        if self.move_type in ["in_invoice", "in_refund"] and self.sii_document_number:
            self.reference = "{} {}".format(self.document_class_id.doc_code_prefix, self.sii_document_number)

    @api.onchange("journal_document_class_id")
    def set_document_class_id(self):
        if self.move_type in ["in_invoice", "in_refund"]:
            return
        self.document_class_id = self.journal_document_class_id.sii_document_class_id.id
        self._onchange_invoice_line_ids()

    def _check_duplicate_supplier_reference(self):
        for invoice in self:
            if invoice.move_type in ("in_invoice", "in_refund") and invoice.sii_document_number:
                if self.search(
                    [
                        ("sii_document_number", "=", invoice.sii_document_number),
                        ("journal_document_class_id", "=", invoice.journal_document_class_id.id),
                        ("partner_id", "=", invoice.partner_id.id),
                        ("move_type", "=", invoice.move_type),
                        ("id", "!=", invoice.id),
                    ]
                ):
                    raise UserError(
                        "El documento %s, Folio %s de la Empresa %s ya se en cuentra registrado"
                        % (invoice.document_class_id.name, invoice.sii_document_number, invoice.partner_id.name)
                    )

    def _validaciones_uso_dte(self):
        ncs = [60, 61, 112, 802]
        nds = [55, 56, 111]
        if self.document_class_id.sii_code in ncs + nds and not self.referencias:
            raise UserError("Las Notas deben llevar por obligación una referencia al documento que están afectando")
        if not self.env.user.get_digital_signature(self.company_id):
            raise UserError(
                _(
                    "Usuario no autorizado a usar firma electrónica para esta compañia. Por favor solicatar autorización en la ficha de compañia del documento por alguien con los permisos suficientes de administrador"
                )
            )
        if not self.env.ref("base.lang_es_CL").active:
            raise UserError(_("Lang es_CL must be enabled"))
        if not self.env.ref("base.CLP").active:
            raise UserError(_("Currency CLP must be enabled"))
        if self.move_type in ["out_refund", "in_refund"] and self.document_class_id.sii_code not in ncs:
            raise UserError(_("El tipo de documento %s, no es de tipo Rectificativo" % self.document_class_id.name))
        if self.move_type in ["out_invoice", "in_invoice"] and self.document_class_id.sii_code in ncs:
            raise UserError(_("El tipo de documento %s, no es de tipo Documento" % self.document_class_id.name))
        for gd in self.global_descuentos_recargos:
            if gd.valor <= 0:
                raise UserError(
                    _("No puede ir una línea igual o menor que 0, elimine la línea o verifique el valor ingresado")
                )
        if self.company_id.tax_calculation_rounding_method != "round_globally":
            raise UserError("El método de redondeo debe ser Estríctamente Global")


    def default_journal(self):
        if self._context.get("default_journal_id", False):
            return self.env["account.journal"].browse(self._context.get("default_journal_id"))
        company_id = self._context.get("company_id", self.company_id.id or self.env.user.company_id.id)
        if self._context.get("honorarios", False):
            inv_type = self._context.get("move_type", "out_invoice")
            inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
            domain = [
                ("journal_document_class_ids.sii_document_class_id.document_letter_id.name", "=", "M"),
                ("move_type", "in", [TYPE2JOURNAL[ty] for ty in inv_types if ty in TYPE2JOURNAL])(
                    "company_id", "=", company_id
                ),
            ]
            journal_id = self.env["account.journal"].search(domain, limit=1)
            return journal_id
        inv_type = self._context.get("move_type", "out_invoice")
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        domain = [
            ("move_type", "in", [TYPE2JOURNAL[ty] for ty in inv_types if ty in TYPE2JOURNAL]),
            ("company_id", "=", company_id),
        ]
        return self.env["account.journal"].search(domain, limit=1, order="sequence asc")

    def time_stamp(self, formato="%Y-%m-%dT%H:%M:%S"):
        tz = pytz.timezone("America/Santiago")
        return datetime.now(tz).strftime(formato)

    def crear_intercambio(self):
        rut = self.partner_id.commercial_partner_id.rut()
        envio = self._crear_envio(RUTRecep=rut)
        result = fe.xml_envio(envio)
        return result["sii_xml_request"].encode("ISO-8859-1")

    def _create_attachment(self,):
        url_path = "/download/xml/invoice/%s" % (self.id)
        filename = ("%s.xml" % self.number).replace(" ", "_")
        att = self.env["ir.attachment"].search(
            [("name", "=", filename), ("res_id", "=", self.id), ("res_model", "=", "account.move")], limit=1,
        )
        self.env["sii.respuesta.cliente"].create(
            {"exchange_id": att.id, "type": "RecepcionEnvio", "recep_envio": "no_revisado",}
        )
        if att:
            return att
        xml_intercambio = self.crear_intercambio()
        data = base64.b64encode(xml_intercambio)
        values = dict(
            name=filename,
            datas_fname=filename,
            url=url_path,
            res_model="account.move",
            res_id=self.id,
            type="binary",
            datas=data,
        )
        att = self.env["ir.attachment"].sudo().create(values)
        return att


    def action_invoice_sent(self):
        result = super(AccountMove, self).action_invoice_sent()
        if self.sii_xml_dte:
            att = self._create_attachment()
            result["context"].update(
                {"default_attachment_ids": att.ids,}
            )
        return result


    def get_xml_file(self):
        url_path = "/download/xml/invoice/%s" % (self.id)
        return {
            "type": "ir.actions.act_url",
            "url": url_path,
            "target": "self",
        }


    def get_xml_exchange_file(self):
        url_path = "/download/xml/invoice_exchange/%s" % (self.id)
        return {
            "type": "ir.actions.act_url",
            "url": url_path,
            "target": "self",
        }

    def get_folio(self):
        # saca el folio directamente de la secuencia
        return self.sii_document_number

    def format_vat(self, value, con_cero=False):
        ''' Se Elimina el 0 para prevenir problemas con el sii, ya que las muestras no las toma si va con
        el 0 , y tambien internamente se generan problemas, se mantiene el 0 delante, para cosultas, o sino retorna "error de datos"'''
        if not value or value == "" or value == 0:
            value = "CL666666666"
            # @TODO opción de crear código de cliente en vez de rut genérico
        rut = value[:10] + "-" + value[10:]
        if not con_cero:
            rut = rut.replace("CL0", "")
        rut = rut.replace("CL", "")
        return rut

    def pdf417bc(self, ted, columns=13, ratio=3):
        bc = pdf417gen.encode(ted, security_level=5, columns=columns, encoding="ISO-8859-1",)
        image = pdf417gen.render_image(bc, padding=15, scale=1, ratio=ratio,)
        return image


    def get_related_invoices_data(self):
        """
        List related invoice information to fill CbtesAsoc.
        """
        self.ensure_one()
        rel_invoices = self.search(
            [("number", "=", self.origin), ("state", "not in", ["draft", "proforma", "proforma2", "cancel"])]
        )
        return rel_invoices

    def _acortar_str(self, texto, size=1):
        c = 0
        cadena = ""
        while c < size and c < len(texto):
            cadena += texto[c]
            c += 1
        return cadena


    def do_dte_send_invoice(self, n_atencion=None):
        ids = []
        envio_boleta = False
        for inv in self.with_context(lang="es_CL"):
            if inv.sii_result in ["", "NoEnviado", "Rechazado"]:
                if inv.sii_result in ["Rechazado"]:
                    inv._timbrar()
                    if len(inv.sii_xml_request.move_ids) == 1:
                        inv.sii_xml_request.unlink()
                    else:
                        inv.sii_xml_request = False
                inv.sii_result = "EnCola"
                inv.sii_message = ""
                ids.append(inv.id)
        if not isinstance(n_atencion, string_types):
            n_atencion = ""
        if ids:
            self.env["sii.cola_envio"].create(
                {
                    "company_id": self[0].company_id.id,
                    "doc_ids": ids,
                    "model": "account.move",
                    "user_id": self.env.user.id,
                    "tipo_trabajo": "envio",
                    "n_atencion": n_atencion,
                    "set_pruebas": self._context.get("set_pruebas", False),
                    "send_email": False
                    if self[0].company_id.dte_service_provider == "SIICERT"
                    or not self.env["ir.config_parameter"].sudo().get_param("account.auto_send_email", default=True)
                    else True,
                }
            )


    def _es_boleta(self):
        return self.document_class_id.es_boleta()


    def _nc_boleta(self):
        if not self.referencias or self.move_type != "out_refund":
            return False
        for r in self.referencias:
            return r.sii_referencia_TpoDocRef.es_nc_boleta()
        return False

    def _actecos_emisor(self):
        actecos = []
        if not self.journal_id.journal_activities_ids:
            raise UserError("El Diario no tiene ACTECOS asignados")
        for acteco in self.journal_id.journal_activities_ids:
            actecos.append(acteco.code)
        return actecos

    def _id_doc(self, taxInclude=False, MntExe=0):
        IdDoc = {}
        IdDoc["TipoDTE"] = self.document_class_id.sii_code
        IdDoc["Folio"] = self.get_folio()
        IdDoc["FchEmis"] = self.invoice_date.strftime("%Y-%m-%d")
        if self._es_boleta():
            IdDoc["IndServicio"] = 3  # @TODO agregar las otras opciones a la fichade producto servicio
        if self.ticket and not self._es_boleta():
            IdDoc["TpoImpresion"] = "T"
        if self.ind_servicio:
            IdDoc["IndServicio"] = self.ind_servicio
        # todo: forma de pago y fecha de vencimiento - opcional
        if taxInclude and MntExe == 0 and not self._es_boleta():
            IdDoc["MntBruto"] = 1
        if not self._es_boleta():
            IdDoc["FmaPago"] = self.forma_pago or 1
        if not taxInclude and self._es_boleta():
            IdDoc["IndMntNeto"] = 2
        # if self._es_boleta():
        # Servicios periódicos
        #    IdDoc['PeriodoDesde'] =
        #    IdDoc['PeriodoHasta'] =
        if not self._es_boleta() and self.invoice_date_due:
            IdDoc["FchVenc"] = self.invoice_date_due.strftime("%Y-%m-%d") or datetime.strftime(datetime.now(), "%Y-%m-%d")
        return IdDoc

    def _emisor(self):
        Emisor = {}
        Emisor["RUTEmisor"] = self.company_id.partner_id.rut()
        if self._es_boleta():
            Emisor["RznSocEmisor"] = self._acortar_str(self.company_id.partner_id.name, 100)
            Emisor["GiroEmisor"] = self._acortar_str(self.company_id.activity_description.name, 80)
        else:
            Emisor["RznSoc"] = self._acortar_str(self.company_id.partner_id.name, 100)
            Emisor["GiroEmis"] = self._acortar_str(self.company_id.activity_description.name, 80)
            if self.company_id.phone:
                Emisor["Telefono"] = self._acortar_str(self.company_id.phone, 20)
            Emisor["CorreoEmisor"] = self.company_id.dte_email_id.name_get()[0][1]
            Emisor["Actecos"] = self._actecos_emisor()
        dir_origen = self.company_id
        if self.journal_id.sucursal_id:
            Emisor['Sucursal'] = self._acortar_str(self.journal_id.sucursal_id.partner_id.name, 20)
            Emisor["CdgSIISucur"] = self._acortar_str(self.journal_id.sucursal_id.sii_code, 9)
            dir_origen = self.journal_id.sucursal_id.partner_id
        Emisor['DirOrigen'] = self._acortar_str(dir_origen.street + ' ' + (dir_origen.street2 or ''), 70)
        if not dir_origen.city_id:
            raise UserError("Debe ingresar la Comuna de compañía emisora")
        Emisor['CmnaOrigen'] = dir_origen.city_id.name
        if not dir_origen.city:
            raise UserError("Debe ingresar la Ciudad de compañía emisora")
        Emisor["CiudadOrigen"] = self.company_id.city
        Emisor["Modo"] = "produccion" if self.company_id.dte_service_provider == "SII" else "certificacion"
        Emisor["NroResol"] = self.company_id.dte_resolution_number
        Emisor["FchResol"] = self.company_id.dte_resolution_date.strftime("%Y-%m-%d")
        Emisor["ValorIva"] = 19
        return Emisor

    def _receptor(self):
        Receptor = {}
        commercial_partner_id = self.commercial_partner_id or self.partner_id.commercial_partner_id
        if not commercial_partner_id.vat and not self._es_boleta() and not self._nc_boleta():
            raise UserError("Debe Ingresar RUT Receptor")
        # if self._es_boleta():
        #    Receptor['CdgIntRecep']
        Receptor["RUTRecep"] = commercial_partner_id.rut()
        Receptor["RznSocRecep"] = self._acortar_str(commercial_partner_id.name, 100)
        if not self.partner_id or Receptor["RUTRecep"] == "66666666-6":
            return Receptor
        if not self._es_boleta() and not self._nc_boleta() and self.move_type not in ["in_invoice", "in_refund"]:
            GiroRecep = self.acteco_id.name or commercial_partner_id.activity_description.name
            if not GiroRecep:
                raise UserError(_("Seleccione giro del partner"))
            Receptor["GiroRecep"] = self._acortar_str(GiroRecep, 40)
        if self.partner_id.phone or commercial_partner_id.phone:
            Receptor["Contacto"] = self._acortar_str(
                self.partner_id.phone or commercial_partner_id.phone or self.partner_id.email, 80
            )
        if (
            commercial_partner_id.email
            or commercial_partner_id.dte_email
            or self.partner_id.email
            or self.partner_id.dte_email
        ) and not self._es_boleta():
            Receptor["CorreoRecep"] = (
                commercial_partner_id.dte_email
                or self.partner_id.dte_email
                or commercial_partner_id.email
                or self.partner_id.email
            )
        street_recep = self.partner_id.street or commercial_partner_id.street or False
        if (
            not street_recep
            and not self._es_boleta()
            and not self._nc_boleta()
            and self.move_type not in ["in_invoice", "in_refund"]
        ):
            # or self.indicador_servicio in [1, 2]:
            raise UserError("Debe Ingresar dirección del cliente")
        street2_recep = self.partner_id.street2 or commercial_partner_id.street2 or False
        if street_recep or street2_recep:
            Receptor["DirRecep"] = self._acortar_str(street_recep + (" " + street2_recep if street2_recep else ""), 70)
        cmna_recep = self.partner_id.city_id.name or commercial_partner_id.city_id.name
        if (
            not cmna_recep
            and not self._es_boleta()
            and not self._nc_boleta()
            and self.move_type not in ["in_invoice", "in_refund"]
        ):
            raise UserError("Debe Ingresar Comuna del cliente")
        else:
            Receptor["CmnaRecep"] = cmna_recep
        ciudad_recep = self.partner_id.city or commercial_partner_id.city
        if ciudad_recep:
            Receptor["CiudadRecep"] = ciudad_recep
        return Receptor

    def _totales_otra_moneda(self, currency_id, MntExe, MntNeto, IVA, TasaIVA, MntTotal=0, MntBase=0):
        Totales = {}
        Totales["TpoMoneda"] = self._acortar_str(currency_id.abreviatura, 15)
        Totales["TpoCambio"] = round(currency_id.rate, 10)
        if MntNeto > 0:
            if currency_id != self.currency_id:
                MntNeto = currency_id._convert(MntNeto, self.currency_id, self.company_id, self.invoice_date)
            Totales["MntNetoOtrMnda"] = MntNeto
        if MntExe:
            if currency_id != self.currency_id:
                MntExe = currency_id._convert(MntExe, self.currency_id, self.company_id, self.invoice_date)
            Totales["MntExeOtrMnda"] = MntExe
        if MntBase and MntBase > 0:
            Totales["MntFaeCarneOtrMnda"] = MntBase
        if TasaIVA:
            if currency_id != self.currency_id:
                IVA = currency_id._convert(IVA, self.currency_id, self.company_id, self.invoice_date)
            Totales["IVAOtrMnda"] = IVA
        if currency_id != self.currency_id:
            MntTotal = currency_id._convert(MntTotal, self.currency_id, self.company_id, self.invoice_date)
        Totales["MntTotOtrMnda"] = MntTotal
        # Totales['MontoNF']
        # Totales['TotalPeriodo']
        # Totales['SaldoAnterior']
        # Totales['VlrPagar']
        return Totales

    def _totales_normal(self, currency_id, MntExe, MntNeto, IVA, TasaIVA, MntTotal=0, MntBase=0):
        Totales = {}
        if MntNeto > 0:
            if currency_id != self.currency_id:
                MntNeto = currency_id._convert(MntNeto, self.currency_id, self.company_id, self.invoice_date)
            Totales["MntNeto"] = currency_id.round(MntNeto)
        if MntExe:
            if currency_id != self.currency_id:
                MntExe = currency_id._convert(MntExe, self.currency_id, self.company_id, self.invoice_date)
            Totales["MntExe"] = currency_id.round(MntExe)
        if MntBase > 0:
            Totales["MntBase"] = currency_id.round(MntBase)
        if TasaIVA:
            Totales["TasaIVA"] = TasaIVA
            if currency_id != self.currency_id:
                IVA = currency_id._convert(IVA, self.currency_id, self.company_id, self.invoice_date)
            Totales["IVA"] = currency_id.round(IVA)
        if currency_id != self.currency_id:
            MntTotal = currency_id._convert(MntTotal, self.currency_id, self.company_id, self.invoice_date)
        Totales["MntTotal"] = currency_id.round(MntTotal)
        # Totales['MontoNF']
        # Totales['TotalPeriodo']
        # Totales['SaldoAnterior']
        # Totales['VlrPagar']
        return Totales

    def _es_exento(self):
        return self.document_class_id.sii_code in [32, 34, 41, 110, 111, 112] or (
            self.referencias and self.referencias[0].sii_referencia_TpoDocRef.sii_code in [32, 34, 41]
        )

    def _totales(self, MntExe=0, no_product=False, taxInclude=False):
        if self.move_type == 'entry' or self.is_outbound():
            sign = 1
        else:
            sign = -1
        MntNeto = 0
        IVA = False
        TasaIVA = False
        MntIVA = 0
        MntBase = 0
        if self._es_exento():
            MntExe = self.amount_total
            if no_product:
                MntExe = 0
            if self.amount_tax > 0:
                raise UserError("NO pueden ir productos afectos en documentos exentos")
        elif self.amount_untaxed and self.amount_untaxed != 0:
            IVA = False
            for t in self.line_ids:
                if t.tax_line_id.sii_code in [14, 15]:
                    IVA = t
                for tl in t.tax_ids:
                    if tl.sii_code in [14, 15]:
                        MntNeto += t.balance
                    if tl.sii_code in [17]:
                        MntBase += t.balance  # @TODO Buscar forma de calcular la base para faenamiento
        if self.amount_tax == 0 and MntExe > 0 and not self._es_exento():
            raise UserError("Debe ir almenos un producto afecto")
        if MntExe > 0:
            MntExe = MntExe
        if IVA:
            TasaIVA = round(IVA.tax_line_id.amount, 2)
            MntIVA = IVA.balance
        if no_product:
            MntNeto = 0
            TasaIVA = 0
            MntIVA = 0
        MntTotal = self.amount_total
        if no_product:
            MntTotal = 0
        return MntExe, (sign * (MntNeto)), (sign * (MntIVA)), TasaIVA, MntTotal, (sign * (MntBase))

    def currency_base(self):
        return self.env.ref("base.CLP")

    def currency_target(self):
        if self.currency_id != self.currency_base():
            return self.currency_id
        return False

    def _encabezado(self, MntExe=0, no_product=False, taxInclude=False):
        Encabezado = {}
        Encabezado["IdDoc"] = self._id_doc(taxInclude, MntExe)
        Encabezado["Emisor"] = self._emisor()
        Encabezado["Receptor"] = self._receptor()
        currency_base = self.currency_base()
        another_currency_id = self.currency_target()
        MntExe, MntNeto, IVA, TasaIVA, MntTotal, MntBase = self._totales(MntExe, no_product, taxInclude)
        Encabezado["Totales"] = self._totales_normal(currency_base, MntExe, MntNeto, IVA, TasaIVA, MntTotal, MntBase)
        if another_currency_id:
            Encabezado["OtraMoneda"] = self._totales_otra_moneda(
                another_currency_id, MntExe, MntNeto, IVA, TasaIVA, MntTotal, MntBase
            )
        return Encabezado

    def _validaciones_caf(self, caf):
        commercial_partner_id = self.commercial_partner_id or self.partner_id.commercial_partner_id
        if not commercial_partner_id.vat and not self._es_boleta() and not self._nc_boleta():
            raise UserError(_("Fill Partner VAT"))
        timestamp = self.time_stamp()
        invoice_date = self.invoice_date
        fecha_timbre = fields.Date.context_today(self)
        if fecha_timbre < invoice_date:
            raise UserError("La fecha de timbraje no puede ser menor a la fecha de emisión del documento")
        if fecha_timbre < date(int(caf["FA"][:4]), int(caf["FA"][5:7]), int(caf["FA"][8:10])):
            raise UserError("La fecha del timbraje no puede ser menor a la fecha de emisión del CAF")
        return timestamp


    def is_price_included(self):
        if not self.invoice_line_ids or not self.invoice_line_ids[0].tax_ids:
            return False
        tax = self.invoice_line_ids[0].tax_ids[0]
        if tax.price_include or (not tax.sii_detailed and (self._es_boleta() or self._nc_boleta())):
            return True
        return False

    def _invoice_lines(self):
        invoice_lines = []
        no_product = False
        MntExe = 0
        currency_base = self.currency_base()
        currency_id = self.currency_target()
        taxInclude = self.document_class_id.es_boleta()
        if (
            self.env["account.move.line"]
            .with_context(lang="es_CL")
            .search(["|", ("sequence", "=", -1), ("sequence", "=", 0), ("move_id", "=", self.id)])
        ):
            self._onchange_invoice_line_ids()
        for line in self.with_context(lang="es_CL").invoice_line_ids:
            if not line.account_id:
                continue
            if line.product_id.default_code == "NO_PRODUCT":
                no_product = True
            lines = {}
            lines["NroLinDet"] = line.sequence
            if line.product_id.default_code and not no_product:
                lines["CdgItem"] = {}
                lines["CdgItem"]["TpoCodigo"] = "INT1"
                lines["CdgItem"]["VlrCodigo"] = line.product_id.default_code
            details = line.get_tax_detail()
            lines["Impuesto"] = details['impuestos']
            MntExe += details['MntExe']
            taxInclude = details['taxInclude']
            if details.get('cod_imp_adic'):
                lines['CodImpAdic'] = details['cod_imp_adic']
            if details.get('IndExe'):
                lines['IndExe'] = details['IndExe']
            # if line.product_id.move_type == 'events':
            #   lines['ItemEspectaculo'] =
            #            if self._es_boleta():
            #                lines['RUTMandante']
            lines["NmbItem"] = self._acortar_str(line.product_id.name, 80)  #
            lines["DscItem"] = self._acortar_str(line.name, 1000)  # descripción más extenza
            if line.product_id.default_code:
                lines["NmbItem"] = self._acortar_str(
                    line.product_id.name.replace("[" + line.product_id.default_code + "] ", ""), 80
                )
            # lines['InfoTicket']
            qty = round(line.quantity, 4)
            if not no_product:
                lines["QtyItem"] = qty
            if qty == 0 and not no_product:
                lines["QtyItem"] = 1
            elif qty < 0:
                raise UserError("NO puede ser menor que 0")
            if not no_product:
                uom_name = line.product_uom_id.with_context(exportacion=self.document_class_id.es_exportacion()).name_get()
                lines["UnmdItem"] = uom_name[0][1][:4]
                price_unit = details['price_unit']
                lines["PrcItem"] = round(price_unit, 6)
                if currency_id:
                    lines["OtrMnda"] = {}
                    lines["OtrMnda"]["PrcOtrMon"] = round(
                        currency_base._convert(
                            price_unit, currency_id, self.company_id, self.invoice_date, round=False
                        ),
                        6,
                    )
                    lines["OtrMnda"]["Moneda"] = self._acortar_str(currency_id.name, 3)
                    lines["OtrMnda"]["FctConv"] = round(currency_id.rate, 4)
            if line.discount > 0:
                lines["DescuentoPct"] = line.discount
                DescMonto = line.discount_amount
                lines["DescuentoMonto"] = DescMonto
                if currency_id:
                    lines["DescuentoMonto"] = currency_base._convert(
                        DescMonto, currency_id, self.company_id, self.invoice_date
                    )
                    lines["OtrMnda"]["DctoOtrMnda"] = DescMonto
            if line.discount < 0:
                lines["RecargoPct"] = line.discount * -1
                RecargoMonto = line.discount_amount * -1
                lines["RecargoMonto"] = RecargoMonto
                if currency_id:
                    lines["OtrMnda"]["RecargoOtrMnda"] = currency_base._convert(
                        RecargoMonto, currency_id, self.company_id, self.invoice_date
                    )
            if not no_product and not taxInclude:
                price_subtotal = line.price_subtotal
                if currency_id:
                    lines["OtrMnda"]["MontoItemOtrMnda"] = currency_base._convert(
                        price_subtotal, currency_id, self.company_id, self.invoice_date
                    )
                lines["MontoItem"] = price_subtotal
            elif not no_product:
                price_total = line.price_total
                if currency_id:
                    lines["OtrMnda"]["MontoItemOtrMnda"] = currency_base._convert(
                        price_total, currency_id, self.company_id, self.invoice_date
                    )
                lines["MontoItem"] = price_total
            if no_product:
                lines["MontoItem"] = 0
            if lines["MontoItem"] < 0:
                raise UserError(_("No pueden ir valores negativos en las líneas de detalle"))
            if lines.get("PrcItem", 1) == 0:
                del lines["PrcItem"]
            invoice_lines.append(lines)
            if "IndExe" in lines:
                taxInclude = False
        return {
            "Detalle": invoice_lines,
            "MntExe": MntExe,
            "no_product": no_product,
            "tax_include": taxInclude,
        }

    def _gdr(self):
        result = []
        lin_dr = 1
        currency_base = self.currency_base()
        for dr in self.global_descuentos_recargos:
            dr_line = {}
            dr_line["NroLinDR"] = lin_dr
            dr_line["TpoMov"] = dr.type
            if dr.gdr_detail:
                dr_line["GlosaDR"] = dr.gdr_detail
            disc_type = "%"
            if dr.gdr_type == "amount":
                disc_type = "$"
            dr_line["TpoValor"] = disc_type
            dr_line["ValorDR"] = currency_base.round(dr.valor)
            if self.currency_id != currency_base:
                currency_id = self.currency_id
                dr_line["ValorDROtrMnda"] = currency_base._convert(
                    dr.valor, currency_id, self.company_id, self.invoice_date
                )
            if self.document_class_id.sii_code in [34] and (
                self.referencias and self.referencias[0].sii_referencia_TpoDocRef.sii_code == "34"
            ):  # solamente si es exento
                dr_line["IndExeDR"] = 1
            result.append(dr_line)
            lin_dr += 1
        return result

    def _dte(self, n_atencion=None):
        dte = {}
        invoice_lines = self._invoice_lines()
        dte["Encabezado"] = self._encabezado(
            invoice_lines["MntExe"], invoice_lines["no_product"],
            invoice_lines["tax_include"]
        )
        lin_ref = 1
        ref_lines = []
        if self._context.get("set_pruebas", False):
            RazonRef = "CASO"
            if not self._es_boleta() and n_atencion:
                RazonRef += " " + n_atencion
            RazonRef += "-" + str(self.sii_batch_number)
            ref_line = {}
            ref_line["NroLinRef"] = lin_ref
            if self._es_boleta():
                ref_line["CodRef"] = "SET"
            else:
                ref_line["TpoDocRef"] = "SET"
                ref_line["FolioRef"] = self.get_folio()
                ref_line["FchRef"] = datetime.strftime(datetime.now(), "%Y-%m-%d")
            ref_line["RazonRef"] = RazonRef
            lin_ref = 2
            ref_lines.append(ref_line)
        if self.referencias:
            for ref in self.referencias:
                ref_line = {}
                ref_line["NroLinRef"] = lin_ref
                if not self._es_boleta():
                    if ref.sii_referencia_TpoDocRef:
                        ref_line["TpoDocRef"] = (
                            self._acortar_str(ref.sii_referencia_TpoDocRef.doc_code_prefix, 3)
                            if ref.sii_referencia_TpoDocRef.use_prefix
                            else ref.sii_referencia_TpoDocRef.sii_code
                        )
                        ref_line["FolioRef"] = ref.origen
                    ref_line["FchRef"] = ref.fecha_documento or datetime.strftime(datetime.now(), "%Y-%m-%d")
                if ref.sii_referencia_CodRef not in ["", "none", False]:
                    ref_line["CodRef"] = ref.sii_referencia_CodRef
                ref_line["RazonRef"] = ref.motivo
                if self._es_boleta():
                    ref_line['CodVndor'] = self.user_id.id
                    ref_lines["CodCaja"] = self.journal_id.point_of_sale_id.name
                ref_lines.append(ref_line)
                lin_ref += 1
        dte["Detalle"] = invoice_lines["Detalle"]
        dte["DscRcgGlobal"] = self._gdr()
        dte["Referencia"] = ref_lines
        dte["CodIVANoRec"] = self.no_rec_code
        dte["IVAUsoComun"] = self.iva_uso_comun
        dte["moneda_decimales"] = self.currency_id.decimal_places
        return dte

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

    def _timbrar(self, n_atencion=None):
        folio = self.get_folio()
        datos = self._get_datos_empresa(self.company_id)
        datos["Documento"] = [
            {
                "TipoDTE": self.document_class_id.sii_code,
                "caf_file": [self.journal_document_class_id.sequence_id.get_caf_file(folio, decoded=False).decode()],
                "documentos": [self._dte(n_atencion)],
            },
        ]
        result = fe.timbrar(datos)
        if result[0].get("error"):
            raise UserError(result[0].get("error"))
        bci = self.get_barcode_img(xml=result[0]["sii_barcode"])
        self.write(
            {
                "sii_xml_dte": result[0]["sii_xml_request"],
                "sii_barcode": result[0]["sii_barcode"],
                "sii_barcode_img": bci,
            }
        )

    def _crear_envio(self, n_atencion=None, RUTRecep="60803000-K"):
        grupos = {}
        batch = 0
        api = False
        for r in self:
            batch += 1
            # si viene una guía/nota referenciando una factura,
            # que por numeración viene a continuación de la guia/nota,
            # será recahazada la guía porque debe estar declarada la factura primero
            if not r.sii_batch_number or r.sii_batch_number == 0:
                r.sii_batch_number = batch
            if r._es_boleta():
                api = True
            if r.sii_batch_number != 0 and r._es_boleta():
                for i in grupos.keys():
                    if i not in [39, 41]:
                        raise UserError(
                            "No se puede hacer envío masivo con contenido mixto, para este envío solamente boleta electrónica, boleta exenta electrónica o NC de Boleta ( o eliminar los casos descitos del set)"
                        )
            if (
                self._context.get("set_pruebas", False) or r.sii_result == "Rechazado" or not r.sii_xml_dte
            ):  # Retimbrar con número de atención y envío
                r._timbrar(n_atencion)
            grupos.setdefault(r.document_class_id.sii_code, [])
            grupos[r.document_class_id.sii_code].append(
                {"NroDTE": r.sii_batch_number, "sii_xml_request": r.sii_xml_dte, "Folio": r.get_folio(),}
            )
            if r.sii_result in ["Rechazado"] or (
                self._context.get("set_pruebas", False) and r.sii_xml_request.state in ["", "draft", "NoEnviado"]
            ):
                if r.sii_xml_request:
                    if len(r.sii_xml_request.move_ids) == 1:
                        r.sii_xml_request.unlink()
                    else:
                        r.sii_xml_request = False
                r.sii_message = ""
        datos = self[0]._get_datos_empresa(self[0].company_id)
        if self._context.get("set_pruebas", False):
            api = False
        datos.update({
            "api": api,
            "RutReceptor": RUTRecep, "Documento": []})
        for k, v in grupos.items():
            datos["Documento"].append(
                {"TipoDTE": k, "documentos": v,}
            )
        return datos


    def do_dte_send(self, n_atencion=None):
        datos = self._crear_envio(n_atencion)
        envio_id = self[0].sii_xml_request
        if not envio_id:
            envio_id = self.env["sii.xml.envio"].create({
                'name': 'temporal',
                'xml_envio': 'temporal',
                'move_ids': [[6,0, self.ids]],
            })
        datos["ID"] = "Env%s" %envio_id.id
        result = fe.timbrar_y_enviar(datos)
        envio = {
            "xml_envio": result.get("sii_xml_request", "temporal"),
            "name": result.get("sii_send_filename", "temporal"),
            "company_id": self[0].company_id.id,
            "user_id": self.env.uid,
            "sii_send_ident": result.get("sii_send_ident"),
            "sii_xml_response": result.get("sii_xml_response"),
            "state": result.get("status"),

        }
        envio_id.write(envio)
        return envio_id

    def _get_dte_status(self):
        datos = self[0]._get_datos_empresa(self[0].company_id)
        datos["Documento"] = []
        docs = {}
        api = False
        for r in self:
            api = r._es_boleta()
            if r.sii_xml_request.state not in ["Aceptado", "Rechazado"]:
                continue
            docs.setdefault(r.document_class_id.sii_code, [])
            docs[r.document_class_id.sii_code].append(r._dte())
        if not docs:
            _logger.warning("En get_dte_status, no docs")
            return
        if self._context.get("set_pruebas", False):
            api = False
        datos['api'] = api
        for k, v in docs.items():
            datos["Documento"].append({"TipoDTE": k, "documentos": v})
        resultado = fe.consulta_estado_documento(datos)
        if not resultado:
            _logger.warning("En get_dte_status, no resultado")
            return
        for r in self:
            id = "T{}F{}".format(r.document_class_id.sii_code, r.sii_document_number)
            r.sii_result = resultado[id]["status"]
            if resultado[id].get("xml_resp"):
                r.sii_message = resultado[id].get("xml_resp")


    def ask_for_dte_status(self):
        for r in self:
            if not r.sii_xml_request and not r.sii_xml_request.sii_send_ident:
                raise UserError("No se ha enviado aún el documento, aún está en cola de envío interna en odoo")
            if r.sii_xml_request.state not in ["Aceptado", "Rechazado"]:
                r.sii_xml_request.with_context(
                    set_pruebas=self._context.get("set_pruebas", False)).get_send_status(r.env.user)
        try:
            self._get_dte_status()
        except Exception as e:
            _logger.warning("Error al obtener DTE Status: %s" % str(e))
        for r in self:
            mess = False
            if r.sii_result == "Rechazado":
                mess = {
                    "title": "Documento Rechazado",
                    "message": "%s" % r.name,
                    "type": "dte_notif",
                }
            if r.sii_result == "Anulado":
                r.canceled = True
                try:
                    r.action_invoice_cancel()
                except Exception:
                    _logger.warning("Error al cancelar Documento")
                mess = {
                    "title": "Documento Anulado",
                    "message": "%s" % r.name,
                    "type": "dte_notif",
                }
            if mess:
                self.env["bus.bus"].sendone((self._cr.dbname, "account.move", r.user_id.partner_id.id), mess)

    def set_dte_claim(self, claim=False):
        if self.document_class_id.sii_code not in [33, 34, 43]:
            self.claim = claim
            return
        tipo_dte = self.document_class_id.sii_code
        datos = self._get_datos_empresa(self.company_id)
        partner_id = self.commercial_partner_id or self.partner_id.commercial_partner_id
        rut_emisor = partner_id.rut()
        datos["DTEClaim"] = [
            {
                "RUTEmisor": rut_emisor,
                "TipoDTE": tipo_dte,
                "Folio": str(self.sii_document_number),
                "Claim": claim,
            }
        ]
        try:
            respuesta = fe.ingresar_reclamo_documento(datos)
            key = "RUT%sT%sF%s" %(rut_emisor,
                                  tipo_dte, str(self.sii_document_number))
            self.claim_description = respuesta[key]
        except Exception as e:
            msg = "Error al ingresar Reclamo DTE"
            _logger.warning("{}: {}".format(msg, str(e)))
            if e.args[0][0] == 503:
                raise UserError(
                    "%s: Conexión al SII caída/rechazada o el SII está temporalmente fuera de línea, reintente la acción"
                    % (msg)
                )
            raise UserError("{}: {}".format(msg, str(e)))
        self.claim_description = respuesta
        if respuesta.codResp in [0, 7]:
            self.claim = claim


    def get_dte_claim(self):
        tipo_dte = self.document_class_id.sii_code
        datos = self._get_datos_empresa(self.company_id)
        rut_emisor = self.company_id.partner_id.rut()
        if self.move_type in ["in_invoice", "in_refund"]:
            partner_id = self.commercial_partner_id or self.partner_id.commercial_partner_id
            rut_emisor = partner_id.rut()
        datos["DTEClaim"] = [
            {
                "RUTEmisor": rut_emisor,
                "TipoDTE": tipo_dte,
                "Folio": str(self.sii_document_number),
            }
        ]
        try:
            respuesta = fe.consulta_reclamo_documento(datos)
            key = "RUT%sT%sF%s" %(rut_emisor,
                                  tipo_dte, str(self.sii_document_number))
            self.claim_description = respuesta[key]
        except Exception as e:
            if e.args[0][0] == 503:
                raise UserError(
                    "%s: Conexión al SII caída/rechazada o el SII está temporalmente fuera de línea, reintente la acción"
                    % (tools.ustr(e))
                )
            raise UserError(tools.ustr(e))


    def wizard_upload(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "sii.dte.upload_xml.wizard",
            "src_model": "account.move",
            "view_mode": "form",
            "view_type": "form",
            "views": [(False, "form")],
            "target": "new",
            "tag": "action_upload_xml_wizard",
        }


    def invoice_print(self):
        self.ensure_one()
        self.filtered(lambda inv: not inv.sent).write({"sent": True})
        if self.ticket or (self.document_class_id and self.document_class_id.sii_code == 39):
            return self.env.ref("l10n_cl_fe.action_print_ticket").report_action(self)
        return super(AccountMove, self).invoice_print()


    def print_cedible(self):
        """ Print Cedible
        """
        return self.env.ref("l10n_cl_fe.action_print_cedible").report_action(self)


    def print_copy_cedible(self):
        """ Print Copy and Cedible
        """
        return self.env.ref("l10n_cl_fe.action_print_copy_cedible").report_action(self)

    def send_exchange(self):
        commercial_partner_id = self.commercial_partner_id or self.partner_id.commercial_partner_id
        att = self._create_attachment()
        if commercial_partner_id.es_mipyme:
            return
        body = "XML de Intercambio DTE: %s" % (self.number)
        subject = "XML de Intercambio DTE: %s" % (self.number)
        dte_email_id = self.company_id.dte_email_id or self.env.user.company_id.dte_email_id
        dte_receptors = commercial_partner_id.child_ids + commercial_partner_id
        email_to = commercial_partner_id.dte_email or ""
        for dte_email in dte_receptors:
            if not dte_email.send_dte or not dte_email.email:
                continue
            if dte_email.email in ["facturacionmipyme2@sii.cl", "facturacionmipyme@sii.cl"]:
                resp = self.env["sii.respuesta.cliente"].sudo().search([("exchange_id", "=", att.id)])
                resp.estado = "0"
                continue
            if not dte_email.email in email_to:
                email_to += dte_email.email + ","
        if email_to == "":
            return
        values = {
            "res_id": self.id,
            "email_from": dte_email_id.name_get()[0][1],
            "email_to": email_to[:-1],
            "auto_delete": False,
            "model": "account.move",
            "body": body,
            "subject": subject,
            "attachment_ids": [[6, 0, att.ids]],
        }
        send_mail = self.env["mail.mail"].sudo().create(values)
        send_mail.send()


    def manual_send_exchange(self):
        self.send_exchange()


    def _get_report_base_filename(self):
        self.ensure_one()
        if self.document_class_id:
            string_state = ""
            if self.state == "draft":
                string_state = "en borrador "
            report_string = "{} {} {}".format(
                self.document_class_id.report_name or self.document_class_id.name,
                string_state,
                self.sii_document_number or "",
            )
        else:
            report_string = super(AccountMove, self)._get_report_base_filename()
        return report_string


    def exento(self):
        exento = 0
        for l in self.invoice_line_ids:
            if l.tax_ids.amount == 0:
                exento += l.price_subtotal
        return exento if exento > 0 else (exento * -1)


    def getTotalDiscount(self):
        total_discount = 0
        for l in self.invoice_line_ids:
            if not l.account_id:
                continue
            total_discount += l.discount_amount
        return self.currency_id.round(total_discount)


    def sii_header(self):
        W, H = (560, 255)
        img = Image.new("RGB", (W, H), color=(255, 255, 255))

        d = ImageDraw.Draw(img)
        w, h = (0, 0)
        for _i in range(10):
            d.rectangle(((w, h), (550 + w, 220 + h)), outline="black")
            w += 1
            h += 1
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        d.text((50, 30), "R.U.T.: %s" % self.company_id.document_number, fill=(0, 0, 0), font=font)
        d.text((50, 90), self.document_class_id.name, fill=(0, 0, 0), font=font)
        d.text((220, 150), "N° %s" % self.sii_document_number, fill=(0, 0, 0), font=font)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        d.text((200, 235), "SII %s" % self.company_id.sii_regional_office_id.name, fill=(0, 0, 0), font=font)

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        imm = base64.b64encode(buffered.getvalue()).decode()
        return imm


    def currency_format(self, val, application='Product Price'):
        code = self._context.get('lang') or self.partner_id.lang
        lang = self.env['res.lang'].search([('code', '=', code)])
        precision = self.env['decimal.precision'].precision_get(application)
        string_digits = '%.{}f'.format(precision)
        res = lang.format(string_digits, val
                          ,grouping=True, monetary=True)
        if self.currency_id.symbol:
            if self.currency_id.position == 'after':
                res = '%s %s' % (res, self.currency_id.symbol)
            elif self.currency_id.position == 'before':
                res = '%s %s' % (self.currency_id.symbol, res)
        return res
