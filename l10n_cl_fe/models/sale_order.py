from odoo import api, fields, models


class SO(models.Model):
    _inherit = "sale.order"

    acteco_ids = fields.Many2many("partner.activities", related="partner_invoice_id.acteco_ids",)
    acteco_id = fields.Many2one("partner.activities", string="Partner Activity",)
    referencia_ids = fields.One2many("sale.order.referencias", "so_id", string="Referencias de documento")

    @api.multi
    def _prepare_invoice(self):
        vals = super(SO, self)._prepare_invoice()
        if self.acteco_id:
            vals["acteco_id"] = self.acteco_id.id
        if self.referencia_ids:
            vals["referencias"] = []
            for ref in self.referencia_ids:
                vals["referencias"].append(
                    (
                        0,
                        0,
                        {
                            "origen": ref.folio,
                            "sii_referencia_TpoDocRef": ref.sii_referencia_TpoDocRef.id,
                            "motivo": ref.motivo,
                            "fecha_documento": ref.fecha_documento,
                        },
                    )
                )
        return vals

    @api.depends("order_line.price_total")
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            amount_untaxed = order.currency_id.round(amount_untaxed)
            amount_tax = order.currency_id.round(amount_tax)
            order.update(
                {
                    "amount_untaxed": amount_untaxed,
                    "amount_tax": amount_tax,
                    "amount_total": amount_untaxed + amount_tax,
                }
            )


class SOL(models.Model):
    _inherit = "sale.order.line"

    @api.depends("product_uom_qty", "discount", "price_unit", "tax_id")
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            taxes = line.tax_id.compute_all(
                line.price_unit,
                line.order_id.currency_id,
                line.product_uom_qty,
                product=line.product_id,
                partner=line.order_id.partner_shipping_id,
                discount=line.discount,
                uom_id=line.product_uom,
            )
            line.update(
                {
                    "price_tax": sum(t.get("amount", 0.0) for t in taxes.get("taxes", [])),
                    "price_total": taxes["total_included"],
                    "price_subtotal": taxes["total_excluded"],
                }
            )
