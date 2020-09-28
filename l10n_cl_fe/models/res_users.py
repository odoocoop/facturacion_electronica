import logging

from odoo import SUPERUSER_ID, models

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    def get_digital_signature(self, company_id):
        user_id = self.id
        if user_id == SUPERUSER_ID:
            user_id = self.env.ref("base.user_admin").id
        signature = self.env["sii.firma"].search(
            [
                ("user_ids", "child_of", [user_id]),
                ("company_ids", "child_of", [company_id.id]),
                ("state", "=", "valid"),
            ],
            limit=1,
            order="priority ASC",
        )
        if signature:
            signature.check_signature()
            if signature.active:
                return signature
        return self.env["sii.firma"]
