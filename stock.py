# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    purchase_request = fields.Many2One(
        'purchase.request', "Purchase Request",
        ondelete='SET NULL', readonly=True)
    supply_state = fields.Function(fields.Selection([
                ('', ""),
                ('requested', "Requested"),
                ('supplied', "Supplied"),
                ('cancelled', "Cancelled"),
                ], "Supply State"), 'get_supply_state')

    @classmethod
    def copy(cls, moves, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('purchase_request', None)
        return super().copy(moves, default=default)

    def get_supply_state(self, name):
        if self.purchase_request is not None:
            if self.purchase_request.state == 'cancelled':
                return 'cancelled'
            if self.purchase_request.purchase_line is not None:
                purchase = self.purchase_request.purchase_line.purchase
                if purchase.state in {'processing', 'done'}:
                    return 'supplied'
            return 'requested'
        return ''
