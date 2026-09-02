# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class Request(metaclass=PoolMeta):
    __name__ = 'purchase.request'

    production_inputs = fields.One2Many(
        'stock.move', 'purchase_request', "Production Inputs", readonly=True)

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() | {'production'}


class RequestStockSupply(metaclass=PoolMeta):
    __name__ = 'purchase.request'

    @classmethod
    def get_shortage(cls, location_id, product_ids, min_date, max_date,
            min_date_qties, order_points):
        pool = Pool()
        Date = pool.get('ir.date')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        User = pool.get('res.user')

        with Transaction().set_context(
                forecast=True,
                stock_date_start=min_date,
                stock_date_end=max_date):
            pbl = Product.products_by_location(
                [location_id], with_childs=True,
                grouping=('date', 'product'),
                grouping_filter=(None, product_ids))
        pbl_dates = defaultdict(dict)
        for key, quantity in pbl.items():
            date, product_id = key[1:]
            pbl_dates[date][product_id] = quantity

        today = Date.today()
        company = User(Transaction().user).company
        with Transaction().set_context(company=company.id):
            moves = Move.search([
                    ('from_location', 'child_of', [location_id], 'parent'),
                    ('to_location', 'not child_of', [location_id], 'parent'),
                    ('product', 'in', product_ids),
                    ('production_input', '!=', None),
                    ('production_input.state', 'not in',
                        ['cancelled', 'done']),
                    ('state', 'in', ['draft', 'assigned']),
                    ])
            for move in moves:
                if move.product.supply_on_production not in {
                        'always', 'stock_first'}:
                    continue
                date = move.effective_date or (
                    today if move.state == 'assigned' else move.planned_date)
                if not date or date < today or date > max_date:
                    continue
                if date <= min_date:
                    min_date_qties[move.product.id] += move.internal_quantity
                else:
                    pbl_dates[date][move.product.id] = (
                        pbl_dates[date].get(move.product.id, 0)
                        + move.internal_quantity)

        min_quantities = defaultdict(int)
        for product_id in product_ids:
            order_point = order_points.get((location_id, product_id))
            if order_point:
                min_quantities[product_id] = order_point.min_quantity

        result_dates = {}
        result_quantities = {}
        current_date = min_date
        current_quantities = min_date_qties.copy()
        products_to_check = product_ids.copy()
        while (current_date < max_date) or (current_date == min_date):
            for product_id in products_to_check:
                current_quantity = current_quantities[product_id]
                min_quantity = min_quantities[product_id]
                result_quantity = result_quantities.get(product_id)
                result_date = result_dates.get(product_id)
                if min_quantity is not None and current_quantity < min_quantity:
                    if not result_date:
                        result_dates[product_id] = current_date
                    if (not result_quantity
                            or current_quantity < result_quantity):
                        result_quantities[product_id] = current_quantity

            if current_date == datetime.date.max:
                break
            current_date += datetime.timedelta(1)

            products_to_check.clear()
            for product_id, quantity in pbl_dates[current_date].items():
                current_quantities[product_id] += quantity
                products_to_check.append(product_id)

        return {
            product_id: (
                result_dates.get(product_id),
                result_quantities.get(product_id))
            for product_id in product_ids}
