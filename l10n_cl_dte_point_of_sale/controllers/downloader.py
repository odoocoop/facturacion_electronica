from odoo import http
from odoo.addons.web.controllers.main import serialize_exception
from odoo.addons.l10n_cl_fe.controllers import downloader


class Binary(downloader.Binary):

    @http.route(["/download/xml/boleta/<model('pos.order'):rec_id>"],
        type='http', auth='user')
    @serialize_exception
    def download_boleta(self, rec_id, **post):
        filename = '%s' % rec_id.sii_xml_request.name
        filecontent = rec_id.sii_xml_request.xml_envio
        return self.document(filename, filecontent)
