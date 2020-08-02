# -*- coding: utf-8 -*-
from odoo import models
from datetime import datetime

class LibroXlsx(models.AbstractModel):
    _name = 'report.account.move.book.xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def _get_moves(self, obj):
        return obj.move_ids

    def generate_xlsx_report(self, workbook, data, libro):
        for obj in libro:
            report_name = obj.name
            # One sheet by partner
            sheet = workbook.add_worksheet(report_name[:31])
            bold = workbook.add_format({'bold': True})
            sheet.write(0, 0, obj.name, bold)
            sheet.write(0, 1, obj.company_id.name, bold)
            sheet.write(0, 2, obj.periodo_tributario, bold)
            sheet.write(0, 3, obj.tipo_operacion, bold)
            sheet.write(0, 4, obj.tipo_libro, bold)
            sheet.write(0, 5, obj.tipo_operacion, bold)
            sheet.write(2, 0, u"Tipo de Documento", bold)
            sheet.write(2, 1, u"Número", bold)
            sheet.write(2, 2, u"Fecha Emisión", bold)
            sheet.write(2, 3, u"RUT", bold)
            sheet.write(2, 4, u"Entidad", bold)
            sheet.write(2, 5, u"Afecto", bold)
            sheet.write(2, 6, u"Exento", bold)
            sheet.write(2, 7, u"IVA", bold)
            sheet.write(2, 8, u"Total", bold)
            line = 3
            move_ids = self._get_moves(obj)
            for mov in move_ids:
                sheet.write(line, 0, mov.document_class_id.name)
                sheet.write(line, 1, (mov.sii_document_number or mov.ref))
                date = mov.date if hasattr(mov, 'date') else mov.date_order[:-9]
                sheet.write(line, 2, datetime.strptime(date, '%Y-%M-%d').strftime('%d/%M/%Y') )
                if mov.partner_id:
                    sheet.write(line, 3, mov.partner_id.document_number)
                    sheet.write(line, 4, mov.partner_id.name)
                else:
                    sheet.write(line, 3, "")
                    sheet.write(line, 4, "")
                if not hasattr(mov, '_dte'):
                    totales = mov.totales_por_movimiento()
                    sheet.write(line, 5, totales['neto'])
                    sheet.write(line, 6, totales['exento'])
                    sheet.write(line, 7, totales['iva'])
                    sheet.write(line, 8, mov.amount)
                else:
                    e = mov.with_context(tax_detail=True)._dte()
                    totales = e['Encabezado']['Totales']
                    sheet.write(line, 5, totales.get('MntNeto', 0))
                    sheet.write(line, 6, totales.get('MntExe', 0))
                    sheet.write(line, 7, totales.get('IVA',0 ))
                    sheet.write(line, 8, mov.amount_total)
                line += 1
            sheet.write(line, 0, "Total General", bold)
            sheet.write(line, 5, obj.total_afecto, bold)
            sheet.write(line, 6, obj.total_exento, bold)
            sheet.write(line, 7, obj.total_iva, bold)
            c = 8
            if obj.total_otros_imps > 0:
                sheet.write(line, c , obj.total_otros_imps, bold)
                c +=1
            #sheet.write(line, c, obj.total_no_rec, bold)
            sheet.write(line, c, obj.total, bold)
