import datetime
import unittest
from decimal import Decimal

from proteus import Model
from trytond.modules.company.tests.tools import create_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        today = datetime.date.today()
        activate_modules('production_supply', create_company)

        ProductUom = Model.get('product.uom')
        ProductTemplate = Model.get('product.template')
        BOM = Model.get('production.bom')
        BOMInput = Model.get('production.bom.input')
        BOMOutput = Model.get('production.bom.output')
        ProductBom = Model.get('product.product-production.bom')
        Inventory = Model.get('stock.inventory')
        InventoryLine = Model.get('stock.inventory.line')
        Location = Model.get('stock.location')
        Production = Model.get('production')
        PurchaseRequest = Model.get('purchase.request')

        unit, = ProductUom.find([('name', '=', 'Unit')])
        default_template = ProductTemplate()
        self.assertEqual(default_template.supply_on_production, 'always')

        output_template = ProductTemplate(
            name='output', default_uom=unit, type='goods', producible=True,
            list_price=Decimal('10'))
        output, = output_template.products
        output_template.save()
        output, = output_template.products

        stock_template = ProductTemplate(
            name='stock first', default_uom=unit, type='goods',
            purchasable=True, supply_on_production='stock_first',
            list_price=Decimal('1'))
        stock_component, = stock_template.products
        stock_template.save()
        stock_component, = stock_template.products

        purchase_template = ProductTemplate(
            name='only purchases', default_uom=unit, type='goods',
            purchasable=True, supply_on_production='always',
            list_price=Decimal('1'))
        purchase_component, = purchase_template.products
        purchase_template.save()
        purchase_component, = purchase_template.products

        stock_only_template = ProductTemplate(
            name='only stock', default_uom=unit, type='goods',
            purchasable=True, supply_on_production=None,
            list_price=Decimal('1'))
        stock_only_component, = stock_only_template.products
        stock_only_template.save()
        stock_only_component, = stock_only_template.products

        bom = BOM(name='output')
        for component, quantity in [
                (stock_component, 5),
                (purchase_component, 1),
                (stock_only_component, 1),
                ]:
            input_ = BOMInput(product=component, quantity=quantity)
            bom.inputs.append(input_)
        bom_output = BOMOutput(product=output, quantity=1)
        bom.outputs.append(bom_output)
        bom.save()
        output.boms.append(ProductBom(bom=bom))
        output.save()

        storage, = Location.find([('code', '=', 'STO')])
        inventory = Inventory(location=storage)
        inventory_line = InventoryLine(product=stock_component, quantity=2)
        inventory.lines.append(inventory_line)
        inventory.click('confirm')

        production = Production(
            planned_date=today, product=output, bom=bom, quantity=1)
        production.save()
        production.click('wait')

        requests = PurchaseRequest.find([
                ('origin', '=', str(production)),
                ])
        self.assertEqual(len(requests), 1)
        request, = requests
        self.assertEqual(request.product, purchase_component)
        self.assertEqual(request.quantity, 1.0)

        production.click('assign_try')
        requests = PurchaseRequest.find([
                ('origin', '=', str(production)),
                ])
        self.assertEqual(
            sorted(
                (request.product.id, request.quantity) for request in requests),
            sorted([
                (purchase_component.id, 1.0),
                (stock_component.id, 3.0),
                ]))

        inventory = Inventory(location=storage)
        inventory_line = InventoryLine(product=stock_component, quantity=5)
        inventory.lines.append(inventory_line)
        inventory.click('confirm')
        production.click('assign_try')
        requests = PurchaseRequest.find([
                ('origin', '=', str(production)),
                ])
        self.assertEqual(len(requests), 1)
        request, = requests
        self.assertEqual(request.product, purchase_component)
