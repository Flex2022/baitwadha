# -*- coding: utf-8 -*-
from odoo import fields, models, _


class PosCategory(models.Model):
    _inherit = 'pos.category'

    foodic_category_id = fields.Char('Foodic Category Id')
    name_localized = fields.Char('Name Localized')
    reference = fields.Char('Reference')

    def set_categories_to_odoo(self, res):
        i = 0
        for category in res.get('data'):
            i += 1
            vals = {
                'foodic_category_id': category.get('id'),
                'name': category.get('name'),
                'name_localized': category.get('name_localized'),
                'reference': category.get('reference'),
            }
            category_id = self.search([('foodic_category_id', '=', category.get('id'))], limit=1)
            if category_id:
                category_id.update(vals)
            else:
                category_id.create(vals)

            if i%100 == 0:
                self.env.cr.commit()
        self.env.cr.commit()