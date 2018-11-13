from odoo import models, http
from odoo.http import request
from odoo.addons.web.controllers.main import serialize_exception, content_disposition

class BinaryGuia(http.Controller):

    def document(self, filename, filecontent):
        if not filecontent:
            return request.not_found()
        headers = [
            ('Content-Type', 'application/xml'),
            ('Content-Disposition', content_disposition(filename)),
            ('charset', 'utf-8'),
        ]
        return request.make_response(
                filecontent, headers=headers, cookies=None)

    @http.route(["/download/xml/guia/<model('stock.picking'):document_id>"], type='http', auth='user')
    @serialize_exception
    def download_guia(self, document_id, **post):
        filename = ('Guia_%s.xml' % document_id.sii_document_number).replace(' ','_')
        filecontent = document_id.sii_xml_request
        return self.document(filename, filecontent)

    @http.route(["/download/xml/libro_guia/<model('stock.picking.book'):document_id>"], type='http', auth='user')
    @serialize_exception
    def download_libro_guia(self, document_id, **post):
        filename = ('Lbro_Guia_%s.xml' % document_id.name).replace(' ','_')
        filecontent = document_id.sii_xml_request
        return self.document(filename, filecontent)
