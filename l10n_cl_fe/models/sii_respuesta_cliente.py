# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)


class SIIRespuestaCliente(models.Model):
    _name = 'sii.respuesta.cliente'
    _description = 'Respuesta de cliente'

    type = fields.Selection(
            [
                ('RecepcionEnvio', 'Recepción Envío'),
                ('RecepcionDTE', 'Recepción Documento'),
                ('DocumentoRecibo', 'Recibo Mercaderías'),
                ('ResultadoDTE', 'Validación Comercial'),
            ]
        )
    recep_envio = fields.Selection(
            [
                ('no_revisado', 'No Revisado'),
                ('0', 'Conforme'),
                ('1', 'Error de Schema'),
                ('2', 'Error de Firma'),
                ('3', 'RUT Receptor No Corresponde'),
                ('90', 'Archivo Repetido'),
                ('91', 'Archivo Ilegible'),
                ('99', 'Envio Rechazado - Otros')
            ],
            string="Estado Envío",
        )
    merc_recinto = fields.Text(
            string="Recinto Recepción Mercadería"
        )
    merc_fecha = fields.Date(
            string="Fecha Respuesta Mercadería"
        )
    merc_declaracion = fields.Text(
            string="Texto Declaración"
        )
    merc_rut = fields.Text(
            string="Rut Receptor Mercaderia",
        )
    attachment_id = fields.Many2one(
            'ir.attachment',
        )
    glosa = fields.Text(
            string="Glosa"
        )
    id_respuesta = fields.Text(
            string="ID Respuesta",
        )
    recep_dte = fields.Selection(
            [
                ('no_revisado', 'No Revisado'),
                ('0', 'Conforme'),
                ('1', 'Error de Schema'),
                ('2', 'Error de Firma'),
                ('3', 'RUT Receptor No Corresponde'),
                ('90', 'Archivo Repetido'),
                ('91', 'Archivo Ilegible'),
                ('99', 'Envio Rechazado - Otros')
            ],
            string="Estado Recepción DTE",
        )
    merc_estado = fields.Selection(
            [
                ('no_revisado', 'No Revisado'),
                ('0', 'Conforme'),
                ('1', 'Error de Schema'),
                ('2', 'Error de Firma'),
                ('3', 'RUT Receptor No Corresponde'),
                ('90', 'Archivo Repetido'),
                ('91', 'Archivo Ilegible'),
                ('99', 'Envio Rechazado - Otros')
            ],
            string="Recepción de Mercaderías",
        )
    recep_comercial = fields.Selection(
            [
                ('no_revisado', 'No Revisado'),
                ('0', 'Conforme'),
                ('1', 'Error de Schema'),
                ('2', 'Error de Firma'),
                ('3', 'RUT Receptor No Corresponde'),
                ('90', 'Archivo Repetido'),
                ('91', 'Archivo Ilegible'),
                ('99', 'Envio Rechazado - Otros')
            ],
            string="Estado Recepción Envío",
        )
    exchange_id = fields.Many2one(
            'ir.attachment',
            string="XML de Intercambio"
        )
    company_id = fields.Many2one(
            'res.company',
            string="Compañia",
        )
