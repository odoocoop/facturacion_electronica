# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)


class ProccessMail(models.Model):
    _name = 'mail.message.dte'
    _description = "DTE Recibido"
    _inherit = ['mail.thread']

    name = fields.Char(
        string="Nombre Envío",
        readonly=True,
    )
    mail_id = fields.Many2one(
        'mail.message',
        string="Email",
        readonly=True,
        ondelete='cascade',
    )
    document_ids = fields.One2many(
        'mail.message.dte.document',
        'dte_id',
        string="Documents",
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string="Compañía",
        readonly=True,
    )

    _order = 'create_date DESC'

    def pre_process(self):
        self.process_message(pre=True)

    @api.multi
    def process_message(self, pre=False, option=False):
        created = []
        for r in self:
            for att in r.sudo().mail_id.attachment_ids:
                if not att.name:
                    continue
                name = att.name.upper()
                if att.mimetype in ['text/plain'] and name.find('.XML') > -1:
                    vals = {
                        'xml_file': att.datas,
                        'filename': att.name,
                        'pre_process': pre,
                        'dte_id': r.id,
                        'option': option,
                    }
                    val = self.env['sii.dte.upload_xml.wizard'].create(vals)
                    created.extend(val.confirm(ret=True))
        xml_id = 'l10n_cl_fe.action_dte_process'
        result = self.env.ref('%s' % (xml_id)).read()[0]
        if created:
            domain = eval(result.get('domain', '[]'))
            domain.append(('id', 'in', created))
            result['domain'] = domain
        return result
