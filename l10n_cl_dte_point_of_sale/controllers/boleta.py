# -*- coding: utf-8 -*-

from odoo.http import request
from odoo.addons.web.controllers.main import serialize_exception
from odoo.tools.misc import formatLang
from odoo.addons.l10n_cl_fe.controllers.boleta import Boleta


class POSBoleta(Boleta):

    def _get_domain_pos_order(self, folio, post_values):
        domain = [('sii_document_number', '=', int(folio))]
        #if post.get('date_invoice', ''):
        #    domain.append(('date_order','=',post.get('date_invoice', '')))
        #if post.get('amount_total', ''):
        #    domain.append(('amount_total','=',float(post.get('amount_total', ''))))
        if post_values.get('sii_codigo', ''):
            domain.append(('document_class_id.sii_code', '=', int(post_values.get('sii_codigo', ''))))
        else:
            domain.append(('document_class_id.sii_code', 'in', [39, 41] ))
        return domain

    def get_orders(self, folio, post):
        orders = super(POSBoleta, self).get_orders(folio, post)
        if not orders:
            Model = request.env['pos.order'].sudo()
            domain = self._get_domain_pos_order(folio, post)
            orders = Model.search(domain, limit=1)
        return orders

    def _get_report(self, document):
        if document._name == 'pos.order':
            return request.env.ref('l10n_cl_dte_point_of_sale.action_report_pos_boleta_ticket').sudo().render_qweb_pdf([document.id])[0]
        return super(POSBoleta, self)._get_report(document)
