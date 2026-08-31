# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyMultiValueMixin, CompanyValueMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Template(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'product.template'

    supply_on_production = fields.MultiValue(fields.Selection([
            (None, "Only Stock"),
            ('stock_first', "Stock First"),
            ('always', "Only Purchases"),
            ], "Supply On Production",
        states={
            'invisible': ~Eval('purchasable'),
            }))
    supply_on_productions = fields.One2Many(
        'product.template.supply_on_production', 'template',
        "Supply On Productions")

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'supply_on_production':
            return pool.get('product.template.supply_on_production')
        return super().multivalue_model(field)

    @staticmethod
    def default_supply_on_production(**pattern):
        return 'always'


class TemplateSupplyOnProduction(ModelSQL, CompanyValueMixin):
    "Template Supply On Production"
    __name__ = 'product.template.supply_on_production'

    template = fields.Many2One('product.template', 'Product Template')
    supply_on_production = fields.Selection([
            (None, "Only Stock"),
            ('stock_first', "Stock First"),
            ('always', "Only Purchases"),
            ], "Supply On Production")


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
