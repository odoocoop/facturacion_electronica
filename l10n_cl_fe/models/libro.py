# -*- coding: utf-8 -*-
from odoo import fields, models, api, tools
from odoo.tools.translate import _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
import logging
from lxml import etree
from lxml.etree import Element, SubElement
import pytz
import collections
_logger = logging.getLogger(__name__)
try:
    import xmltodict
except ImportError:
    _logger.info('Cannot import xmltodict library')

try:
    import dicttoxml
    dicttoxml.set_debug(False)
except ImportError:
    _logger.info('Cannot import dicttoxml library')


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
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    tipo_envio = fields.Selection([
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
        default=lambda self: fields.Date.context_today(self),)
    boletas = fields.One2many('account.move.book.boletas',
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
        if not self.periodo_tributario or not self.tipo_operacion:
            return
        current = datetime.strptime(self.periodo_tributario + '-01', '%Y-%m-%d' )
        next_month = current + relativedelta(months=1)
        docs = [False, 70, 71]
        operator = 'not in'
        query = [
            ('company_id', '=', self.company_id.id),
            ('sended', '=', False),
            ('date' , '<', next_month.strftime('%Y-%m-%d')),
            ]
        domain = 'sale'
        if self.tipo_operacion in [ 'COMPRA' ]:
            two_month = current + relativedelta(months=-2)
            query.append(('date' , '>=', two_month.strftime('%Y-%m-%d')))
            domain = 'purchase'
        elif self.tipo_operacion != 'BOLETA':
            #en ventas no considerar las boletas
            query.append(('document_class_id.sii_code', 'not in', (35, 38, 39, 41, 70, 71)))
        query.append(('journal_id.type', '=', domain))
        boleta_lines = [[5, ], ]
        impuesto_lines = [[5,],]
        if self.tipo_operacion in [ 'VENTA' ]:
            cfs = self.env['account.move.consumo_folios'].search([
                ('state', 'not in', ['draft', 'Anulado', 'Rechazado']),
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
                        lineas[tpo_doc] = {'cantidad': 0, 'neto': 0, 'monto_exento': 0, 'monto_impuesto': 0.0, 'monto_total': 0.0}
                    lineas[tpo_doc] = {
                                'cantidad': lineas[tpo_doc]['cantidad'] + cantidad,
                                'neto': lineas[tpo_doc]['neto'] + impuesto.monto_neto,
                                'monto_exento': lineas[tpo_doc]['monto_exento'] + impuesto.monto_exento,
                                'monto_impuesto': lineas[tpo_doc]['monto_impuesto'] + impuesto.monto_iva,
                                'monto_total': lineas[tpo_doc]['monto_total'] + impuesto.monto_total,
                            }
                for tpo_doc, det in lineas.items():
                    tax_id = self.env['account.tax'].search([('sii_code', '=', 14), ('type_tax_use', '=', 'sale'), ('company_id', '=', self.company_id.id)], limit=1) if tpo_doc.sii_code == 39 else self.env['account.tax'].search([('sii_code', '=', 0), ('type_tax_use', '=', 'sale'), ('company_id', '=', self.company_id.id)], limit=1)
                    line = {
                        'currency_id': self.env.user.company_id.currency_id,
                        'tipo_boleta': tpo_doc.id,
                        'cantidad_boletas': det['cantidad'],
                        'neto': det['neto'] or det['monto_exento'],
                        'monto_impuesto': det['monto_impuesto'],
                        'monto_total': det['monto_total'],
                        'impuesto': tax_id.id,
                    }
                    boleta_lines.append([0, 0, line])
        elif self.tipo_operacion in ['BOLETA']:
            docs = [35, 38, 39, 41]
            cfs = self.env['account.move.consumo_folios'].search([
                ('state', 'not in', ['draft', 'Anulado', 'Rechazado']),
                ('fecha_inicio', '>=', current),
                ('fecha_inicio', '<', next_month),
            ])
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
        for book in self:
            for mov in book.move_ids:
                totales = mov.totales_por_movimiento()
                book.total_afecto += totales['neto']
                book.total_exento += totales['exento']
                book.total_iva += totales['iva']
                book.total_otros_imps += totales['otros_imps']
                book.total += mov.amount

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

    def create_template_envio(self, RutEmisor, PeriodoTributario, FchResol,\
                              NroResol, EnvioDTE, subject_serial_number,\
                              TipoOperacion='VENTA',TipoLibro='MENSUAL',\
                              TipoEnvio='TOTAL',FolioNotificacion="123",\
                              IdEnvio='SetDoc'):
        if TipoOperacion == 'BOLETA' and TipoLibro not in ['ESPECIAL', 'RECTIFICA']:
            raise UserError("Boletas debe ser solamente Tipo Operación ESPECIAL")
        CodigoRectificacion = ''
        if TipoLibro in ['ESPECIAL'] or TipoOperacion in ['BOLETA']:
            FolioNotificacion = '\n<FolioNotificacion>' + FolioNotificacion + '</FolioNotificacion>'
        else:
            FolioNotificacion =''
        if TipoLibro == 'RECTIFICA':
            CodigoRectificacion = '\n<CodAutRec>' + self.codigo_rectificacion + '</CodAutRec>'

        if TipoOperacion in ['BOLETA']:
            TipoOperacion = ''
        else:
            TipoOperacion = '\n<TipoOperacion>'+TipoOperacion+'</TipoOperacion>'
        xml = '''<EnvioLibro ID="{10}">
<Caratula>
<RutEmisorLibro>{0}</RutEmisorLibro>
<RutEnvia>{1}</RutEnvia>
<PeriodoTributario>{2}</PeriodoTributario>
<FchResol>{3}</FchResol>
<NroResol>{4}</NroResol>{5}
<TipoLibro>{6}</TipoLibro>
<TipoEnvio>{7}</TipoEnvio>{8}{11}
</Caratula>
{9}
</EnvioLibro>
'''.format(RutEmisor,
           subject_serial_number,
           PeriodoTributario,
           FchResol,
           NroResol,
           TipoOperacion,
           TipoLibro,
           TipoEnvio,
           FolioNotificacion,
           EnvioDTE,
           IdEnvio,
           CodigoRectificacion,
       )
        return xml

    def time_stamp(self, formato='%Y-%m-%dT%H:%M:%S'):
        tz = pytz.timezone('America/Santiago')
        return datetime.now(tz).strftime(formato)

    def create_template_env(self, doc,simplificado=False):
        simp = 'http://www.sii.cl/SiiDte LibroCV_v10.xsd'
        if simplificado:
            simp ='http://www.sii.cl/SiiDte LibroCVS_v10.xsd'
        xml = '''<LibroCompraVenta xmlns="http://www.sii.cl/SiiDte" \
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" \
xsi:schemaLocation="{0}" \
version="1.0">
{1}</LibroCompraVenta>'''.format(simp, doc)
        return xml

    def create_template_env_boleta(self, doc):
        xsd = 'http://www.sii.cl/SiiDte LibroBOLETA_v10.xsd'
        xml = '''<LibroBoleta xmlns="http://www.sii.cl/SiiDte" \
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" \
xsi:schemaLocation="{0}" \
version="1.0">
{1}</LibroBoleta>'''.format(xsd, doc)
        return xml

    def get_resolution_data(self, comp_id):
        resolution_data = {
            'dte_resolution_date': comp_id.dte_resolution_date,
            'dte_resolution_number': comp_id.dte_resolution_number}
        return resolution_data

    @api.multi
    def get_xml_file(self):
        return {
            'type' : 'ir.actions.act_url',
            'url': '/download/xml/libro/%s' % (self.id),
            'target': 'self',
        }

    def format_vat(self, value):
        if not value or value=='' or value == 0:
            value ="CL666666666"
            #@TODO opción de crear código de cliente en vez de rut genérico
        rut = value[:10] + '-' + value[10:]
        rut = rut.replace('CL0','').replace('CL','')
        return rut

    @api.onchange('periodo_tributario', 'tipo_operacion')
    def _setName(self):
        self.name = self.tipo_operacion or ''
        if self.periodo_tributario:
            self.name += " " + self.periodo_tributario

    @api.multi
    def validar_libro(self):
        self._validar()
        return self.write({'state': 'NoEnviado'})

    def _acortar_str(self, texto, size=1):
        c = 0
        cadena = ""
        while c < size and c < len(texto):
            cadena += texto[c]
            c += 1
        return cadena

    def _TpoImp(self, tasa):
        #if tasa.sii_code in [14, 1]:
        return 1
        #if tasa.sii_code in []: determinar cuando es 18.211 // zona franca
        #    return 2

    def getResumen(self, rec):
        no_product = False
        ob = self.env['account.invoice']
        inv = ob.search([
                        ('move_id','=',rec.id),
                        ])
        det = collections.OrderedDict()
        det['TpoDoc'] = rec.document_class_id.sii_code
        #det['Emisor']
        #det['IndFactCompra']
        if self.tipo_operacion in ['COMPRA']:
            det['NroDoc'] = int(rec.ref)
        else:
            det['NroDoc'] = int(rec.sii_document_number)
        if rec.canceled:
            det['Anulado'] = 'A'
        #det['Operacion']
        #det['TotalesServicio']
        imp = {}
        TaxMnt = 0
        MntExe = 0
        MntIVA = 0
        Neto = 0
        ActivoFijo = [0,0]
        ivas = {}
        for l in rec.line_ids:
            if l.tax_line_id:
                if l.tax_line_id and l.tax_line_id.amount > 0:
                    if l.tax_line_id.sii_code in [14, 15, 17, 18, 19, 30,31, 32 ,33, 34, 36, 37, 38, 39, 41, 47, 48]: # diferentes tipos de IVA retenidos o no
                        if not l.tax_line_id.id in ivas:
                            ivas[l.tax_line_id.id] = {'det': l.tax_line_id, 'credit':0, 'debit': 0}
                        if l.credit > 0:
                            ivas[l.tax_line_id.id]['credit'] += l.credit
                            if l.tax_line_id.activo_fijo:
                                ActivoFijo[1] += l.credit
                        else:
                            ivas[l.tax_line_id.id]['debit'] += l.debit
                            if l.tax_line_id.activo_fijo:
                                ActivoFijo[1] += l.debit
                    else:
                        if not l.tax_line_id.id in imp:
                            imp[l.tax_line_id.id] = {'imp':l.tax_line_id, 'Mnt':0}
                        if l.credit > 0:
                            imp[l.tax_line_id.id]['Mnt'] += l.credit
                            TaxMnt += l.credit
                        else:
                            imp[l.tax_line_id.id]['Mnt'] += l.debit
                            TaxMnt += l.debit
            elif l.tax_ids and l.tax_ids[0].no_rec:
                if not l.tax_ids[0].id in imp:
                    imp[l.tax_ids[0].id] = {'imp':l.tax_ids[0], 'Mnt':0}
                if l.credit > 0:
                    imp[l.tax_ids[0].id]['Mnt'] += l.credit
                    TaxMnt += l.credit
                else:
                    imp[l.tax_ids[0].id]['Mnt'] += l.debit
                    TaxMnt += l.debit
            elif l.tax_ids and l.tax_ids[0].amount > 0:
                if l.credit > 0:
                    Neto += l.credit
                    if l.tax_ids[0].activo_fijo:
                        ActivoFijo[0] += l.credit
                else:
                    Neto += l.debit
                    if l.tax_ids[0].activo_fijo:
                        ActivoFijo[0] += l.debit
            elif l.tax_ids and l.tax_ids[0].amount == 0: #caso monto exento
                if l.credit > 0:
                    MntExe += l.credit
                else:
                    MntExe += l.debit
        if ivas:
            for i, value in ivas.items():
                det['TpoImp'] = self._TpoImp(value['det'])
                det['TasaImp'] = round(value['det'].amount,2)
                continue
        #det['IndServicio']
        #det['IndSinCosto']
        det['FchDoc'] = rec.date.strftime(DF)
        if rec.journal_id.sii_code:
            det['CdgSIISucur'] = rec.journal_id.sii_code
        det['RUTDoc'] = self.format_vat(rec.partner_id.vat)
        det['RznSoc'] = rec.partner_id and rec.partner_id.name[:50] or 'Anonimo'
        refs = []
        for ref in inv.referencias:
            if ref.sii_referencia_CodRef and ref.sii_referencia_TpoDocRef.sii_code in allowed_docs:
                ref_line = collections.OrderedDict()
                ref_line['TpoDocRef'] = ref.sii_referencia_TpoDocRef.sii_code
                ref_line['FolioDocRef'] = ref.origen
                refs.append(ref_line)
        if refs:
            det['item_refs'] = refs
        if MntExe > 0 :
            det['MntExe'] = int(round(MntExe,0))
        elif self.tipo_operacion in ['VENTA'] and not Neto > 0:
            det['MntExe'] = 0
        if Neto > 0:
            det['MntNeto'] = int(round(Neto))
            if ivas: # Es algún tipo de iva que puede ser adicional o anticipado
                MntIVA = 0
                for key, i in ivas.items():
                    Mnt = i['credit'] or i['debit']
                    if round(i['credit'] - i['debit']) != 0:
                        Mnt = i['credit'] + i['debit']
                    if i['det'].sii_code not in [14]:
                        imp[i['det'].id] = {'imp': i['det'], 'Mnt': Mnt}
                    MntIVA += int(round(Mnt))
                if not rec.no_rec_code and not rec.iva_uso_comun:
                    det['MntIVA'] = MntIVA
                if ActivoFijo != [0, 0]:
                    det['MntActivoFijo'] = ActivoFijo[0]
                    det['MntIVAActivoFijo'] = ActivoFijo[1]
                if rec.no_rec_code:
                    det['IVANoRec'] = collections.OrderedDict()
                    det['IVANoRec']['CodIVANoRec'] = rec.no_rec_code
                    det['IVANoRec']['MntIVANoRec'] = MntIVA
                if rec.iva_uso_comun:
                    det['IVAUsoComun'] = MntIVA
        if imp:
            imps = []
            for key, t in imp.items():
                otro = {}
                if t['imp'].no_rec:
                    otro['MntSinCred'] = int(round(t['Mnt']))
                else:
                    otro['OtrosImp'] = collections.OrderedDict()
                    otro['OtrosImp']['CodImp'] = t['imp'].sii_code
                    otro['OtrosImp']['TasaImp'] = round(t['imp'].amount, 2)
                    otro['OtrosImp']['MntImp'] = int(round(t['Mnt']))
                imps.append(otro)
            det['itemOtrosImp'] = imps
        if ivas:
            for key, i in ivas.items():
                tasa = i['det']
                if tasa.sii_type in ['R']:
                    if tasa.retencion == tasa.amount:
                        det['IVARetTotal'] = int(round(i['credit'] or i['debit']))
                        MntIVA -= det['IVARetTotal']
                    else:
                        reten = i['credit']
                        tax = i['debit']
                        if self.tipo_operacion in ['VENTA']:
                            tax = i['credit']
                            reten = i['debit']
                        det['IVARetParcial'] = int(round(reten))
                        det['IVANoRetenido'] = int(round(tax))
                        MntIVA -= det['IVARetParcial']
        monto_total = int(round((Neto + MntExe + TaxMnt + MntIVA), 0))
        if no_product :
            monto_total = 0
        det['MntTotal'] = monto_total
        return det

    def _setResumenBoletas(self, rec):
        det = collections.OrderedDict()
        det['TpoDoc'] = rec.tipo_boleta.sii_code
        det['TotDoc'] = det['NroDoc'] = rec.cantidad_boletas
        if rec.impuesto.amount > 0:
            #det['TpoImp'] = self._TpoImp(rec.impuesto)
            det['TasaImp'] = round(rec.impuesto.amount,2)
            det['MntNeto'] = int(round(rec.neto))
            det['MntIVA'] = int(round(rec.monto_impuesto))
        else:
            det['MntExe'] = int(round(rec.neto))
        det['MntTotal'] = int(round(rec.monto_total))
        return det

    def _process_imps(self, tax_line_id, totales=0, currency=None, Neto=0, TaxMnt=0, MntExe=0, ivas={}, imp={}):
        mnt = tax_line_id.compute_all(totales,  currency, 1)['taxes'][0]
        if mnt['amount'] < 0:
            mnt['amount'] *= -1
            mnt['base'] *= -1
        if tax_line_id.sii_code in [14, 15, 17, 18, 19, 30, 31, 32, 33, 34, 36, 37, 38, 39, 41, 47, 48]: # diferentes tipos de IVA retenidos o no
            ivas.setdefault(tax_line_id.id, [tax_line_id, 0])
            ivas[tax_line_id.id][1] += mnt['amount']
            TaxMnt += mnt['amount']
            Neto += mnt['base']
        else:
            imp.setdefault(tax_line_id.id, [tax_line_id, 0])
            imp[tax_line_id.id][1] += mnt['amount']
            if tax_line_id.amount == 0:
                MntExe += mnt['base']
        return Neto, TaxMnt, MntExe, ivas, imp

    def _es_iva(self, tax):
        if tax.sii_code in [14, 15, 17, 18, 19, 30,31, 32 ,33, 34, 36, 37, 38, 39, 41, 47, 48]:
            return True
        return False

    def _get_date(self, rec):
        return {
            'FchEmiDoc': rec.date.strftime(DF),
            'FchVencDoc': rec.date.strftime(DF)
        }

    def _get_datos(self, rec):
        Neto = 0
        MntExe = 0
        TaxMnt = 0
        for l in rec.line_ids:
            if l.tax_line_id:
                if l.tax_line_id and l.tax_line_id.amount > 0: #supuesto iva único
                    if self._es_iva(l.tax_line_id): # diferentes tipos de IVA retenidos o no
                        if l.credit > 0:
                            TaxMnt += l.credit
                        else:
                            TaxMnt += l.debit
            elif l.tax_ids and l.tax_ids[0].amount > 0:
                if l.credit > 0:
                    Neto += l.credit
                else:
                    Neto += l.debit
            elif l.tax_ids and l.tax_ids[0].amount == 0: #caso monto exento
                if l.credit > 0:
                    MntExe += l.credit
                else:
                    MntExe += l.debit
        TasaIVA = self.env['account.move.line'].search([('move_id', '=', rec.id), ('tax_line_id.amount', '>', 0)], limit=1).tax_line_id.amount
        return Neto, MntExe, TaxMnt, TasaIVA

    def _get_resumen_boleta(self, rec):
        det = collections.OrderedDict()
        det['TpoDoc'] = rec.document_class_id.sii_code
        det['FolioDoc'] = int(rec.sii_document_number)
        #if self.env['account.invoice.referencias'].search(
        #        [('origen', '=', det['FolioDoc']),
        #         ('sii_referencia_TpoDocRef', '=', rec.document_class_id.id),
        #         ('sii_referencia_CodRef', '=', '1')
        #        ]) or  \
        #    (rec.document_class_id.sii_code in [39, 41] and
        #     self.env['pos.order.referencias'].search([
        #         ('origen', '=', det['FolioDoc']),
        #         ('sii_referencia_TpoDocRef', '=', rec.document_class_id.id),
        #         ('sii_referencia_CodRef', '=', '1')
        #        ])
        #    ):
        #    det['Anulado'] = 'A'
        det['TpoServ'] = 3
        det.update(self._get_date(rec))
        #det['PeriodoDesde']
        #det['PeriodoHasta']
        #det['CdgSIISucur']
        MntTotal = 0
        Neto, MntExe, TaxMnt, TasaIVA = self._get_datos(rec)
        MntTotal = Neto + MntExe + TaxMnt
        det['RUTCliente'] = self.format_vat(rec.partner_id.vat)
        if MntExe > 0 :
            det['MntExe'] = self.currency_id.round(MntExe)
        if TaxMnt > 0:
            det['MntIVA'] = self.currency_id.round(TaxMnt)
            det['TasaIVA'] = TasaIVA
        det['MntNeto'] = self.currency_id.round(Neto)
        det['MntTotal'] = self.currency_id.round(MntTotal)
        return det

    def _procesar_otros_imp(self, resumen, resumenP):
        no_rec = 0 if 'TotImpSinCredito' not in resumenP else resumenP['TotImpSinCredito']
        if not 'itemOtrosImp' in resumenP :
            tots = []
            for o in resumen['itemOtrosImp']:
                tot = {}
                if 'MntSinCred' not in o:
                    cod = o['OtrosImp']['CodImp']
                    tot['TotOtrosImp'] = collections.OrderedDict()
                    tot['TotOtrosImp']['CodImp']  = cod
                    tot['TotOtrosImp']['TotMntImp']  = o['OtrosImp']['MntImp']
                    #tot['FctImpAdic']
                    tot['TotOtrosImp']['TotCredImp']  = o['OtrosImp']['MntImp']
                    tots.append(tot)
                else:
                    no_rec += o['MntSinCred']
            if tots:
                resumenP['itemOtrosImp'] = tots
            if no_rec > 0:
                resumenP['TotImpSinCredito'] = no_rec
            return resumenP
        seted = False
        itemOtrosImp = []
        for r in resumen['itemOtrosImp']:
            cod = r['OtrosImp']['CodImp'].replace('_no_rec','')
            for o in resumenP['itemOtrosImp']:
                if o['TotOtrosImp']['CodImp'] == cod:
                    o['TotOtrosImp']['TotMntImp'] += r['OtrosImp']['MntImp']
                    if cod == r['OtrosImp']['CodImp'] and not 'TotCredImp' in o['TotOtrosImp']:
                        o['TotOtrosImp']['TotCredImp'] = r['OtrosImp']['MntImp']
                    elif cod == r['OtrosImp']['CodImp']:
                        o['TotOtrosImp']['TotCredImp'] += r['OtrosImp']['MntImp']
                    seted = True
                    itemOtrosImp.append(o)
                else:
                    no_rec += o['OtrosImp']['MntImp']
            if not seted:
                if cod == o['OtrosImp']['CodImp']:
                    tot = {}
                    tot['TotOtrosImp'] = collections.OrderedDict()
                    tot['TotOtrosImp']['CodImp'] = cod
                    tot['TotOtrosImp']['TotMntImp'] = r['OtrosImp']['MntImp']
                    #tot['FctImpAdic']
                    tot['TotOtrosImp']['TotCredImp'] += o['OtrosImp']['MntImp']
                    itemOtrosImp.append(tot)
                else:
                    no_rec += o['OtrosImp']['MntImp']

        resumenP['itemOtrosImp'] = itemOtrosImp
        if not 'TotImpSinCredito' in resumenP and no_rec > 0:
            resumenP['TotImpSinCredito'] += no_rec
        elif no_rec:
            resumenP['TotImpSinCredito'] = no_rec
        return resumenP

    def _setResumenPeriodo(self, resumen, resumenP):
        resumenP['TpoDoc'] = resumen['TpoDoc']
        if 'TpoImp' in resumen:
            resumenP['TpoImp'] = resumen['TpoImp'] or 1
        if not 'TotDoc' in resumenP:
            resumenP['TotDoc'] = 1
            if 'TotDoc' in resumen:
                resumenP['TotDoc'] = resumen['TotDoc']
        else:
            resumenP['TotDoc'] += 1
        if 'TotAnulado' in resumenP and 'Anulado' in resumen:
            resumenP['TotAnulado'] += 1
            return resumenP
        elif 'Anulado' in resumen:
            resumenP['TotAnulado'] = 1
            return resumenP
        if 'MntExe' in resumen and not 'TotMntExe' in resumenP:
            resumenP['TotMntExe'] = resumen['MntExe']
        elif 'MntExe' in resumen:
            resumenP['TotMntExe'] += resumen['MntExe']
        elif not 'TotMntExe' in resumenP:
            resumenP['TotMntExe'] = 0
        if 'MntNeto' in resumen and not 'TotMntNeto' in resumenP:
            resumenP['TotMntNeto'] = resumen['MntNeto']
        elif 'MntNeto' in resumen:
            resumenP['TotMntNeto'] += resumen['MntNeto']
        elif not 'TotMntNeto' in resumenP:
            resumenP['TotMntNeto'] = 0
        if 'TotOpIVARec' in resumen:
            resumenP['TotOpIVARec'] = resumen['OpIVARec']
        if 'MntIVA' in resumen and not 'TotMntIVA' in resumenP:
            resumenP['TotMntIVA'] = resumen['MntIVA']
        elif 'MntIVA' in resumen:
            resumenP['TotMntIVA'] += resumen['MntIVA']
        elif not 'TotMntIVA' in resumenP:
            resumenP['TotMntIVA'] = 0
        if 'MntActivoFijo' in resumen and not 'TotOpActivoFijo'in resumenP:
            resumenP['TotOpActivoFijo'] = resumen['MntActivoFijo']
            resumenP['TotMntIVAActivoFijo'] = resumen['MntIVAActivoFijo']
        elif 'MntActivoFijo' in resumen:
            resumenP['TotOpActivoFijo'] += resumen['MntActivoFijo']
            resumenP['TotMntIVAActivoFijo'] += resumen['MntIVAActivoFijo']
        if 'IVANoRec' in resumen and not 'itemNoRec' in resumenP:
            tot = {}
            tot['TotIVANoRec'] = collections.OrderedDict()
            tot['TotIVANoRec']['CodIVANoRec'] = resumen['IVANoRec']['CodIVANoRec']
            tot['TotIVANoRec']['TotOpIVANoRec'] = 1
            tot['TotIVANoRec']['TotMntIVANoRec'] = resumen['IVANoRec']['MntIVANoRec']
            resumenP['itemNoRec'] = [tot]
        elif 'IVANoRec' in resumen:
            seted = False
            itemNoRec = []
            for r in resumenP['itemNoRec']:
                if r['TotIVANoRec']['CodIVANoRec'] == resumen['IVANoRec']['CodIVANoRec']:
                    r['TotIVANoRec']['TotOpIVANoRec'] += 1
                    r['TotIVANoRec']['TotMntIVANoRec'] += resumen['IVANoRec']['MntIVANoRec']
                    seted = True
                itemNoRec.extend([r])
            if not seted:
                tot = {}
                tot['TotIVANoRec'] = collections.OrderedDict()
                tot['TotIVANoRec']['CodIVANoRec'] = resumen['IVANoRec']['CodIVANoRec']
                tot['TotIVANoRec']['TotOpIVANoRec'] = 1
                tot['TotIVANoRec']['TotMntIVANoRec'] = resumen['IVANoRec']['MntIVANoRec']
                itemNoRec.extend([tot])
            resumenP['itemNoRec'] = itemNoRec

        if 'IVAUsoComun' in resumen and not 'TotOpIVAUsoComun' in resumenP:
            resumenP['TotOpIVAUsoComun'] = 1
            resumenP['TotIVAUsoComun'] = resumen['IVAUsoComun']
            resumenP['FctProp'] = self.fact_prop
            resumenP['TotCredIVAUsoComun'] = int(round((resumen['IVAUsoComun'] * self.fact_prop )))
        elif 'IVAUsoComun' in resumen:
            resumenP['TotOpIVAUsoComun'] += 1
            resumenP['TotIVAUsoComun'] += resumen['IVAUsoComun']
            resumenP['TotCredIVAUsoComun'] += int(round((resumen['IVAUsoComun'] * self.fact_prop )))
        if 'itemOtrosImp' in resumen:
            resumenP = self._procesar_otros_imp(resumen, resumenP)
        if 'IVARetTotal' in resumen and not 'TotOpIVARetTotal' in resumenP:
            resumenP['TotIVARetTotal'] = resumen['IVARetTotal']
        elif 'IVARetTotal' in resumen:
            resumenP['TotIVARetTotal'] += resumen['IVARetTotal']
        if 'IVARetParcial' in resumen and not 'TotOpIVARetParcial' in resumenP:
            resumenP['TotIVARetParcial'] = resumen['IVARetParcial']
            resumenP['TotIVANoRetenido'] = resumen['IVANoRetenido']
        elif 'IVARetParcial' in resumen:
            resumenP['TotIVARetParcial'] += resumen['IVARetParcial']
            resumenP['TotIVANoRetenido'] += resumen['IVANoRetenido']

        #@TODO otros tipos IVA
        if not 'TotMntTotal' in resumenP:
            resumenP['TotMntTotal'] = resumen['MntTotal']
        else:
            resumenP['TotMntTotal'] += resumen['MntTotal']
        return resumenP

    def _setResumenPeriodoBoleta(self, resumen, resumenP):
        resumenP['TpoDoc'] = resumen['TpoDoc']
        if 'Anulado' in resumen and 'TotAnulado' in resumenP:
            resumenP['TotAnulado'] += 1
            return resumenP
        elif 'Anulado' in resumen:
            resumenP['TotAnulado'] = 1
            return resumenP
        if not 'TotalesServicio' in resumenP:
            resumenP['TotalesServicio'] = collections.OrderedDict()
            resumenP['TotalesServicio']['TpoServ'] = resumen['TpoServ']#@TODO separar por tipo de servicio
            resumenP['TotalesServicio']['TotDoc'] = 0
        resumenP['TotalesServicio']['TotDoc'] += 1
        if 'MntExe' in resumen and not 'TotMntExe' in resumenP['TotalesServicio']:
            resumenP['TotalesServicio']['TotMntExe'] = resumen['MntExe']
        elif 'MntExe' in resumen:
            resumenP['TotalesServicio']['TotMntExe'] += resumen['MntExe']
        elif not 'TotMntExe' in resumenP['TotalesServicio']:
            resumenP['TotalesServicio']['TotMntExe'] = 0
        if 'MntNeto' in resumen and 'TotMntNeto' not in resumenP['TotalesServicio']:
            resumenP['TotalesServicio']['TotMntNeto'] = resumen['MntNeto']
        elif 'MntNeto' in resumen:
            resumenP['TotalesServicio']['TotMntNeto'] += resumen['MntNeto']
        elif not 'TotMntNeto' in resumenP['TotalesServicio']:
            resumenP['TotalesServicio']['TotMntNeto'] = 0
        if 'MntIVA' in resumen and resumen['MntIVA'] > 0:
            resumenP['TotalesServicio']['TasaIVA'] = resumen['TasaIVA']
        if 'MntIVA' in resumen and not 'TotMntIVA' in resumenP['TotalesServicio']:
            resumenP['TotalesServicio']['TotMntIVA'] = resumen['MntIVA']
        elif 'MntIVA' in resumen:
            resumenP['TotalesServicio']['TotMntIVA'] += resumen['MntIVA']
        elif not 'TotMntIVA' in resumenP['TotalesServicio']:
            resumenP['TotalesServicio']['TotMntIVA'] = 0
        if not 'TotMntTotal' in resumenP['TotalesServicio']:
            resumenP['TotalesServicio']['TotMntTotal'] = resumen['MntTotal']
        else:
            resumenP['TotalesServicio']['TotMntTotal'] += resumen['MntTotal']
        return resumenP

    def _get_moves(self):
        recs = []
        for rec in self.with_context(lang='es_CL').move_ids:
            rec.sended = True
            document_class_id = rec.document_class_id
            if not document_class_id or document_class_id.sii_code in [39, 41]\
            or rec.sii_document_number in [False, 0]:
                continue
            recs.append(rec)
        return recs

    def _validar(self):
        dicttoxml.set_debug(False)
        company_id = self.company_id
        signature_id = self.env.user.get_digital_signature(self.company_id)
        if not signature_id:
            raise UserError(_('''There are not a Signature Cert Available for this user, pleaseupload your signature or tell to someelse.'''))
        resumenes = []
        resumenesPeriodo = {}
        recs = self._get_moves()
        for rec in recs:
            TpoDoc = rec.document_class_id.sii_code
            if TpoDoc not in resumenesPeriodo:
                resumenesPeriodo[TpoDoc] = {}
            if self.tipo_operacion == 'BOLETA':
                resumen = self._get_resumen_boleta(rec)
                resumenesPeriodo[TpoDoc] = self._setResumenPeriodoBoleta(resumen, resumenesPeriodo[TpoDoc])
                del(resumen['MntNeto'])
                del(resumen['MntIVA'])
                if resumen.get('TasaIVA'):
                    del(resumen['TasaIVA'])
                resumenes.extend([{'Detalle': resumen}])
            else:
                resumen = self.getResumen(rec)
                resumenes.extend([{'Detalle': resumen}])
                resumenesPeriodo[TpoDoc] = self._setResumenPeriodo(resumen, resumenesPeriodo[TpoDoc])
        self.with_context(lang='es_CL').move_ids.write({'sended': True})
        if self.boletas:#no es el libro de boletas especial
            for boletas in self.boletas:
                resumenesPeriodo[boletas.tipo_boleta.id] = {}
                resumen = self._setResumenBoletas(boletas)
                #del(resumen['TotDoc'])
                resumenesPeriodo[boletas.tipo_boleta.id] = self._setResumenPeriodo(resumen, resumenesPeriodo[boletas.tipo_boleta.id])
                #resumenes.extend([{'Detalle':resumen}])
        lista = ['TpoDoc', 'TpoImp', 'TotDoc', 'TotAnulado', 'TotMntExe', 'TotMntNeto', 'TotalesServicio', 'TotOpIVARec',
                'TotMntIVA', 'TotMntIVA', 'TotOpActivoFijo', 'TotMntIVAActivoFijo', 'itemNoRec', 'TotOpIVAUsoComun',
                'TotIVAUsoComun', 'FctProp', 'TotCredIVAUsoComun', 'itemOtrosImp', 'TotImpSinCredito', 'TotIVARetTotal',
                  'TotIVARetParcial', 'TotMntTotal', 'TotIVANoRetenido',
                 'TotTabPuros', 'TotTabCigarrillos', 'TotTabElaborado', 'TotImpVehiculo',]
        ResumenPeriodo=[]
        for r, value in resumenesPeriodo.items():
            total = collections.OrderedDict()
            if value:
                for v in lista:
                    if v in value:
                        total[v] = value[v]
                ResumenPeriodo.extend([{'TotalesPeriodo':total}])
        dte = collections.OrderedDict()
        if ResumenPeriodo:
            dte['ResumenPeriodo'] = ResumenPeriodo
            dte['item'] = resumenes
        dte['TmstFirma'] = self.time_stamp()
        resol_data = self.get_resolution_data(company_id)
        RUTEmisor = self.format_vat(company_id.vat)
        xml = dicttoxml.dicttoxml(
            dte, root=False, attr_type=False).decode()
        doc_id =  self.tipo_operacion+'_'+self.periodo_tributario
        libro = self.create_template_envio(
                    RUTEmisor,
                    self.periodo_tributario,
                    resol_data['dte_resolution_date'],
                    resol_data['dte_resolution_number'],
                    xml,
                    signature_id.subject_serial_number,
                    self.tipo_operacion,
                    self.tipo_libro,
                    self.tipo_envio,
                    self.folio_notificacion,
                    doc_id)
        xml  = self.create_template_env(libro)
        env = 'libro'
        if self.tipo_operacion in['BOLETA']:
                xml = self.create_template_env_boleta(libro)
                env = 'libro_boleta'
        root = etree.XML( xml )
        xml_pret = etree.tostring(root, pretty_print=True).decode('iso-8859-1')\
                .replace('<item/>','\n')\
                .replace('<item>','\n').replace('</item>','')\
                .replace('<itemNoRec>','').replace('</itemNoRec>','\n')\
                .replace('<itemOtrosImp>','').replace('</itemOtrosImp>','\n')\
                .replace('<item_refs>','').replace('</item_refs>','\n')\
                .replace('_no_rec','')
        envio_dte = self.env['account.invoice'].sign_full_xml(
            xml_pret,
            doc_id,
            env)
        self.sii_xml_request = self.env['sii.xml.envio'].create({
            'xml_envio': envio_dte,
            'name': doc_id,
            'company_id': company_id.id,
        }).id

    @api.multi
    def do_dte_send_book(self):
        if self.state not in ['draft', 'NoEnviado', 'Rechazado']:
            raise UserError("El Libro ya ha sido enviado")
        if not self.sii_xml_request or self.sii_xml_request.state == "Rechazado":
            if self.sii_xml_request:
                self.sii_xml_request.unlink()
            self._validar()
        self.env['sii.cola_envio'].create({
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

    @api.multi
    def action_cancel(self):
        self.write({'state': 'Anulado'})
        return True
        
    @api.multi
    def action_cancel_to_draft(self):
        if self.move_ids:
            self.with_context(lang='es_CL').move_ids.write({'sended': False})
        self.write({'state': 'draft',
                    'move_ids': [(6, 0, [])],
                    'boletas': [(6, 0, [])],
                    'sii_xml_request': "",
                    })
        return True


class Boletas(models.Model):
    _name = 'account.move.book.boletas'

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
        string="Monto Impuesto",
        required=True)
    monto_total = fields.Monetary(
        string="Monto Total",
        required=True)
    book_id = fields.Many2one('account.move.book')

    @api.onchange('rango_inicial', 'rango_final')
    def get_cantidad(self):
        if not self.rango_inicial or not self.rango_final:
            return
        if self.rango_final < self.rango_inicial:
            raise UserError("¡El rango Final no puede ser menor al inicial")
        self.cantidad_boletas = self.rango_final - self.rango_inicial +1


class ImpuestosLibro(models.Model):
    _name="account.move.book.tax"

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
