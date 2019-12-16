from openerp import http
from openerp.addons.web.controllers.main import serialize_exception
from odoo.addons.l10n_cl_fe.controllers import downloader

class Binary(downloader.Binary):

    @http.route(["/download/xml/cesion/<model('account.invoice'):rec_id>"], type='http', auth='user')
    @serialize_exception
    def download_cesion(self, rec_id, **post):
        filename = ('CES_%s_%s.xml' % (rec_id.sii_document_class_id.sii_code, rec_id.sii_document_number)).replace(' ','_')
        filecontent = rec_id.sii_cesion_request
        return self.document(filename, filecontent)
