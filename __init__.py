# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import product, production, purchase, stock


def register():
    Pool.register(
        product.Template,
        product.TemplateSupplyOnProduction,
        product.Product,
        production.Production,
        purchase.Request,
        stock.Move,
        module='production_supply', type_='model')
