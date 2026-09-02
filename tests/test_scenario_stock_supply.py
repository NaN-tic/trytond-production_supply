import datetime
import unittest
from decimal import Decimal

from proteus import Model, Wizard
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
        activate_modules(
            ['production_supply', 'stock_supply'], create_company)

        ProductUom = Model.get('product.uom')
        ProductTemplate = Model.get('product.template')
        BOM = Model.get('production.bom')
        BOMInput = Model.get('production.bom.input')
        BOMOutput = Model.get('production.bom.output')
        ProductBom = Model.get('product.product-production.bom')
        Production = Model.get('production')
        PurchaseRequest = Model.get('purchase.request')
        Party = Model.get('party.party')
        ProductSupplier = Model.get('purchase.product_supplier')

        unit, = ProductUom.find([('name', '=', 'Unit')])
        supplier = Party(name='supplier')
        supplier.save()
        output_template = ProductTemplate(
            name='output', default_uom=unit, type='goods', producible=True,
            list_price=Decimal('10'))
        output, = output_template.products
        output_template.save()
        output, = output_template.products

        stock_first_template = ProductTemplate(
            name='stock first', default_uom=unit, type='goods',
            purchasable=True, supply_on_production='stock_first',
            list_price=Decimal('1'))
        stock_first, = stock_first_template.products
        stock_first_template.save()
        stock_first, = stock_first_template.products
        ProductSupplier(
            template=stock_first_template, party=supplier).save()

        purchase_template = ProductTemplate(
            name='only purchases', default_uom=unit, type='goods',
            purchasable=True, supply_on_production='always',
            list_price=Decimal('1'))
        purchase, = purchase_template.products
        purchase_template.save()
        purchase, = purchase_template.products
        ProductSupplier(template=purchase_template, party=supplier).save()

        stock_only_template = ProductTemplate(
            name='stock only', default_uom=unit, type='goods',
            purchasable=True, supply_on_production=None,
            list_price=Decimal('1'))
        stock_only, = stock_only_template.products
        stock_only_template.save()
        stock_only, = stock_only_template.products
        ProductSupplier(template=stock_only_template, party=supplier).save()

        bom = BOM(name='output')
        bom.inputs.append(BOMInput(product=stock_first, quantity=1))
        bom.inputs.append(BOMInput(product=purchase, quantity=1))
        bom.inputs.append(BOMInput(product=stock_only, quantity=1))
        bom.outputs.append(BOMOutput(product=output, quantity=1))
        bom.save()
        output.boms.append(ProductBom(bom=bom))
        output.save()

        production = Production(
            planned_date=datetime.date.today(), product=output,
            bom=bom, quantity=1)
        production.save()
        production.click('wait')

        Wizard('stock.supply').execute('create_')
        requests = PurchaseRequest.find([
                ('origin', 'like', 'stock.order_point,%'),
                ])
        self.assertEqual([request.product for request in requests],
            [stock_only])
