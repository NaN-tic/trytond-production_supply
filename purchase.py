# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Request(metaclass=PoolMeta):
    __name__ = 'purchase.request'

    production_inputs = fields.One2Many(
        'stock.move', 'purchase_request', "Production Inputs", readonly=True)

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() | {'production'}
