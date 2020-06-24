# -*- coding: utf-8 -*-
from odoo import fields, models, api, tools
from odoo.tools.translate import _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import dateutil.relativedelta as relativedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
from lxml import etree
import pytz
import logging
_logger = logging.getLogger(__name__)

try:
    from facturacion_electronica import facturacion_electronica as fe
except Exception as e:
    _logger.warning("Problema al cargar Facturación electrónica: %s" % str(e))

allowed_docs = [29, 30, 32, 33, 34, 35, 38, 39, 40,
                41, 43, 45, 46, 48, 53, 55, 56, 60,
                61, 101, 102, 103, 104, 105, 106, 108,
                109, 110, 111, 112, 175, 180, 185, 900,
                901, 902, 903, 904, 905, 906, 907, 909,
                910, 911, 914, 918, 919, 920, 921, 922,
                924, 500, 501,
                ]


class Libro(models.Model):
    _name = "account.move.book"
    _description = 'Libro de Compra / Venta DTE'

    sii_xml_request = fields.Many2one(
            'sii.xml.envio',
            string='SII XML Request',
            copy=False)
    state = fields.Selection([
            ('draft', 'Borrador'),
            ('NoEnviado', 'No Enviado'),
            ('EnCola', 'En Cola'),
            ('Enviado', 'Enviado'),
            ('Aceptado', 'Aceptado'),
            ('Rechazado', 'Rechazado'),
            ('Reparo', 'Reparo'),
            ('Proceso', 'Proceso'),
            ('Reenviar', 'Reenviar'),
            ('Anulado', 'Anulado')],
        string='Resultado',
        index=True,
        readonly=True,
        default='draft',
        track_visibility='onchange',
        copy=False,
        help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed Invoice.\n"
             " * The 'Pro-forma' status is used the invoice does not have an invoice number.\n"
             " * The 'Open' status is used when user create invoice, an invoice number is generated. Its in open status till user does not pay invoice.\n"
             " * The 'Paid' status is set automatically when the invoice is paid. Its related journal entries may or may not be reconciled.\n"
             " * The 'Cancelled' status is used when user cancel invoice.")
    move_ids = fields.Many2many('account.move',
        readonly=True,
        states={'draft': [('readonly', False)]})

    tipo_libro = fields.Selection([
                ('ESPECIAL','Especial'),
                ('MENSUAL','Mensual'),
                ('RECTIFICA', 'Rectifica'),
                ],
                string="Tipo de Libro",
                default='MENSUAL',
                required=True,
                readonly=True,
                states={'draft': [('readonly', False)]}
            )
    tipo_operacion = fields.Selection(
            [
                ('COMPRA','Compras'),
                ('VENTA','Ventas'),
                ('BOLETA','Boleta Electrónica'),
            ],
            string="Tipo de operación",
            default="COMPRA",
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    tipo_envio = fields.Selection(
            [
                ('AJUSTE','Ajuste'),
                ('TOTAL','Total'),
                ('PARCIAL','Parcial'),
                ('TOTAL','Total'),
            ],
            string="Tipo de Envío",
            default="TOTAL",
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    folio_notificacion = fields.Char(
            string="Folio de Notificación",
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    impuestos = fields.One2many(
            'account.move.book.tax',
            'book_id',
            string="Detalle Impuestos",
        )
    currency_id = fields.Many2one(
            'res.currency',
            string='Moneda',
            default=lambda self: self.env.user.company_id.currency_id,
            required=True,
            track_visibility='always',
        )
    total_afecto = fields.Monetary(
            string="Total Afecto",
            readonly=True,
            compute="set_resumen",
            store=True,
        )
    total_exento = fields.Monetary(
            string="Total Exento",
            readonly=True,
            compute='set_resumen',
            store=True,
        )
    total_iva = fields.Monetary(
            string="Total IVA",
            readonly=True,
            compute='set_resumen',
            store=True,
        )
    total_otros_imps = fields.Monetary(
            string="Total Otros Impuestos",
            readonly=True,
            compute='set_resumen',
            store=True,
        )
    total = fields.Monetary(
            string="Total Otros Impuestos",
            readonly=True,
            compute='set_resumen',
            store=True,
        )
    periodo_tributario = fields.Char(
            string='Periodo Tributario',
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]},
            default=lambda *a: datetime.now().strftime('%Y-%m'),
        )
    company_id = fields.Many2one(
            'res.company',
            string="Compañía",
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
    fact_prop = fields.Float(
            string="Factor proporcionalidad",
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    nro_segmento = fields.Integer(
            string="Número de Segmento",
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    date = fields.Date(
            string="Fecha",
            required=True,
            readonly=True,
            states={'draft': [('readonly', False)]},
            default=lambda *a: datetime.now(),
        )
    boletas = fields.One2many(
            'account.move.book.boletas',
            'book_id',
            string="Boletas",
            readonly=True,
            states={'draft': [('readonly', False)]},
        )
    codigo_rectificacion = fields.Char(
            string="Código de Rectificación",
        )
    sii_result = fields.Selection(
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
            related="state",
        )

    @api.onchange('periodo_tributario', 'tipo_operacion', 'company_id')
    def set_movimientos(self):
        current = datetime.strptime( self.periodo_tributario + '-01', '%Y-%m-%d' )
        next_month = current + relativedelta.relativedelta(months=1)
        docs = [False, 70, 71, 35, 38, 39, 41]
        operator = 'not in'
        query = [
            ('company_id', '=', self.company_id.id),
            #('sended', '=', False),
            ('date' , '<', next_month.strftime('%Y-%m-%d')),
            ]
        domain = 'sale'
        if self.tipo_operacion in [ 'COMPRA' ]:
            two_month = current + relativedelta.relativedelta(months=-2)
            query.append(('date' , '>=', two_month.strftime('%Y-%m-%d')))
            domain = 'purchase'
        query.append(('journal_id.type', '=', domain))
        boleta_lines = [[5, ], ]
        impuesto_lines = [[5,],]
        if self.tipo_operacion in [ 'VENTA' ]:
            cfs = self.env['account.move.consumo_folios'].search([
                ('state', '=', 'Proceso'),
                ('fecha_inicio', '>=', current),
                ('fecha_inicio', '<', next_month),
            ])
            if cfs:
                cantidades = {}
                for cf in cfs:
                    for det in cf.detalles:
                        if det.tpo_doc.sii_code in [39, 41]:
                            if not cantidades.get((cf.id, det.tpo_doc)):
                                cantidades[(cf.id, det.tpo_doc)] = 0
                            cantidades[(cf.id, det.tpo_doc)] += det.cantidad
                lineas = {}
                for key, cantidad in cantidades.items():
                    cf = key[0]
                    tpo_doc = key[1]
                    impuesto = self.env['account.move.consumo_folios.impuestos'].search([('cf_id', '=', cf), ('tpo_doc.sii_code', '=', tpo_doc.sii_code)])
                    if not lineas.get(tpo_doc):
                        lineas[tpo_doc] = {'cantidad': 0, 'neto': 0, 'monto_exento': 0}
                    lineas[tpo_doc] = {
                                'cantidad': lineas[tpo_doc]['cantidad'] + cantidad,
                                'neto': lineas[tpo_doc]['neto'] + impuesto.monto_neto,
                                'monto_exento': lineas[tpo_doc]['monto_exento'] + impuesto.monto_exento,
                            }
                for tpo_doc, det in lineas.items():
                    tax_id = self.env['account.tax'].search([('sii_code', '=', 14), ('type_tax_use', '=', 'sale'), ('company_id', '=', self.company_id.id)], limit=1) if tpo_doc.sii_code == 39 else self.env['account.tax'].search([('sii_code', '=', 0), ('type_tax_use', '=', 'sale'), ('company_id', '=', self.company_id.id)], limit=1)
                    line = {
                        'currency_id': self.env.user.company_id.currency_id,
                        'tipo_boleta': tpo_doc.id,
                        'cantidad_boletas': det['cantidad'],
                        'neto': det['neto'] or det['monto_exento'],
                        'impuesto': tax_id.id,
                    }
                boleta_lines.append([0, 0, line])
        elif self.tipo_operacion in ['BOLETA']:
            docs = [39, 41]
            cfs = self.env['account.move.consumo_folios'].search([
                ('state', 'not in', ['draft']),
                ('fecha_inicio', '>=', current),
                ('fecha_inicio', '<', next_month),
            ])
            lines = [[5,],]
            monto_iva = 0
            monto_exento = 0
            for cf in cfs:
                for i in cf.impuestos:
                    monto_iva += i.monto_iva
                    monto_exento += i.monto_exento
            impuesto_lines.extend([
                 [0,0, {'tax_id': self.env['account.tax'].search([('sii_code', '=', 14), ('type_tax_use', '=', 'sale'),('company_id', '=', self.company_id.id)], limit=1).id, 'credit': monto_iva, 'currency_id' : self.env.user.company_id.currency_id.id}],
                 [0,0, {'tax_id': self.env['account.tax'].search([('sii_code', '=', 0), ('type_tax_use', '=', 'sale'),('company_id', '=', self.company_id.id)], limit=1).id, 'credit': monto_exento, 'currency_id' : self.env.user.company_id.currency_id.id}]
                 ])
            operator = 'in'
        if self.tipo_operacion in [ 'VENTA', 'BOLETA' ]:
            query.append(('date', '>=', current.strftime('%Y-%m-%d')))
        query.append(('document_class_id.sii_code', operator, docs))
        self.boletas = boleta_lines
        self.impuestos = impuesto_lines
        self.move_ids = self.env['account.move'].search(query)

    def _get_imps(self):
        imp = {}
        for move in self.move_ids:
            move_imps = move._get_move_imps()
            for key, i in move_imps.items():
                if not key in imp:
                    imp[key] = i
                else:
                    imp[key]['credit'] += i['credit']
                    imp[key]['debit'] += i['debit']
        return imp

    @api.onchange('move_ids')
    def set_resumen(self):
        for mov in self.move_ids:
            totales = mov.totales_por_movimiento()
            self.total_afecto += totales['neto']
            self.total_exento += totales['exento']
            self.total_iva += totales['iva']
            self.total_otros_imps += totales['otros_imps']
            self.total += mov.amount

    @api.onchange('move_ids')
    def compute_taxes(self):
        if self.tipo_operacion not in [ 'BOLETA' ]:
            imp = self._get_imps()
            if self.boletas:
                for bol in self.boletas:
                    if not imp.get(bol.impuesto.id):
                        imp[bol.impuesto.id] = {'credit': 0}
                    imp[bol.impuesto.id]['credit'] += bol.monto_impuesto
            if self.impuestos and isinstance(self.id, int):
                self._cr.execute("DELETE FROM account_move_book_tax WHERE book_id=%s", (self.id,))
                self.invalidate_cache()
            lines = [[5,],]
            for key, i in imp.items():
                i['currency_id'] = self.env.user.company_id.currency_id.id
                lines.append([0, 0, i])
            self.impuestos = lines

    @api.multi
    def unlink(self):
        for libro in self:
            if libro.state not in ('draft', 'cancel'):
                raise UserError(_('You cannot delete a Validated book.'))
        return super(Libro, self).unlink()

    @api.multi
    def get_xml_file(self):
        return {
            'type' : 'ir.actions.act_url',
            'url': '/download/xml/libro/%s' % (self.id),
            'target': 'self',
        }

    @api.onchange('periodo_tributario', 'tipo_operacion')
    def _setName(self):
        self.name = self.tipo_operacion
        if self.periodo_tributario:
            self.name += " " + self.periodo_tributario

    @api.multi
    def validar_libro(self):
        self._validar()
        return self.write({'state': 'NoEnviado'})

    def _get_moves(self):
        recs = []
        for rec in self.with_context(lang='es_CL').move_ids:
            rec.sended = True
            document_class_id = rec.document_class_id
            if not document_class_id or document_class_id.es_boleta()\
                or rec.sii_document_number in [False, 0]:
                continue
            query = [
                ('sii_document_number', '=', rec.sii_document_number),
                ('document_class_id', '=', document_class_id.id),
                ('partner_id.commercial_partner_id', '=', rec.partner_id.id),
                ('journal_id', '=', rec.journal_id.id),
                ('state', 'not in', ['cancel', 'draft']),
            ]
            ref = self.env['account.invoice'].search(query)
            recs.append(ref)
        return recs

    def _emisor(self):
        Emisor = {}
        Emisor['RUTEmisor'] = self.company_id.partner_id.rut()
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
        boletas = []
        recs = self._get_moves()
        for r in recs:
            grupos.setdefault(r.document_class_id.sii_code, [])
            grupos[r.document_class_id.sii_code].append(r.with_context(tax_detail=True)._dte())
        for b in self.boletas:
            boletas.append(b._dte())
        datos['Libro'] = {
            "PeriodoTributario": self.periodo_tributario,
            "TipoOperacion": self.tipo_operacion,
            "TipoLibro": self.tipo_libro,
            "FolioNotificacion": self.folio_notificacion,
            "TipoEnvio": self.tipo_envio,
            "CodigoRectificacion": self.codigo_rectificacion,
            "Documento": [{'TipoDTE': k, 'documentos': v} for k, v in grupos.items()],
            'FctProp': self.fact_prop,
            'boletas': boletas,
        }
        datos['test'] = True
        result = fe.libro(datos)
        envio_dte = result['sii_xml_request']
        doc_id = '%s_%s' % (self.tipo_operacion, self.periodo_tributario)
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
                        'model': 'account.move.book',
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
            self.state = self.sii_xml_request.state
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


class Boletas(models.Model):
    _name = 'account.move.book.boletas'
    _description = 'Detalle Boleta libro CV'

    currency_id = fields.Many2one('res.currency',
        string='Moneda',
        default=lambda self: self.env.user.company_id.currency_id,
        required=True,
        track_visibility='always')
    tipo_boleta = fields.Many2one('sii.document_class',
        string="Tipo de Boleta",
        required=True,
        domain=[('document_letter_id.name','in',['B','M'])])
    rango_inicial = fields.Integer(
        string="Rango Inicial",
        required=True)
    rango_final = fields.Integer(
        string="Rango Final",
        required=True)
    cantidad_boletas = fields.Integer(
        string="Cantidad Boletas",
        rqquired=True)
    neto = fields.Monetary(
        string="Monto Neto",
        required=True)
    impuesto = fields.Many2one('account.tax',
        string="Impuesto",
        required=True,
        domain=[('type_tax_use','!=','none'), '|', ('active', '=', False), ('active', '=', True)])
    monto_impuesto = fields.Monetary(
        compute='_monto_total',
        string="Monto Impuesto",
        required=True)
    monto_total = fields.Monetary(
        compute='_monto_total',
        string="Monto Total",
        required=True)
    book_id = fields.Many2one('account.move.book')

    @api.onchange( 'neto', 'impuesto')
    def _monto_total(self):
        for b in self:
            monto_impuesto = 0
            if b.impuesto and b.impuesto.amount > 0:
                monto_impuesto = b.monto_impuesto = b.neto * (b.impuesto.amount / 100)
            b.monto_total = b.neto + monto_impuesto

    @api.onchange('rango_inicial', 'rango_final')
    def get_cantidad(self):
        if not self.rango_inicial or not self.rango_final:
            return
        if self.rango_final < self.rango_inicial:
            raise UserError("¡El rango Final no puede ser menor al inicial")
        self.cantidad_boletas = self.rango_final - self.rango_inicial +1


class ImpuestosLibro(models.Model):
    _name="account.move.book.tax"
    _description = 'Detalle Impuesto Libro CV'

    def get_monto(self):
        for t in self:
            t.amount = t.debit - t.credit
            if t.book_id.tipo_operacion in [ 'VENTA' ]:
                t.amount = t.credit - t.debit

    tax_id = fields.Many2one('account.tax', string="Impuesto")
    credit = fields.Monetary(string="Créditos", default=0.00)
    debit = fields.Monetary(string="Débitos", default=0.00)
    amount = fields.Monetary(compute="get_monto", string="Monto")
    currency_id = fields.Many2one('res.currency',
        string='Moneda',
        default=lambda self: self.env.user.company_id.currency_id,
        required=True,
        track_visibility='always')
    book_id = fields.Many2one('account.move.book', string="Libro")
