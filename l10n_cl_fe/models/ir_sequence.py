# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID
from odoo.tools.translate import _
from odoo.exceptions import UserError
from datetime import datetime, date
import pytz
import logging
_logger = logging.getLogger(__name__)


class IRSequence(models.Model):
    _inherit = "ir.sequence"

    @api.model
    def check_cafs(self):
        self._cr.execute(
        "SELECT id FROM ir_sequence WHERE autoreponer_caf and qty_available < nivel_minimo")
        for r in self.env['ir.sequence'].sudo().browse([x[0] for x in self._cr.fetchall()]):
            try:
                r.solicitar_caf()
            except Exception as e:
                _logger.warning("Error al solictar folios a secuencia %s: %s" % (r.sii_document_class_id.name, str(e)))

    def get_qty_available(self, folio=None):
        folio = folio or self._get_folio()
        try:
            cafs = self.get_caf_files(folio)
        except:
            cafs = False
        available = 0
        folio = int(folio)
        if cafs:
            for c in cafs:
                final = (c.final_nm +1)
                if folio >= c.start_nm and folio < final:
                    available += final - folio
                elif folio < final:
                    available += (final - c.start_nm)
        if available <= self.nivel_minimo:
            alert_msg = 'Nivel bajo de CAF para %s, quedan %s foliosself. Recuerde verificar su token apicaf.cl' % (self.sii_document_class_id.name, available)
            self.env['bus.bus'].sendone((
                self._cr.dbname,
                'ir.sequence',
                self.env.user.partner_id.id),
                {
                'title': "Alerta sobre Folios",
                 'message': alert_msg,
                 'url': 'res_config',
                 'type': 'dte_notif',
                })
        return available

    def solicitar_caf(self):
        firma = self.env.user.sudo(SUPERUSER_ID).get_digital_signature(self.company_id)
        wiz_caf = self.env['dte.caf.apicaf'].create({
                                    'company_id': self.company_id.id,
                                    'sequence_id': self.id,
                                    'firma': firma.id,
                                })
        wiz_caf.conectar_api()
        alert_msg = False
        if not wiz_caf.id_peticion:
            alert_msg = "Problema al conectar con apicaf.cl"
        else:
            cantidad = self.autoreponer_cantidad
            if wiz_caf.api_max_autor > 0 and cantidad > wiz_caf.api_max_autor:
                cantidad = wiz_caf.api_max_autor
            elif wiz_caf.api_max_autor == 0:
                self.autoreponer_caf = False
                alert_msg = 'El SII no permite solicitar más CAFs para %s, consuma los %s folios disponibles o verifique situación tributaria en www.sii.cl' % (
                    self.sii_document_class_id.name,
                    wiz_caf.api_folios_disp
                    )
        if alert_msg:
            _logger.warning(alert_msg)
            self.env['bus.bus'].sendone((
                self._cr.dbname,
                'ir.sequence',
                self.env.user.partner_id.id),
                {
                'title': "Alerta sobre Folios",
                'message': alert_msg,
                'url': 'res_config',
                'type': 'dte_notif',
                })
            return
        wiz_caf.cant_doctos = cantidad
        wiz_caf.obtener_caf()

    def _set_qty_available(self):
        self.qty_available = self.get_qty_available()

    @api.depends('dte_caf_ids', 'number_next_actual')
    def _qty_available(self):
        for i in self.sudo():
            if i.is_dte and i.sii_document_class_id:
                i._set_qty_available()

    sii_document_class_id = fields.Many2one(
            'sii.document_class',
            string='Tipo de Documento',
        )
    is_dte = fields.Boolean(
            string='IS DTE?',
            related='sii_document_class_id.dte',
        )
    dte_caf_ids = fields.One2many(
            'dte.caf',
            'sequence_id',
            string='DTE Caf',
        )
    qty_available = fields.Integer(
            string="Quantity Available",
            compute="_qty_available",
            store=True,
        )
    forced_by_caf = fields.Boolean(
            string="Forced By CAF",
        )
    nivel_minimo = fields.Integer(
        string="Nivel Mínimo de Folios",
        default=5,#@TODO hacerlo configurable
    )
    autoreponer_caf = fields.Boolean(
            string="Reposición Automática de CAF",
            default=False
    )
    autoreponer_cantidad = fields.Integer(
            string="Cantidad de Folios a Reponer",
            default=2
    )

    def _get_folio(self):
        return self.number_next_actual

    def time_stamp(self, formato='%Y-%m-%dT%H:%M:%S'):
        tz = pytz.timezone('America/Santiago')
        return datetime.now(tz).strftime(formato)

    def get_caf_file(self, folio=False, decoded=True):
        folio = folio or self._get_folio()
        caffiles = self.get_caf_files(folio)
        msg = '''No Hay caf para el documento: {}, está fuera de rango . Solicite un nuevo CAF en el sitio \
www.sii.cl'''.format(folio)
        if not caffiles:
            raise UserError(_('''No hay caf disponible para el documento %s folio %s. Por favor solicite y suba un CAF o solicite uno en el SII o Utilice la opción obtener folios en la secuencia (usando apicaf.cl).''' % (self.name, folio)))
        for caffile in caffiles:
            if int(folio) >= caffile.start_nm and int(folio) <= caffile.final_nm:
                if caffile.expiration_date:
                    if fields.Date.context_today(self) > caffile.expiration_date:
                        msg = "CAF Vencido. %s" % msg
                        continue
                if decoded:
                    return caffile.decode_caf()
                return caffile.caf_file
        raise UserError(_(msg))

    def get_caf_files(self, folio=None):
        '''
            Devuelvo caf actual y futuros
        '''
        folio = folio or self._get_folio()
        if not self.dte_caf_ids:
            raise UserError(_('''No hay CAFs disponibles para la secuencia de %s. Por favor suba un CAF o solicite uno en el SII.''' % (self.name)))
        cafs = self.dte_caf_ids
        cafs = sorted(cafs, key=lambda e: e.start_nm)
        result = []
        for caffile in cafs:
            if caffile.start_nm == 0:
                try:
                    caffile.load_caf()
                except Exception as e:
                    _logger.warning("error en cargar caff %s" % str(e))
            if int(folio) <= caffile.final_nm:
                result.append(caffile)
        if result:
            return result
        return False

    def update_next_by_caf(self, folio=None):
        folio = folio or self._get_folio()
        menor = False
        cafs = self.get_caf_files(folio)
        if not cafs:
            _logger.warning('No quedan CAFs para %s disponibles' % self.name)
            return
        for c in cafs:
            if not menor or c.start_nm < menor.start_nm:
                menor = c
        if menor and int(folio) < menor.start_nm:
            self.sudo(SUPERUSER_ID).write({'number_next': menor.start_nm})

    def _next_do(self):
        number_next = self.number_next
        if self.implementation == 'standard':
            number_next = self.number_next_actual
        folio = super(IRSequence, self)._next_do()
        if self.sii_document_class_id and self.forced_by_caf and self.dte_caf_ids:
            self.update_next_by_caf(folio)
            actual = self.number_next
            if self.implementation == 'standard':
                actual = self.number_next_actual
            if number_next +1 != actual: #Fue actualizado
                number_next = actual
                if self.implementation == 'no_gap':
                    self._cr.execute("SELECT number_next FROM %s WHERE id=%s FOR UPDATE NOWAIT" % (self._table, self.id))
                    self._cr.execute("UPDATE %s SET number_next=%s WHERE id=%s " % (self._table, number_next, self.id))
                    self.invalidate_cache(['number_next'], [self.id])
            folio = self.get_next_char(number_next)
        self._qty_available()
        return folio
