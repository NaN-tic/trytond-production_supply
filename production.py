# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pool import Pool, PoolMeta


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    @classmethod
    def wait(cls, productions):
        super().wait(productions)
        cls._process_supply(productions)

    @classmethod
    def _process_supply(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        PurchaseRequest = pool.get('purchase.request')

        requests, moves = [], []
        for production in productions:
            reqs, mvs = production.get_purchase_requests()
            requests.extend(reqs)
            moves.extend(mvs)
        if requests:
            PurchaseRequest.save(requests)
        if moves:
            Move.save(moves)

    def get_purchase_requests(self):
        requests = []
        moves = []
        request_per_product = {}
        moves_per_product = defaultdict(list)
        for move in self.inputs:
            if (move.purchase_request
                    or not move.product
                    or move.quantity <= 0
                    or not move.product.purchasable):
                continue
            moves_per_product[move.product].append(move)
        for product, product_moves in moves_per_product.items():
            request = self.get_purchase_request(product, product_moves)
            if not request:
                continue
            requests.append(request)
            request_per_product[product] = request
        for move in self.inputs:
            request = request_per_product.get(move.product)
            if not request:
                continue
            move.purchase_request = request
            moves.append(move)
        return requests, moves

    def get_purchase_request(self, product, moves):
        pool = Pool()
        Uom = pool.get('product.uom')
        Request = pool.get('purchase.request')

        unit = product.purchase_uom or product.default_uom
        quantity = 0
        supply_date = None
        for move in moves:
            quantity += Uom.compute_qty(move.unit, move.quantity, unit)
            move_supply_date = move.planned_date or self.planned_start_date
            if supply_date is None or move_supply_date < supply_date:
                supply_date = move_supply_date
        supplier, purchase_date = Request.find_best_supplier(
            product, supply_date, company=self.company.id)
        return Request(
            product=product,
            party=supplier,
            quantity=quantity,
            unit=unit,
            computed_quantity=quantity,
            computed_unit=unit,
            purchase_date=purchase_date,
            supply_date=supply_date,
            company=self.company,
            warehouse=self.warehouse,
            origin=self,
            )
