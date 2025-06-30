# -*- coding: utf-8 -*-

from odoo import fields, models, _


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    foodic_payment_method_id = fields.Char('Foodic Payment Method Id')
    code = fields.Char('Code')
    name_localized = fields.Char('Name Localized')
    auto_open_drawer = fields.Boolean('Auto Open Drawer')

    def set_payment_methods_to_odoo(self, res):
        i = 0
        account = self.env['account.account'].search([], limit=1)
        for payment in res.get('data'):
            i +=1
            vals = {
                'foodic_payment_method_id': payment.get('id'),
                'name': payment.get('name'),
                'name_localized': payment.get('name_localized'),
                'code': payment.get('code'),
                'receivable_account_id': account.id,
                'auto_open_drawer': payment.get('auto_open_drawer'),
            }
            payment_id = self.search([('foodic_payment_method_id', '=', payment.get('id'))], limit=1)
            if payment_id:
                payment_id.update(vals)
            else:
                payment_id.create(vals)

            if i%100 == 0:
                self.env.cr.commit()
        self.env.cr.commit()
