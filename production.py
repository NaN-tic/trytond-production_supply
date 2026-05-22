# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow
from trytond.pool import Pool, PoolMeta

from .exceptions import SupplyWarning


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() | {'production'}

    @classmethod
    def wait(cls, productions):
        super().wait(productions)
        cls._process_supply(productions)

    @classmethod
    def _check_supply_documents(cls, productions, transition):
        pool = Pool()
        PurchaseRequest = pool.get('purchase.request')
        Production = pool.get('production')
        Warning = pool.get('res.user.warning')

        origins = [str(p) for p in productions]
        purchase_requests = PurchaseRequest.search([
                ('origin', 'in', origins),
                ])
        child_productions = Production.search([
                ('origin', 'in', origins),
                ])
        purchase_requests_in_progress = [
            r for r in purchase_requests
            if r.state not in {'draft', 'cancelled'}]
        child_productions_in_progress = [
            p for p in child_productions
            if p.state not in {'draft', 'cancelled'}]

        if purchase_requests_in_progress or child_productions_in_progress:
            key = Warning.format(
                'production_supply_documents_%s' % transition, productions)
            if Warning.check(key):
                raise SupplyWarning(key, gettext(
                        'production_supply.'
                        'msg_supply_documents_in_progress'))
        return purchase_requests, child_productions

    @classmethod
    def _clean_supply_documents(cls, purchase_requests, child_productions):
        pool = Pool()
        PurchaseRequest = pool.get('purchase.request')
        Production = pool.get('production')

        purchase_requests_to_delete = [
            r for r in purchase_requests
            if r.state == 'draft']
        child_productions_to_delete = [
            p for p in child_productions
            if p.state == 'draft']
        if purchase_requests_to_delete:
            PurchaseRequest.delete(purchase_requests_to_delete)
        if child_productions_to_delete:
            Production.delete(child_productions_to_delete)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, productions):
        purchase_requests, child_productions = cls._check_supply_documents(
            productions, 'cancel')
        cls._clean_supply_documents(purchase_requests, child_productions)
        super().cancel(productions)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, productions):
        purchase_requests, child_productions = cls._check_supply_documents(
            productions, 'draft')
        cls._clean_supply_documents(purchase_requests, child_productions)
        super().draft(productions)

    @classmethod
    def _process_supply(cls, productions):
        pool = Pool()
        Move = pool.get('stock.move')
        PurchaseRequest = pool.get('purchase.request')
        Production = pool.get('production')

        requests, productions_to_create, moves = [], [], []
        for production in productions:
            reqs, mvs = production.get_purchase_requests()
            childs = production.get_production_requests()
            requests.extend(reqs)
            productions_to_create.extend(childs)
            moves.extend(mvs)
        if requests:
            PurchaseRequest.save(requests)
        if productions_to_create:
            Production.save(productions_to_create)
            Production.set_moves(productions_to_create)
        if moves:
            Move.save(moves)

    def must_supply_on_production(self, product):
        return True

    def _get_purchase_request_product_supplier_pattern(self):
        return {
            'company': self.company.id,
            }

    def get_purchase_request_supplier(self, product, supply_date):
        pool = Pool()
        Request = pool.get('purchase.request')

        pattern = self._get_purchase_request_product_supplier_pattern()
        supplier, purchase_date = Request.find_best_supplier(
            product, supply_date, **pattern)
        if supplier:
            return supplier, purchase_date, supply_date

        product_supplier = Request.find_best_product_supplier(
            product, None, **pattern)
        if product_supplier:
            supplier = product_supplier.party
            purchase_date = product_supplier.compute_purchase_date(None)
            supplier_supply_date = product_supplier.compute_supply_date(
                purchase_date)
            if supplier_supply_date != datetime.date.max:
                supply_date = supplier_supply_date
        return supplier, purchase_date, supply_date

    def get_purchase_requests(self):
        requests = []
        moves = []
        request_per_product = {}
        moves_per_product = defaultdict(list)
        for move in self.inputs:
            if (move.purchase_request
                    or not move.product
                    or move.quantity <= 0):
                continue
            if (move.product.producible
                    or not self.must_supply_on_production(move.product)
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

    def get_production_requests(self):
        productions = []
        existing = {
            production.product: production
            for production in self.__class__.search([
                    ('origin', '=', str(self)),
                    ('state', '!=', 'cancelled'),
                    ])
            if production.product
            }
        moves_per_product = defaultdict(list)
        for move in self.inputs:
            if (not move.product
                    or move.quantity <= 0):
                continue
            if (not self.must_supply_on_production(move.product)
                    or not move.product.producible
                    or move.product in existing):
                continue
            moves_per_product[move.product].append(move)
        for product, product_moves in moves_per_product.items():
            production = self.get_production_request(product, product_moves)
            if production:
                productions.append(production)
        return productions

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
        supplier, purchase_date, supply_date = (
            self.get_purchase_request_supplier(product, supply_date))
        return Request(
            product=product,
            party=supplier and supplier or None,
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

    def get_production_request(self, product, moves):
        pool = Pool()
        Uom = pool.get('product.uom')

        product_bom = product.get_bom()
        bom = product_bom.bom if product_bom else None
        unit = product.default_uom
        if bom:
            for output in bom.outputs:
                if output.product == product:
                    unit = output.unit
                    break
        quantity = 0
        planned_date = None
        for move in moves:
            quantity += Uom.compute_qty(move.unit, move.quantity, unit)
            move_planned_date = move.planned_date or self.planned_start_date
            if planned_date is None or move_planned_date < planned_date:
                planned_date = move_planned_date
        production = self.__class__(
            planned_date=planned_date,
            company=self.company,
            warehouse=self.warehouse,
            location=self.location,
            product=product,
            bom=bom,
            unit=unit,
            quantity=quantity,
            state='request',
            origin=self,
            )
        production.set_planned_start_date()
        return production
