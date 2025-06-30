from odoo import models, fields


class FoodicOperation(models.TransientModel):
    _name = "foodic.operation"
    _description = 'foodic operations'

    foodic_instance_id = fields.Many2one('foodics.connector')
    from_date = fields.Date()
    operation = fields.Selection([('sync_branch', 'Import Branch'),
                                ('sync_payment_method', 'Import Payment Methods'),
                                ('sync_categories', 'Import Categories'),
                                ('sync_products', 'Import Products'),
                                ('sync_orders', 'Import Orders'),
                                # ('sync_suppliers', 'Import Suppliers'),
                                # ('sync_inventory_items', 'Import Inventory Items'),
                                # ('sync_modifier_products', 'Import Modifier Product'),
                                ('sync_purchase_order', 'Import Purchase Order'),
                                ('specific_orders','Import Specific Orders'),

                                # ('sync_transactions', 'Import Transactions'),
                                ], default="sync_branch", required=True)
    order_reference = fields.Char(help='Provide foodic order reference separated by coma(,)')


    def foodic_execute(self):
        foodic = self.foodic_instance_id
        if self.operation == 'specific_orders':
            foodic.get_specific_orders(self.order_reference)
        elif self.operation == 'sync_branch':
            foodic.get_branches()
        elif self.operation == 'sync_suppliers':
            foodic.get_suppliers()
        elif self.operation == 'sync_payment_method':
            foodic.get_payment_methods()
        elif self.operation == 'sync_categories':
            foodic.get_categories_methods()
        elif self.operation == 'sync_products':
            foodic.with_context({'is_modifier': False}).get_products_methods()
        elif self.operation == 'sync_orders':
            foodic.get_orders_methods(self.from_date)
        elif self.operation == 'sync_inventory_items':
            foodic.get_inventory_items()
        elif self.operation == 'sync_modifier_products':
            foodic.with_context({'is_modifier': True}).get_products_methods()
        elif self.operation == 'sync_purchase_order':
            foodic.foodics_import_purchase_orders()
        elif self.operation == 'sync_import_warehouse':
            foodic.foodics_import_warehouse()
        elif self.operation == 'sync_transactions':
            foodic.foodics_import_transactions()
            
