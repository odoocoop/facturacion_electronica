# Copyright 2017 Creu Blanca
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models


class PartnerXlsx(models.AbstractModel):
    _name = "report.l10n_cl_fe.partner_xlsx"
    _inherit = "report.l10n_cl_fe.abstract"
    _description = "Partner XLSX Report"

    def generate_xlsx_report(self, workbook, data, partners):
        sheet = workbook.add_worksheet("Report")
        i = 0
        for obj in partners:
            bold = workbook.add_format({"bold": True})
            sheet.write(i, 0, obj.name, bold)
            i += 1
