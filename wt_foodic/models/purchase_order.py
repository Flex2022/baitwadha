# -*- coding: utf-8 -*-
from odoo import fields, models, _
from datetime import datetime, date
from dateutil import parser
from odoo.tools import float_is_zero
import json


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    foodic_order_id = fields.Char()

    def set_orders_to_odoo(self, orders):
        PurchaseOrder = self.env['purchase.order']
        PurchaseOrderLine = self.env['purchase.order.line']
        ProductProduct = self.env['product.product']
        ResPartner = self.env['res.partner']

        for rec in orders.get('data'):
            lines = []
            order = PurchaseOrder.search([('foodic_order_id', '=', rec.get('id'))])            
            if rec.get('business_date'):
                order_date = datetime.strptime(rec.get('business_date'), '%Y-%m-%d')
            else:
                order_date = datetime.today()

            for item in rec.get('items'):
                prdt = ProductProduct.search([('foodic_product_id', '=', item.get('id')), ('active', 'in', [True, False])],limit=1)
                if not prdt:
                    ProductProduct.set_products_to_odoo({'data': [item]})
                    prdt = ProductProduct.search([('foodic_product_id', '=', item.get('id')), ('active', 'in', [True, False])],limit=1)

                vals = {'name': prdt.name,
                'product_id': prdt.id,
                'price_unit': item.get('pivot').get('cost'),
                'product_qty': item.get('pivot').get('quantity'),
                'date_planned': order_date,
                'product_uom': self.env.ref('uom.product_uom_categ_unit').id,
                'taxes_id': []
                }
                po_line = False
                if order:
                    po_line = PurchaseOrderLine.search([('order_id', '=', order.id), ('product_id', '=', prdt.id)])
                    if po_line:
                        lines.append((1, po_line.id, vals))
                
                if not po_line:
                    lines.append((0, 0, vals))

            supplier = False
            if rec.get('supplier'):
                supplier = ResPartner.search([('foodic_partner_id', '=', rec.get('supplier').get('id')), ('active', 'in', [True, False])], limit=1)
                if not supplier:
                    ResPartner.set_partner_to_odoo({'data': [rec.get('supplier')]})
                    supplier = ResPartner.search([('foodic_partner_id', '=', rec.get('supplier').get('id')), ('active', 'in', [True, False])], limit=1)

            
            vals = {'partner_id': supplier.id,
            'date_order': order_date,
            'order_line': lines,
            'foodic_order_id': rec.get('id')
            }
            if rec.get('reference'):
                vals['name'] = rec.get('reference')

            if not order:
                order = PurchaseOrder.create(vals)
            else:
                order.write(vals)

            if rec.get('status') == 3: #Approved
                order.button_confirm()

            self._cr.commit()
