# -*- coding: utf-8 -*-
from odoo import fields, models, _
from datetime import datetime, date, timedelta
from dateutil import parser
from odoo.tools import float_is_zero
import logging

_logger = logging.getLogger(__name__)


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    foodic_payment_id = fields.Char()


class PosMakePayment(models.TransientModel):
    _inherit = 'pos.make.payment'

    def check(self):
        """Check the order:
        if the order is not paid: continue payment,
        if the order is paid print ticket.
        """
        self.ensure_one()

        order = self.env['pos.order'].browse(self.env.context.get('active_id', False))
        currency = order.currency_id

        init_data = self.read()[0]
        if not float_is_zero(init_data['amount'], precision_rounding=currency.rounding):
            order.add_payment({
                'pos_order_id': order.id,
                'amount': order._get_rounded_amount(init_data['amount']),
                'name': init_data['payment_name'],
                'payment_method_id': init_data['payment_method_id'][0],
                'foodic_payment_id': self.env.context.get('foodic_payment_id', False),
            })

        if order._is_pos_order_paid():
            order.action_pos_order_paid()
            order._create_order_picking()
            return {'type': 'ir.actions.act_window_close'}


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    is_void = fields.Boolean(default=False)
    is_returned = fields.Boolean(default=False)
    foodic_discount = fields.Float('Discount')
    is_moved = fields.Boolean('Moved', default=False)
    is_charge = fields.Boolean(default=False)
    is_modifier = fields.Boolean('Modifier', default=False)
    is_combo = fields.Boolean('Combo Product', default=False)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    foodic_order_id = fields.Char('Foodic product Id', copy=False)
    foodic_order_ref = fields.Char('Foodic Order Ref', readonly=True, copy=False)
    cashier = fields.Char(readonly=True)
    count = fields.Integer(default=0)
    discounted_order = fields.Boolean(default=False)
    charged_order = fields.Boolean(default=False)

    def set_orders_to_odoo(self, res, timestamp=False):
        PosConfig = self.env['pos.config']
        ResPartner = self.env['res.partner']
        PosOrder = self.env['pos.order']
        PosSession = self.env['pos.session']
        ProductProduct = self.env['product.product']
        PosOrderLine = self.env['pos.order.line']
        PosPaymentmethod = self.env['pos.payment.method']
        AccountTax = self.env['account.tax']
        if res:
            count = 1
            for order in res.get('data'):
                # if not order.get('combos'):
                #     continue
                
                # if order.get('reference') in [317230, 317290, 315846]:
                #     import pdb;pdb.set_trace()
                # else:
                #     print(">>>>>>>>>>>>", order.get('reference'))
                #     continue

                is_refund = False
                if order.get('status') == 5:
                    is_refund = True

                date_order = order.get('business_date')
                if timestamp and datetime.strptime(date_order, '%Y-%m-%d') > datetime.strptime(timestamp, '%Y-%m-%d') - timedelta(days=1):
                    continue

                customer = ''
                branch = PosConfig.search([('foodic_branch_id', '=', order.get('branch').get('id'))], limit=1)
                if not branch:
                    PosConfig.set_branches_to_odoo({'data': [order.get('branch')]})
                    branch = PosConfig.search([('foodic_branch_id', '=', order.get('branch').get('id'))], limit=1)
                if order.get('customer'):
                    customer = ResPartner.search([('foodic_partner_id', '=', order.get('customer').get('id'))]).id
                    if not customer:
                        ResPartner.set_partner_to_odoo({'data': [order.get('customer')]})
                        customer = ResPartner.search([('foodic_partner_id', '=', order.get('customer').get('id'))]).id
                else:
                    customer = False

                pos_order = PosOrder.search([('foodic_order_id', '=', order.get('id'))])
                session = PosSession.search([('config_id', '=', branch.id), ('state', 'not in', ['closed', 'closing_control'])])
                if not session:
                    session = session.create({'config_id': branch.id, 'user_id': self.env.uid})

                pos_order_line = []

                amount_total = 0
                amount_paid = 0
                total_tax = 0
                contain_void_product = True
                line_discount = 0
                skip_order = False
                if not pos_order:
                    tax_exclusive = False
                    for foodic_prdt in order.get('products'):
                        if foodic_prdt.get('status') == 5:
                            continue

                        moved_product = True if foodic_prdt.get('status') == 4 else False
                        declined_product = True if foodic_prdt.get('status') == 7 else False

                        if foodic_prdt.get('product'):
                            if foodic_prdt.get('options'):
                                for options in foodic_prdt.get('options'):
                                    if options.get('modifier_option'):
                                        # prdt = FoodicProduct.search([('foodic_product_id', '=', options.get('modifier_option').get('id'))], limit=1)
                                        prdt = ProductProduct.search([('foodic_product_id', '=', options.get('modifier_option').get('id')), ('active', 'in', [True, False])], limit=1)
                                        if not prdt:
                                            # FoodicProduct.with_context({'is_modifier': True}).set_products_to_odoo({'data': [options.get('modifier_option')]})
                                            # prdt = FoodicProduct.search([('foodic_product_id', '=', options.get('modifier_option').get('id'))], limit=1)
                                            ProductProduct.with_context({'is_modifier': True}).set_products_to_odoo({'data': [options.get('modifier_option')]})
                                            prdt = ProductProduct.search([('foodic_product_id', '=', options.get('modifier_option').get('id')), ('active', 'in', [True, False])], limit=1)
                                        pos_order_line.append((0, 0, {'name': prdt.name,
                                            # 'name': prdt.name,
                                            # 'full_product_name': prdt.name,
                                            'full_product_name': prdt.name,
                                            # 'product_id': prdt.id,
                                            'product_id': prdt.id,
                                            'qty': -options.get('quantity') if is_refund else options.get('quantity'),
                                            # 'price_subtotal': options.get('total_exclusice_total_price'),
                                            'price_subtotal': 0,
                                            'price_subtotal_incl': 0,
                                            'price_unit': 0 if moved_product or declined_product else options.get('unit_price'),
                                            'is_modifier': True,
                                            'is_moved': moved_product
                                            }))
                            prdt = ProductProduct.search([('foodic_product_id', '=', foodic_prdt.get('product').get('id')), ('active', 'in', [True, False])],limit=1)
                            # prdt = FoodicProduct.search([('foodic_product_id', '=', foodic_prdt.get('product').get('id'))],limit=1)
                            if not prdt:
                                ProductProduct.set_products_to_odoo({'data': [foodic_prdt.get('product')]})
                                prdt = ProductProduct.search([('foodic_product_id', '=', foodic_prdt.get('product').get('id')), ('active', 'in', [True, False])], limit=1)
                                # FoodicProduct.set_products_to_odoo({'data': [foodic_prdt.get('product')]})
                                # prdt = FoodicProduct.search([('foodic_product_id', '=', foodic_prdt.get('product').get('id'))], limit=1)

                            tax_ids = []
                            amount_tax = 0
                            price_unit = foodic_prdt.get('tax_exclusive_unit_price')
                            fixed_tax = False
                            for tax in foodic_prdt.get('taxes'):
                                tax_group_id = self.env.ref('wt_foodic.foodics_tax_group')
                                foodic_tax = AccountTax.search([('name', '=', 'VAT {}%'.format(tax.get('rate'))), ('amount', '=', tax.get('rate')), ('amount_type', '=', 'percent')], limit=1) 
                                # foodic_tax = AccountTax.search([('name', '=', 'VAT {}%'.format(tax.get('pivot').get('rate'))), ('amount', '=', tax.get('pivot').get('rate')), ('amount_type', '=', 'percent')], limit=1) 
                                if not foodic_tax:
                                    foodic_tax = AccountTax.create({'name': "VAT {}%".format(tax.get('rate')), 'amount': tax.get('rate'), 'amount_type': 'percent', 'country_id': self.env.company.country_id.id, 'tax_group_id': tax_group_id.id})
                                    # foodic_tax = AccountTax.create({'name': "VAT {}%".format(tax.get('pivot').get('rate')), 'amount': tax.get('pivot').get('rate'), 'amount_type': 'percent'})
                                # amount_tax = amount_tax + amount
                                # taxes = foodic_tax.compute_all(price_unit=price_unit, currency=None, quantity=foodic_prdt.get('quantity'), product=None, partner=None)
                                # price_tax = sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                                # if int(price_tax) != int(amount):
                                #     foodic_tax = AccountTax.search([('name', '=', 'VAT {}%'.format(amount)), ('amount', '=', amount), ('amount_type', '=', 'fixed')], limit=1) 
                                #     if not foodic_tax:
                                #         foodic_tax = AccountTax.create({'name': "VAT {}%".format(amount), 'amount': amount, 'amount_type': 'fixed'})
                                #     fixed_tax = True
                                tax_ids.append(foodic_tax.id)


                            is_returned = False
                            total_price = foodic_prdt.get('total_price')
                            # if foodic_prdt.get('status') == 6:
                            #     is_returned = True
                            #     total_price = -foodic_prdt.get('total_price')

                            is_void = True
                            foodic_discount =  foodic_prdt.get('discount_amount')

                            price_subtotal = foodic_prdt.get('tax_exclusive_total_price')
                            # amount_paid = amount_paid + foodic_prdt.get('total_price')
                            amount_total = amount_total + total_price
                            is_void = False

                            price_unit = foodic_prdt.get('tax_exclusive_unit_price')
                            amt = foodic_prdt.get('tax_exclusive_unit_price') * foodic_prdt.get('quantity')

                            if total_price == 0:
                                line_discount = 0
                            else:
                                line_discount += foodic_prdt.get('discount_amount')

                            # if price_unit == foodic_prdt.get('unit_price'):
                            #     line_discount += foodic_prdt.get('discount_amount')
                            # else:
                            #     tax_exclusive = True
                            #     line_discount += foodic_prdt.get('tax_exclusive_discount_amount')

                            
                            if not foodic_prdt.get('taxes') and foodic_prdt.get('tax_exclusive_total_price') != foodic_prdt.get('total_price'):
                                price_unit = foodic_prdt.get('unit_price')
                            
                            if total_price == 0:
                                # price_subtotal = foodic_prdt.get('tax_exclusive_unit_price') * foodic_prdt.get('quantity')
                                price_unit = price_subtotal = 0
                            else:
                                # total_tax = total_tax + (total_price - price_subtotal)
                                total_tax = total_tax + amount_tax
                            
                            if fixed_tax and foodic_prdt.get('quantity') > 1:
                                qty = 1
                                price_unit = price_unit * foodic_prdt.get('quantity')
                            else:
                                qty = foodic_prdt.get('quantity')

                            pos_order_line.append((0 ,0 ,{'name': prdt.name,
                                'name': prdt.name,
                                # 'full_product_name': prdt.name,
                                'full_product_name': prdt.name,
                                'qty': -qty if is_refund else qty,
                                # 'product_id': prdt.id,
                                'product_id': prdt.id,
                                'price_unit': 0 if moved_product or declined_product else price_unit,
                                # 'discount': line_discount,
                                # 'price_unit': foodic_prdt.get('unit_price'),
                                # 'price_subtotal': -price_subtotal if is_refund else price_subtotal,
                                # 'price_subtotal': -total_price if is_refund else total_price,
                                # 'price_subtotal_incl': -total_price if is_refund else total_price,
                                'price_subtotal': 0,
                                'price_subtotal_incl': 0,
                                'tax_ids': [(6, 0, tax_ids)] if tax_ids else [],
                                'is_void': is_void,
                                'is_returned': is_returned,
                                'is_moved': moved_product
                                }))

                    if not pos_order_line:
                        continue

                    # add line for charges
                    charge_applied = False
                    for charge in order.get('charges'):
                        # charge_product = FoodicProduct.search([('foodic_product_id', '=', charge.get('charge', {}).get('id'))], limit=1)
                        # if not charge_product:
                        #     FoodicProduct.set_products_to_odoo({'data': [order.get('charges')]})
                        #     charge_product = FoodicProduct.search([('foodic_product_id', '=', charge.get('charge', {}).get('id'))], limit=1)

                        charge_product = ProductProduct.search([('foodic_product_id', '=', charge.get('charge', {}).get('id'))], limit=1)
                        if not charge_product:
                            charge_product = ProductProduct.create({'foodic_product_id': charge.get('charge', {}).get('id'),
                                'name': charge.get('charge', {}).get('name'),
                                'lst_price': charge.get('charge', {}).get('value'),
                                'type': 'service'
                                })
                        tax_ids = []
                        for tax in charge.get('taxes'):
                            amount = tax.get('pivot').get('amount')
                            foodic_tax = AccountTax.search([('name', '=', 'VAT {}%'.format(tax.get('rate'))), ('amount', '=', tax.get('rate')), ('amount_type', '=', 'percent')]) 
                            if not foodic_tax:
                                foodic_tax = AccountTax.create({'name': "VAT {}%".format(tax.get('rate')), 'amount': tax.get('rate'), 'amount_type': 'percent', 'country_id': self.env.company.country_id.id, 'tax_group_id': tax_group_id.id})
                            tax_ids.append(foodic_tax.id)
                            total_tax = total_tax + amount
                        # if charge_product.odoo_product_id:
                        charge_applied = True
                        pos_order_line.append((0, 0, {'name': charge_product.name,
                            # 'name': charge_product.name,
                            'full_product_name': charge_product.name,
                            'qty': -1 if is_refund else 1,
                            'product_id': charge_product.id,
                            # 'price_unit': charge.get('unit_price'),
                            'price_unit': charge.get('tax_exclusive_amount'),
                            # 'price_subtotal': charge.get('tax_exclusive_amount'),
                            # 'price_subtotal': charge.get('amount'),
                            # 'price_subtotal_incl': charge.get('amount'),
                            'price_subtotal': 0, 
                            'price_subtotal_incl': 0,
                            'tax_ids': [(6, 0, tax_ids)] if tax_ids else [],
                            'is_charge': True
                            }))
                        # print(">>>>>>>>>>>>>>>>>Order with charge: ", order.get('reference'))
                        if charge.get('amount'):
                            # total_tax += charge.get('amount') - charge.get('tax_exclusive_amount')
                            amount_total += charge.get('amount')

                    # add tips line to the order
                    tips_amount = sum(list(map(lambda payment_data: payment_data.get('tips') if payment_data.get('tips') else 0, order.get('payments'))))
                    if tips_amount:
                        tip_product = self.env.ref('wt_foodic.foodic_tip_product')
                        pos_order_line.append((0, 0, {'name': tip_product.name,
                            'full_product_name': tip_product.name,
                            'qty': -1 if is_refund else 1,
                            'product_id': tip_product.id,
                            'price_unit': tips_amount,
                            'price_subtotal': 0,
                            'price_subtotal_incl': 0
                            }))

                    if order.get('rounding_amount'):
                        rounding_product = self.env.ref('wt_foodic.foodic_rounding_amount')
                        pos_order_line.append((0, 0, {'name': rounding_product.name,
                            'full_product_name': rounding_product.name,
                            'qty': -1 if is_refund else 1,
                            'product_id': rounding_product.id,
                            'price_unit': order.get('rounding_amount'),
                            'price_subtotal': 0,
                            'price_subtotal_incl': 0
                            }))

                    # add combo lines
                    for combo in order.get('combos') or []:
                        for combo_product in combo.get('products'):
                            if combo_product.get('status') == 5:
                                continue
                                
                            if combo_product.get('options'):
                                for options in combo_product.get('options'):
                                    if options.get('modifier_option'):
                                        # prdt = FoodicProduct.search([('foodic_product_id', '=', options.get('modifier_option').get('id'))], limit=1)
                                        prdt = ProductProduct.search([('foodic_product_id', '=', options.get('modifier_option').get('id')), ('active', 'in', [True, False])], limit=1)
                                        if not prdt:
                                            # FoodicProduct.with_context({'is_modifier': True}).set_products_to_odoo({'data': [options.get('modifier_option')]})
                                            # prdt = FoodicProduct.search([('foodic_product_id', '=', options.get('modifier_option').get('id'))], limit=1)
                                            ProductProduct.with_context({'is_modifier': True}).set_products_to_odoo({'data': [options.get('modifier_option')]})
                                            prdt = ProductProduct.search([('foodic_product_id', '=', options.get('modifier_option').get('id')), ('active', 'in', [True, False])], limit=1)
                                        pos_order_line.append((0, 0, {'name': prdt.id,
                                            # 'name': prdt.name,
                                            'full_product_name': prdt.name,
                                            'product_id': prdt.id,
                                            'qty': -combo_product.get('quantity') if is_refund else combo_product.get('quantity'),
                                            'price_subtotal': 0,
                                            'price_subtotal_incl': 0,
                                            'price_unit': options.get('unit_price'),
                                            'is_modifier': True,
                                            'is_combo': True
                                            }))

                            # prdt = FoodicProduct.search([('foodic_product_id', '=', combo_product.get('product').get('id')), ('active', 'in', [True, False])], limit=1)
                            prdt = ProductProduct.search([('foodic_product_id', '=', combo_product.get('product').get('id')), ('active', 'in', [True, False])],limit=1)
                            if not prdt:
                                # FoodicProduct.set_products_to_odoo({'data': [combo_product.get('product')]})
                                # prdt = FoodicProduct.search([('foodic_product_id', '=', combo_product.get('product').get('id')), ('active', 'in', [True, False])], limit=1)
                                ProductProduct.set_products_to_odoo({'data': [combo_product.get('product')]})
                                prdt = ProductProduct.search([('foodic_product_id', '=', combo_product.get('product').get('id')), ('active', 'in', [True, False])], limit=1)

                            # modifier_total = 0
                            # for modifier in combo_product.get('options'):
                            #     modifier_total += modifier.get('unit_price') * modifier.get('quantity')

                            tax_ids = []
                            for tax in combo_product.get('taxes'):
                                foodic_tax = AccountTax.search([('name', '=', 'VAT {}%'.format(tax.get('pivot').get('rate'))), ('amount', '=', tax.get('pivot').get('rate')), ('amount_type', '=', 'percent')], limit=1) 
                                if not foodic_tax:
                                    foodic_tax = AccountTax.create({'name': "VAT {}%".format(tax.get('pivot').get('rate')), 'amount': tax.get('pivot').get('rate'), 'amount_type': 'percent', 'country_id':self.env.company.country_id.id, 'tax_group_id': tax_group_id.id})
                                tax_ids.append(foodic_tax.id)

                            total_price = combo_product.get('total_price')
                            price_unit = combo_product.get('tax_exclusive_unit_price')
                            line_discount += combo_product.get('discount_amount')

                            if not combo_product.get('taxes') and combo_product.get('tax_exclusive_total_price') != foodic_prdt.get('total_price'):
                                price_unit = combo_product.get('unit_price')
                            elif total_price == 0:
                                price_unit = 0

                            pos_order_line.append((0, 0, {'name': prdt.id,
                                'name': prdt.name,
                                'full_product_name': prdt.name,
                                'qty': -combo_product.get('quantity') if is_refund else combo_product.get('quantity'),
                                'product_id': prdt.id,
                                'price_unit': price_unit,
                                'price_subtotal': 0, 
                                'price_subtotal_incl': 0,
                                'tax_ids': [(6, 0, tax_ids)] if tax_ids else [],
                                'is_combo': True
                                }))

                    # Discount amount
                    discount_applied = False
                    if order.get('discount_amount') or line_discount:
                        if order.get('discount'):
                            discount_product = ProductProduct.search([('foodic_product_id', '=', order.get('discount', {}).get('id'))], limit=1)
                            if not discount_product:
                                discount_product = ProductProduct.create({'foodic_product_id': order.get('discount', {}).get('id'),
                                    'name': order.get('discount', {}).get('name'),
                                    'type': 'service'
                                    })
                        else:
                            discount_product = self.env.ref('wt_foodic.foodic_discount')

                        # if tax_exclusive:
                        #     discount_amount = order.get('tax_exclusive_discount_amount') + line_discount
                        # else:
                        #     discount_amount = order.get('discount_amount') + line_discount
                        discount_amount = order.get('discount_amount') + line_discount
                        discount_applied = True
                        pos_order_line.append((0, 0, {'name': discount_product.name,
                            'full_product_name': discount_product.name,
                            'qty': -1 if is_refund else 1,
                            'product_id': discount_product.id,
                            'price_unit': -discount_amount,

                            # 'price_subtotal': -order.get('discount_amount'),
                            # 'price_subtotal_incl': -order.get('discount_amount'),
                            'price_subtotal': 0,
                            'price_subtotal_incl': 0
                            }))
                        amount_total -= order.get('discount_amount')

                    # returned order
                    if order.get('status') == 5:
                        amount_total = -amount_total
                        total_tax = -total_tax

                    date_order = order.get('opened_at')
                    if date_order:
                        date_order = datetime.strptime(date_order, '%Y-%m-%d %H:%M:%S')

                    #create order
                    cashier = ''
                    if order.get('creator'):
                        cashier = order.get('creator').get('name')

                    pos_order = PosOrder.create({
                        'foodic_order_ref': order.get('reference'),
                        'cashier': cashier,
                        'foodic_order_id': order.get('id'),
                        'session_id': session.id,
                        'partner_id': customer,
                        'date_order': date_order,
                        'lines': pos_order_line,
                        # 'amount_total': amount_total,
                        # 'amount_tax': total_tax,
                        'amount_total': 0,
                        'amount_tax': 0,
                        'amount_return': 0,
                        'amount_paid': 0,
                        'discounted_order': discount_applied,
                        'charged_order': charge_applied
                        })
                    _logger.info(">>>>>%s" % pos_order)

                    for line in pos_order.lines:
                        line._onchange_amount_line_all()
                    pos_order._onchange_amount_all()

                # Generate Payment for order
                self._cr.commit()
                context_make_payment = {"active_id": pos_order.id}
                if pos_order.amount_total == 0 and pos_order.state != 'paid':
                    payment_date = date.today().strftime('%Y-%m-%d')
                    pos_payment = pos_order.config_id.payment_method_ids[0]
                    make_payment = self.env['pos.make.payment'].with_context(context_make_payment).create({
                        'payment_date': payment_date,
                        'payment_method_id': pos_payment.id,
                        'config_id': branch.id,
                        'amount': 0,
                    })
                    ctx = make_payment.env.context.copy()
                    # make_payment.check()
                    make_payment.with_context(ctx).check()
                    # amount_paid = amount_total
                    amount_paid = 0
                    continue

                payments = pos_order.payment_ids.filtered(lambda payment: payment.foodic_payment_id != False)
                payment_count = 1
                for payment in order.get('payments'):
                    if payment.get('id') in payments.mapped('foodic_payment_id'):
                        continue
                    payment_date = payment.get('business_date')
                    if payment_date:
                        payment_date = datetime.strptime(payment_date, '%Y-%m-%d')
                    else:
                        payment_date = date.today().strftime('%Y-%m-%d')
                    pos_payment = PosPaymentmethod.sudo().search([('foodic_payment_method_id', '=', payment.get('payment_method').get('id'))], limit=1)
                    if not pos_payment:
                        PosPaymentmethod.set_payment_methods_to_odoo({'data': [payment.get('payment_method')]})
                        pos_payment = PosPaymentmethod.sudo().search([('foodic_payment_method_id', '=', payment.get('payment_method').get('id'))])
                    # if len(order.get('payments')) == 1:
                    #     amount_paid = pos_order.amount_total
                    # else
                    if payment_count == len(order.get('payments')):
                        amount_paid = pos_order.amount_total - pos_order.amount_paid
                    else:
                        amount_paid = payment.get('amount')
                        if payment.get('tips', 0):
                            amount_paid += payment.get('tips')
                    make_payment = self.env['pos.make.payment'].with_context(context_make_payment).create({
                        'payment_date': payment_date,
                        'payment_method_id': pos_payment.id,
                        'config_id': branch.id,
                        'amount': amount_paid,
                    })                    
                    pos_order.amount_paid += amount_paid
                    ctx = make_payment.env.context.copy()
                    ctx.update({'foodic_payment_id': payment.get('id')})
                    make_payment.with_context(ctx).check()
                    payment_count += 1
                # pos_order.amount_paid = amount_paid
                pos_order._onchange_amount_all()
                self._cr.commit()
                count += 1
        return False
        