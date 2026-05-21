==========================
Production Supply Scenario
==========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('production_supply', create_company)

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> BOM = Model.get('production.bom')
    >>> BOMInput = Model.get('production.bom.input')
    >>> BOMOutput = Model.get('production.bom.output')
    >>> ProductBom = Model.get('product.product-production.bom')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.list_price = Decimal(30)
    >>> product, = template.products
    >>> product.cost_price = Decimal(20)
    >>> template.save()
    >>> product, = template.products

Create components::

    >>> template1 = ProductTemplate()
    >>> template1.name = 'component 1'
    >>> template1.default_uom = unit
    >>> template1.type = 'goods'
    >>> template1.purchasable = True
    >>> template1.list_price = Decimal(5)
    >>> component1, = template1.products
    >>> component1.cost_price = Decimal(1)
    >>> template1.save()
    >>> component1, = template1.products

Define a product supplier for the purchasable component::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> ProductSupplier = Model.get('purchase.product_supplier')
    >>> product_supplier = ProductSupplier(template=template1)
    >>> product_supplier.party = supplier
    >>> product_supplier.lead_time = dt.timedelta(days=1)
    >>> product_supplier.save()

    >>> template2 = ProductTemplate()
    >>> template2.name = 'component 2'
    >>> template2.default_uom = unit
    >>> template2.type = 'goods'
    >>> template2.producible = True
    >>> template2.list_price = Decimal(7)
    >>> component2, = template2.products
    >>> component2.cost_price = Decimal(5)
    >>> template2.save()
    >>> component2, = template2.products

Create BOM for producible component::

    >>> component2_bom = BOM(name='component 2')
    >>> component2_output = BOMOutput()
    >>> component2_bom.outputs.append(component2_output)
    >>> component2_output.product = component2
    >>> component2_output.quantity = 1
    >>> component2_bom.save()

    >>> component2.boms.append(ProductBom(bom=component2_bom))
    >>> component2.save()

Create Bill of Material::
    >>> bom = BOM(name='product')
    >>> input1 = BOMInput()
    >>> bom.inputs.append(input1)
    >>> input1.product = component1
    >>> input1.quantity = 5
    >>> input2 = BOMInput()
    >>> bom.inputs.append(input2)
    >>> input2.product = component1
    >>> input2.quantity = 2
    >>> input3 = BOMInput()
    >>> bom.inputs.append(input3)
    >>> input3.product = component2
    >>> input3.quantity = 3
    >>> output = BOMOutput()
    >>> bom.outputs.append(output)
    >>> output.product = product
    >>> output.quantity = 1
    >>> bom.save()

    >>> product.boms.append(ProductBom(bom=bom))
    >>> product.save()

Make a production::

    >>> Production = Model.get('production')
    >>> production = Production()
    >>> production.planned_date = today
    >>> production.planned_start_date = yesterday
    >>> production.product = product
    >>> production.bom = bom
    >>> production.quantity = 2
    >>> production.save()
    >>> production.click('wait')
    >>> production.state
    'waiting'

Purchase requests are created per product and linked to all input moves::

    >>> PurchaseRequest = Model.get('purchase.request')
    >>> requests = PurchaseRequest.find([('origin', '=', str(production))])
    >>> len(requests)
    1
    >>> sorted((r.product.name, r.quantity) for r in requests)
    [('component 1', 14.0)]
    >>> request, = requests
    >>> request.party == supplier
    True
    >>> component1_moves = [m for m in production.inputs if m.product == component1]
    >>> len({m.purchase_request.id for m in component1_moves})
    1
    >>> for move in production.inputs:
    ...     if move.product == component1:
    ...         assertEqual(move.purchase_request.origin.id, production.id)
    ...         assertEqual(str(move.purchase_request.origin), str(production))
    ...     else:
    ...         assertEqual(move.purchase_request, None)

Productions are created for producible products::

    >>> child_productions = Production.find([('origin', '=', str(production))])
    >>> len(child_productions)
    1
    >>> child_production, = child_productions
    >>> child_production.product == component2
    True
    >>> child_production.quantity
    6.0
