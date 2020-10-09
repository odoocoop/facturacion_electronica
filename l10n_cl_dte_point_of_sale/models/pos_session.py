# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging
import json

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    secuencia_boleta = fields.Many2one(
            'ir.sequence',
            string='Documents Type',
        )
    secuencia_boleta_exenta = fields.Many2one(
            'ir.sequence',
            string='Documents Type',
        )
    start_number = fields.Integer(
            string='Folio Inicio',
        )
    start_number_exentas = fields.Integer(
            string='Folio Inicio Exentas',
        )
    numero_ordenes = fields.Integer(
            string="Número de órdenes",
            default=0,
        )
    numero_ordenes_exentas = fields.Integer(
            string="Número de órdenes exentas",
            default=0,
        )
    caf_files = fields.Char(
            compute='get_caf_string',
        )
    caf_files_exentas = fields.Char(
            compute='get_caf_string',
        )

    @api.model
    def create(self, values):
        pos_config = values.get('config_id') or self.env.context.get('default_config_id')
        config_id = self.env['pos.config'].browse(pos_config)
        if not config_id:
            raise UserError(_("You should assign a Point of Sale to your session."))
        if config_id.restore_mode:
            return super(PosSession, self).create(values)
        if config_id.secuencia_boleta:
            sequence = config_id.secuencia_boleta
            sequence.update_next_by_caf(increment=False)
            start_number = sequence.get_folio()
            values.update({
                'secuencia_boleta': sequence.id,
                'start_number': start_number,
            })
        if config_id.secuencia_boleta_exenta:
            sequence = config_id.secuencia_boleta_exenta
            sequence.update_next_by_caf(increment=False)
            start_number = sequence.get_folio()
            values.update({
                'secuencia_boleta_exenta': sequence.id,
                'start_number_exentas': start_number,
            })
        if self.env['product.template'].search([
                ('available_in_pos', '=', True),
                ('taxes_id.mepco', '!=', False)],
            limit=1):
            for t in self.env['account.tax'].sudo().search([
                ('mepco', '!=', False)]):
                t.verify_mepco(date_target=False,
                               currency_id=config_id.company_id.currency_id)
        return super(PosSession, self).create(values)

    def recursive_xml(self, el):
        if el.text and bool(el.text.strip()):
            return el.text
        res = {}
        for e in el:
            res.setdefault(e.tag, self.recursive_xml(e))
        return res

    @api.model
    def get_caf_string(self):
        for r in self:
            seq = r.config_id.secuencia_boleta
            if seq:
                folio = r.start_number
                caf_files = seq.get_caf_files(folio)
                if caf_files:
                    caffs = []
                    for caffile in caf_files:
                        xml = caffile.decode_caf()
                        caffs += [{xml.tag: self.recursive_xml(xml)}]
                    if caffs:
                        r.caf_files = json.dumps(
                            caffs, ensure_ascii=False)
            seq = r.config_id.secuencia_boleta_exenta
            if seq:
                folio = self.start_number_exentas
                caf_files = seq.get_caf_files(folio)
                if caf_files:
                    caffs = []
                    for caffile in caf_files:
                        xml = caffile.decode_caf()
                        caffs += [{xml.tag: self.recursive_xml(xml)}]
                        r.caf_files_exentas = json.dumps(
                            caffs, ensure_ascii=False)
