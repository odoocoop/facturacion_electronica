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
            r.caf_files = r.caf_files_exentas = ''
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

    '''
    se testeará primero la propuesta de odoo
    def _accumulate_amounts(self, data):
        def _flatten_tax_and_children(taxes, group_done=None):
            children = self.env['account.tax']
            if group_done is None:
                group_done = set()
            for tax in taxes.filtered(lambda t: t.amount_type == 'group'):
                if tax.id not in group_done:
                    group_done.add(tax.id)
                    children |= _flatten_tax_and_children(tax.children_tax_ids, group_done)
            return taxes + children
        # Tricky, via the workflow, we only have one id in the ids variable
        """Create a account move line of order grouped by products or not."""
        IrProperty = self.env['ir.property']
        ResPartner = self.env['res.partner']

        if session and not all(session.id == order.session_id.id for order in self):
            raise UserError(_('Selected orders do not have the same session!'))

        grouped_data = {}
        have_to_group_by = session and session.config_id.group_by or False
        rounding_method = session and session.config_id.company_id.tax_calculation_rounding_method
        document_class_id = False

        def add_anglosaxon_lines(grouped_data):
            Product = self.env['product.product']
            Analytic = self.env['account.analytic.account']
            keys = []
            for product_key in list(grouped_data.keys()):
                if product_key[0] == "product":
                    line = grouped_data[product_key][0]
                    product = Product.browse(line['product_id'])
                    # In the SO part, the entries will be inverted by function compute_invoice_totals
                    price_unit = self._get_pos_anglo_saxon_price_unit(product, line['partner_id'], line['quantity'])
                    account_analytic = Analytic.browse(line.get('analytic_account_id'))
                    res = Product._anglo_saxon_sale_move_lines(
                        line['name'], product, product.uom_id, line['quantity'], price_unit,
                            fiscal_position=order.fiscal_position_id,
                            account_analytic=account_analytic)
                    if res:
                        line1, line2 = res
                        line1 = Product._convert_prepared_anglosaxon_line(line1, line['partner_id'])
                        values = {
                            'name': line1['name'],
                            'account_id': line1['account_id'],
                            'credit': line1['credit'] or 0.0,
                            'debit': line1['debit'] or 0.0,
                            'partner_id': line1['partner_id']
                        }
                        keys.append(self._get_account_move_line_group_data_type_key('counter_part', values))
                        insert_data('counter_part', values)

                        line2 = Product._convert_prepared_anglosaxon_line(line2, line['partner_id'])
                        values = {
                            'name': line2['name'],
                            'account_id': line2['account_id'],
                            'credit': line2['credit'] or 0.0,
                            'debit': line2['debit'] or 0.0,
                            'partner_id': line2['partner_id']
                        }
                        keys.append(self._get_account_move_line_group_data_type_key('counter_part', values))
                        insert_data('counter_part', values)
            if not keys:
                return
            dif = 0
            for group_key, group_data in grouped_data.items():
                if group_key in keys:
                    for value in group_data:
                        if value['credit'] > 0:
                            entera, decimal = math.modf(value['credit'])
                            dif = cur_company.round(value['credit']) - entera
                        elif dif > 0 and value['debit'] > 0:
                            value['debit'] += 1
                            dif = 0

        for order in self.filtered(lambda o: not o.account_move or o.state == 'paid'):
            current_company = order.sale_journal.company_id
            account_def = IrProperty.get(
                'property_account_receivable_id', 'res.partner')
            order_account = order.partner_id.property_account_receivable_id.id or account_def and account_def.id
            partner_id = ResPartner._find_accounting_partner(order.partner_id).id or False
            if move is None:
                # Create an entry for the sale
                journal_id = self.env['ir.config_parameter'].sudo().get_param(
                    'pos.closing.journal_id_%s' % current_company.id, default=order.sale_journal.id)
                move = self._create_account_move(
                    order.session_id.start_at, order.name, int(journal_id), order.company_id.id)
            if order.document_class_id and not move.document_class_id:
                move.document_class_id = order.document_class_id
            def insert_data(data_type, values):
                # if have_to_group_by:
                values.update({
                    'partner_id': partner_id,
                    'move_id': move.id,
                })
                key = self._get_account_move_line_group_data_type_key(data_type, values)
                if not key:
                    return

                grouped_data.setdefault(key, [])

                if have_to_group_by:
                    if not grouped_data[key]:
                        grouped_data[key].append(values)
                    else:
                        current_value = grouped_data[key][0]
                        current_value['quantity'] = current_value.get('quantity', 0.0) + values.get('quantity', 0.0)
                        current_value['credit'] = current_value.get('credit', 0.0) + values.get('credit', 0.0)
                        current_value['debit'] = current_value.get('debit', 0.0) + values.get('debit', 0.0)
                else:
                    grouped_data[key].append(values)

            # because of the weird way the pos order is written, we need to make sure there is at least one line,
            # because just after the 'for' loop there are references to 'line' and 'income_account' variables (that
            # are set inside the for loop)
            # TOFIX: a deep refactoring of this method (and class!) is needed
            # in order to get rid of this stupid hack
            assert order.lines, _('The POS order must have lines when calling this method')
            # Create an move for each order line
            cur = order.pricelist_id.currency_id
            cur_company = order.company_id.currency_id
            amount_cur_company = 0.0
            date_order = order.date_order.date() if order.date_order else fields.Date.today()
            total = 0
            all_tax = {}
            last = False
            for line in order.lines:
                if cur != cur_company:
                    amount_subtotal = cur._convert(line.price_subtotal, cur_company, order.company_id, date_order)
                else:
                    amount_subtotal = line.price_subtotal
                if amount_subtotal != 0:
                    last = line
                # Search for the income account
                if line.product_id.property_account_income_id.id:
                    income_account = line.product_id.property_account_income_id.id
                elif line.product_id.categ_id.property_account_income_categ_id.id:
                    income_account = line.product_id.categ_id.property_account_income_categ_id.id
                else:
                    raise UserError(_('Please define income '
                                      'account for this product: "%s" (id:%d).')
                                    % (line.product_id.name, line.product_id.id))

                name = line.product_id.name
                if line.notice:
                    # add discount reason in move
                    name = name + ' (' + line.notice + ')'

                # Create a move for the line for the order line
                # Just like for invoices, a group of taxes must be present on this base line
                # As well as its children
                base_line_tax_ids = _flatten_tax_and_children(line.tax_ids_after_fiscal_position).filtered(lambda tax: tax.type_tax_use in ['sale', 'none'])
                fpos = line.order_id.fiscal_position_id
                tax_ids_after_fiscal_position = fpos.map_tax(line.tax_ids, line.product_id, order.partner_id) if fpos else line.tax_ids
                taxes = tax_ids_after_fiscal_position.with_context(round=False, date=order.date_order, currency=cur_company.code).compute_all(line.price_unit, order.pricelist_id.currency_id, line.qty, product=line.product_id, partner=order.partner_id, discount=line.discount, uom_id=line.product_id.uom_id)
                data = {
                    'name': name,
                    'quantity': line.qty,
                    'product_id': line.product_id.id,
                    'account_id': income_account,
                    'analytic_account_id': self._prepare_analytic_account(line),
                    'credit': ((amount_subtotal > 0) and amount_subtotal) or 0.0,
                    'debit': ((amount_subtotal < 0) and -amount_subtotal) or 0.0,
                    'tax_ids': [(6, 0, base_line_tax_ids.ids)],
                    'partner_id': partner_id
                }
                total += amount_subtotal
                if cur != cur_company:
                    data['currency_id'] = cur.id
                    data['amount_currency'] = -abs(line.price_subtotal) if data.get('credit') else abs(line.price_subtotal)
                    amount_cur_company += data['credit'] - data['debit']
                insert_data('product', data)

                # Create the tax lines
                line_taxes = line.tax_ids_after_fiscal_position.filtered(lambda t: t.company_id.id == current_company.id)
                if not line_taxes:
                    raise UserError("Hay un producto sin impuesto, seleccionar exento si no afecta al IVA")
                    continue
                #el Cálculo se hace sumando todos los valores redondeados, luego se cimprueba si hay descuadre de $1 y se agrega como línea de ajuste
                taxes = line.tax_ids_after_fiscal_position.filtered(lambda t: t.company_id.id == current_company.id)
                for tax in taxes.with_context(date=order.date_order, currency=cur_company.code).compute_all(line.price_unit, cur, line.qty, discount=line.discount, uom_id=line.product_id.uom_id)['taxes']:
                    if cur != cur_company:
                        round_tax = False if rounding_method == 'round_globally' else True
                        amount_tax = cur._convert(tax['amount'], cur_company, order.company_id, date_order, round=round_tax)
                        # amount_tax = cur.with_context(date=date_order).compute(tax['amount'], cur_company, round=round_tax)
                    else:
                        amount_tax = tax['amount']
                    data = {
                        'name': _('Tax') + ' ' + tax['name'],
                        'product_id': line.product_id.id,
                        'quantity': line.qty,
                        'account_id': tax['account_id'] or income_account,
                        'credit': ((amount_tax > 0) and amount_tax) or 0.0,
                        'debit': ((amount_tax < 0) and -amount_tax) or 0.0,
                        'tax_line_id': tax['id'],
                        'partner_id': partner_id,
                        'order_id': order.id
                    }
                    all_tax.setdefault(tax['name'], 0)
                    all_tax[tax['name']] += amount_tax
                    if cur != cur_company:
                        data['currency_id'] = cur.id
                        data['amount_currency'] = -abs(tax['amount']) if data.get('credit') else abs(tax['amount'])
                        amount_cur_company += data['credit'] - data['debit']
                    insert_data('tax', data)
            # round tax lines  per order
            total_tax = 0
            for t, v in all_tax.items():
                total_tax += cur_company.round(v)
            dif = order.amount_total - (cur.round(total) + total_tax)
            if rounding_method == 'round_globally':
                for group_key, group_value in grouped_data.items():
                    if dif != 0 and group_key[0] == 'product':
                        for l in group_value:
                            if last.product_id.id == l['product_id']:
                                if l['credit'] > 0:
                                    l['credit'] += dif
                                else:
                                    l['debit'] -= dif
                                dif = 0
                    if group_key[0] == 'tax':
                        for l in group_value:
                            l['credit'] = cur_company.round(l['credit'])
                            l['debit'] = cur_company.round(l['debit'])
                            if l.get('currency_id'):
                                l['amount_currency'] = cur.round(l.get('amount_currency', 0.0))
            # counterpart
            if cur != cur_company:
                # 'amount_cur_company' contains the sum of the AML converted in the company
                # currency. This makes the logic consistent with 'compute_invoice_totals' from
                # 'account.invoice'. It ensures that the counterpart line is the same amount than
                # the sum of the product and taxes lines.
                amount_total = amount_cur_company
            else:
                amount_total = order.amount_total
            data = {
                'name': _("Trade Receivables"),  # order.name,
                'account_id': order_account,
                'credit': ((amount_total < 0) and -amount_total) or 0.0,
                'debit': ((amount_total > 0) and amount_total) or 0.0,
                'partner_id': partner_id
            }
            if cur != cur_company:
                data['currency_id'] = cur.id
                data['amount_currency'] = -abs(order.amount_total) if data.get('credit') else abs(order.amount_total)
            insert_data('counter_part', data)

            order.write({'state': 'done', 'account_move': move.id})

        if self and order.company_id.anglo_saxon_accounting:
            add_anglosaxon_lines(grouped_data)
        return {
            'grouped_data': grouped_data,
            'move': move,
        }
    '''
