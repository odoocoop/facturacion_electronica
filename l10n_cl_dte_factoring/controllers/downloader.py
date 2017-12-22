from openerp import http
from openerp.addons.web.controllers.main import serialize_exception
from odoo.addons.l10n_cl_fe.controllers.downloader import document

class Binary(http.Controller):

    @http.route(["/download/xml/cesion/<model('account.invoice'):rec_id>"], type='http', auth='user')
    @serialize_exception
    def download_book(self, rec_id, **post):
        filename = ('CES_%s_%s.xml' % (rec_id.sii_document_class.sii_code, rec_id.sii_document_number)).replace(' ','_')
        filecontent = rec_id.sii_xml_request
        return document(filename, filecontent)
