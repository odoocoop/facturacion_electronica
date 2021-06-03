# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AccountInvoiceRefund(models.TransientModel):
    """Refunds invoice"""

    _inherit = "account.invoice.refund"

    def _dominio_nc(self):
        inv_obj = self.env['account.invoice']
        context = dict(self._context or {})
        docs = []
        for doc in inv_obj.browse(context.get('active_ids')):
            if doc.document_class_id.sii_code in [110]:
                if doc.type in ['out_invoice', 'in_invoice']:
                    docs.append(112)
                docs.append(111)
            else:
                if doc.type in ['out_invoice', 'in_invoice']:
                    docs += [60, 61]
                docs += [55, 56]
        return [
            ('sii_code', 'in', docs),
            ('dte', '=', True),
        ]

    def _default_nc(self):
        return self.env['sii.document_class'].search(
            self._dominio_nc())[-1].id

    tipo_nota = fields.Many2one(
            'sii.document_class',
            string="Tipo De nota",
            required=True,
            domain=lambda self: self._dominio_nc(),
            default=lambda self: self._default_nc(),
        )
    filter_refund = fields.Selection(
            [
                ('1', 'Anula Documento de Referencia'),
                ('2', 'Corrige texto Documento Referencia'),
                ('3', 'Corrige montos'),
            ],
            default='1',
            string='Refund Method',
            required=True,
            help='Refund base on this type. You can not Modify and Cancel if the invoice is already reconciled',
        )

    @api.onchange('filter_refund')
    def _set_template(self):
        if self.filter_refund == '2':
            self.description = _("Dice:   Debe Decir: ")

    @api.multi
    def compute_refund(self, mode='1'):
        inv_obj = self.env['account.invoice']
        inv_tax_obj = self.env['account.invoice.tax']
        inv_line_obj = self.env['account.invoice.line']
        inv_reference_obj = self.env['account.invoice.referencias']
        context = dict(self._context or {})
        xml_id = False
        for form in self:
            created_inv = []
            date = False
            description = False
            for inv in inv_obj.browse(context.get('active_ids')):
                if inv.state in ['draft', 'proforma2', 'cancel']:
                    raise UserError(_('Cannot refund draft/proforma/cancelled invoice.'))
                if inv.reconciled and inv.amount_total > 0:
                    raise UserError(_('Cannot refund invoice which is already reconciled, invoice should be unreconciled first. You can only refund this invoice.'))

                date = form.date_invoice or False
                description = form.description or inv.name
                type = inv.type
                if mode in ['2']:
                    invoice = inv.read(inv_obj._get_refund_modify_read_fields())
                    invoice = invoice[0]
                    del invoice['id']
                    prod = self.env['product.product'].search(
                            [
                                    ('product_tmpl_id', '=', self.env.ref('l10n_cl_fe.no_product').id),
                            ]
                        )
                    jdc = self.env['account.journal.sii_document_class'].search(
                            [
                                ('sii_document_class_id.sii_code','=', self.tipo_nota.sii_code),
                                ('journal_id', '=', inv.journal_id.id),
                            ],
                            limit=1,
                        )
                    if type == 'out_invoice' and self.tipo_nota.document_type == "credit_note":
                        refund_type = 'out_refund'
                    elif type in ['out_invoice', 'out_refund']:
                        refund_type = 'out_invoice'
                    elif type == 'in_invoice' and self.tipo_nota.document_type == "credit_note":
                        refund_type = 'in_refund'
                    else:
                        refund_type = 'in_invoice'
                    account = inv.invoice_line_ids.get_invoice_line_account(
                        inv.type, prod, inv.fiscal_position_id, inv.company_id)
                    invoice_lines = [
                                    [
                                        0,
                                        0,
                                        {
                                            'product_id': prod.id,
                                            'account_id': account.id,
                                            'name': prod.name,
                                            'quantity': 1,
                                            'price_unit': 0
                                        }
                                    ]
                                ]

                    referencias = []
                    i = 1
                    '''
                    for r in inv.referencias:
                        referencias.append([0,0, {
                                'sequence': i,
                                'origen': r.origen,
                                'sii_referencia_TpoDocRef': r.sii_referencia_TpoDocRef.id,
                                'sii_referencia_CodRef': r.sii_referencia_CodRef,
                                'motivo': r.motivo,
                                'fecha_documento': r.fecha_documento,
                            }]
                        )
                        i += 1
                    '''
                    referencias.append([0,0, {
                            'sequence': i,
                            'origen': inv.sii_document_number,
                            'sii_referencia_TpoDocRef': inv.document_class_id.id,
                            'sii_referencia_CodRef': mode,
                            'motivo': description,
                            'fecha_documento': inv.date_invoice
                        }])
                    global_descuentos_recargo = []
                    for gdr in  inv.global_descuentos_recargos:
                        n_gdr = gdr.copy()
                        if n_gdr.get('invoice_id'):
                            del n_gdr['invoice_id']
                        global_descuentos_recargo.append([0,0, n_gdr])
                    invoice.update({
                        'date_invoice': date,
                        'state': 'draft',
                        'number': False,
                        'date': date,
                        'name': description,
                        'origin': inv.number,
                        'fiscal_position_id': inv.fiscal_position_id.id,
                        'type': refund_type,
                        'journal_document_class_id': jdc.id,
                        'document_class_id': jdc.sii_document_class_id.id,
                        'referencias': referencias,
                        'invoice_line_ids': invoice_lines,
                        'tax_line_ids': False,
                        'refund_invoice_id': inv.id,
                        'global_descuentos_recargo': global_descuentos_recargo,
                    })

                    for field in inv_obj._get_refund_common_fields():
                        if inv_obj._fields[field].type == 'many2one':
                            invoice[field] = invoice[field] and invoice[field][0]
                        else:
                            invoice[field] = invoice[field] or False
                    refund = inv_obj.create(invoice)
                    if refund.payment_term_id.id:
                        refund._onchange_payment_term_date_invoice()
                if mode in ['1', '3']:
                    refund = inv.refund(form.date_invoice, date, description,
                                        inv.journal_id.id,
                                        tipo_nota=self.tipo_nota.sii_code,
                                        mode=mode)
                created_inv.append(refund.id)
                xml_id = refund.type == 'out_refund' and 'action_invoice_out_refund' or \
                         refund.type == 'out_invoice' and 'action_invoice_tree1' or \
                         refund.type == 'in_refund' and 'action_invoice_in_refund' or \
                         refund.type == 'in_invoice' and 'action_invoice_tree2'
                # Put the reason in the chatter
                subject = self.tipo_nota.name
                body = description
                refund.message_post(body=body, subject=subject)
        if xml_id:
            result = self.env.ref('account.%s' % (xml_id)).read()[0]
            invoice_domain = safe_eval(result['domain'])
            invoice_domain.append(('id', 'in', created_inv))
            result['domain'] = invoice_domain
            return result
        return True
