# -*- coding: utf-8 -*-
from odoo import models
from datetime import datetime

class LibroXlsx(models.AbstractModel):
    _inherit = 'report.account.move.book.xlsx'

    def _get_moves(self, obj):
        move_ids = super(LibroXlsx, self)._get_moves(obj)
        if obj.tipo_operacion == 'BOLETA':
            moves = []
            for rec in obj.move_ids:
                if rec.document_class_id and not rec.sii_document_number:
                    orders = self.env['pos.order'].search(
                            [('account_move', '=', rec.id),
                             ('invoice_id' , '=', False),
                             ('sii_document_number', 'not in', [False, '0']),
                             ('document_class_id.sii_code', 'in', [39, 41]),
                            ]).with_context(lang='es_CL')
                    for m in orders:
                        moves.append(m)
                elif rec.document_class_id:
                    moves.append(rec)
            move_ids = sorted(moves, key=lambda r: r.sii_document_number)
        return move_ids
