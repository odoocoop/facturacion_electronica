from odoo import api, fields, models
from odoo.tools.translate import _


class SOR(models.Model):
    _name = 'sale.order.referencias'
    _description = 'Línea de Referencias DTE para Pedidos de Venta'

    fecha_documento = fields.Date(
            string="Fecha Documento",
            required=True,
        )
    folio = fields.Char(
            string="Folio Referencia",
        )
    sii_referencia_TpoDocRef = fields.Many2one(
            'sii.document_class',
            string="Tipo de Documento SII",
        )
    motivo = fields.Char(
            string="Motivo",
        )
    so_id = fields.Many2one(
            'sale.order',
            ondelete='cascade',
            index=True,
            copy=False,
            string="Documento",
        )

