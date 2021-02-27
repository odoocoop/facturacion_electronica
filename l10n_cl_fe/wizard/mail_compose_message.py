import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class MailComposer(models.TransientModel):
    _inherit = "mail.compose.message"

    
    def onchange_template_id(self, template_id, composition_mode, model, res_id):
        result = super(MailComposer, self).onchange_template_id(template_id, composition_mode, model, res_id)
        atts = self._context.get("default_attachment_ids", [])
        for att in atts:
            if not result["value"].get("attachment_ids"):
                result["value"]["attachment_ids"] = [(6, 0, [])]
            if att not in result["value"]["attachment_ids"][0][2]:
                result["value"]["attachment_ids"][0][2].append(att)
        return result
