from odoo import fields, models


class partner_activities(models.Model):
    _name = "sii.activity.description"
    _description = "SII Economical Activities Printable Description"

    name = fields.Char(string="Glosa", required=True, translate=True,)
    vat_affected = fields.Selection(
        (("SI", "Si"), ("NO", "No"), ("ND", "ND")), string="VAT Affected", required=True, default="SI",
    )
    active = fields.Boolean(string="Active", help="Allows you to hide the activity without removing it.", default=True,)
