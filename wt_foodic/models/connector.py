import requests
import datetime
from odoo import fields, models, api, _
from odoo.exceptions import UserError
import json
import logging
import time
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

class FoodicsConnector(models.Model):
    _name = 'foodics.connector'
    _rec_name = 'business_name'
    _description = "Foodics Connector"

    business_name = fields.Char(string='Business', readonly=True)
    user_name = fields.Char(string='User', readonly=True, copy=False)
    email = fields.Char(readonly=True, copy=False)
    order_date = fields.Date()
    access_token = fields.Char(string='Access Token', required=True)

    from_date = fields.Date(string='Last POS Order Imported Date')
    last_purchase_order_import_date = fields.Date(string='Last Purchase Order Imported Date')
    to_date = fields.Date(string='To Date')
    state = fields.Selection([('authenticate', 'Authenticate'), ('authenticated', 'Authenticated')], default='authenticate',copy=False)
    page = fields.Integer(default=1)
    note = fields.Text()
    environment = fields.Selection([('sandbox', 'Sandbox'), ('production', 'Production')], required=True, default='production')
    url = fields.Char(compute='set_foodics_url')
    product_timestamp = fields.Char(default='2000-01-01 01:01:01')
    current_product_page = fields.Integer(default=1)
    current_product_timestamp = fields.Char(default='2000-01-01 01:01:01')

    @api.depends('environment')
    def set_foodics_url(self):
        for rec in self:
            if rec.environment == 'sandbox':
                rec.url = 'https://api-sandbox.foodics.com'
            else:
                rec.url = 'https://api.foodics.com'

    def foodics_whoami(self):
        res = self.foodic_import_data(self.url + '/v5/whoami')
        self.business_name = res.get('data').get('business').get('name')
        self.user_name = res.get('data').get('user').get('name')
        self.email = res.get('data').get('user').get('email')
        self.state = 'authenticated'

    def authenticate(self):
        self.foodics_whoami()
        # console = 'console-sandbox' if self.environment == 'sandbox' else 'console'
        # target_url = 'https://%s.foodics.com/authorize?client_id=%s&state=%s' % (console, self.client_id, self.id)
        # return {
        #     'type': 'ir.actions.act_url',
        #     'target': 'self',
        #     'url': target_url,
        # }

    def foodic_import_data(self, url):
        access_token = self.access_token
        headers = {
            'authorization': "Bearer %s" % access_token,
            'content-type': 'text/plain',
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            res = response.json()
            return res
        else:
            raise UserError(_('Something Went Wrong !'))

    def success_popup(self, data):
        return {
            "name": "Message",
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "pop.message",
            "target": "new",
            "context": {
                "default_name": "Successfully %s Imported!"%data
            },
        }

    def get_branches(self):
        data_access_url = self.url + '/v5/branches'
        res = self.foodic_import_data(data_access_url)
        Branch = self.env['pos.config']
        Branch.set_branches_to_odoo(res)
        last_page = int(res.get('meta').get('last_page'))
        if last_page > 1:
            for page_no in range(int(res.get('meta').get('current_page')) + 1, last_page + 1):
                res = self.foodic_import_data(data_access_url + "?page={}".format(page_no))
                Branch.set_branches_to_odoo(res)
        return self.success_popup('Branches')

    def get_payment_methods(self):
        data_access_url = self.url + '/v5/payment_methods'
        res = self.foodic_import_data(data_access_url)
        PaymentMethods = self.env['pos.payment.method']
        PaymentMethods.set_payment_methods_to_odoo(res)
        last_page = int(res.get('meta').get('last_page'))
        if last_page > 1:
            for page_no in range(int(res.get('meta').get('current_page')) + 1, last_page + 1):
                res = self.foodic_import_data(data_access_url + "?page={}".format(page_no))
                PaymentMethods.set_payment_methods_to_odoo(res)
        return self.success_popup('Payment Methods')

    def get_categories_methods(self):
        data_access_url = self.url + '/v5/categories'
        res = self.foodic_import_data(data_access_url)
        PosCategory = self.env['pos.category']
        PosCategory.set_categories_to_odoo(res)
        last_page = int(res.get('meta').get('last_page'))
        if last_page > 1:
            for page_no in range(int(res.get('meta').get('current_page')) + 1, last_page + 1):
                res = self.foodic_import_data(data_access_url + "?page={}".format(page_no))
                PosCategory.set_categories_to_odoo(res)
        return self.success_popup('Categories')


    def get_products_methods(self):
        data_access_url = self.url + '/v5/products?filter[updated_after]=%s' % self.product_timestamp
        res = self.foodic_import_data(data_access_url)
        Product = self.env['product.product']
        self.current_product_timestamp = Product.set_products_to_odoo(res, self.current_product_timestamp)
        last_page = int(res.get('meta').get('last_page'))
        page = self.current_product_page if self.current_product_page != 1 else int(res.get('meta').get('current_page')) + 1
        if last_page > 1:
            for page_no in range(page, last_page + 1):
                res = self.foodic_import_data(data_access_url + "&page={}".format(page_no))
                self.current_product_timestamp = Product.set_products_to_odoo(res, self.current_product_timestamp)
                self.current_product_page = page_no
                self._cr.commit()
            self.product_timestamp = self.current_product_timestamp
            self.current_product_page = 1
            self._cr.commit()

    def foodics_import_purchase_orders(self):
        data_access_url = self.url + '/v5/purchase_orders?include=supplier,items,branch'
        res = self.foodic_import_data(data_access_url)
        purchase_order = self.env['purchase.order']
        purchase_order.set_orders_to_odoo(res)
        last_page = int(res.get('meta').get('last_page'))
        if last_page > 1:
            for page_no in range(int(res.get('meta').get('current_page')) + 1, last_page + 1):
                res = self.foodic_import_data(data_access_url + "&page={}".format(page_no))
                purchase_order.set_orders_to_odoo(res)

    def get_orders_methods(self, from_date=None):
        if not from_date and not self.from_date:
            from_date = (datetime.datetime.now() - relativedelta(years=1000)).date().strftime('%Y-%m-%d')
        elif from_date:
            from_date = (from_date - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            from_date = self.from_date.strftime('%Y-%m-%d')
        
        self.from_date = from_date
        to_date = (datetime.datetime.now().date() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        url = self.url + "/v5/orders?include=branch,charges.charge,charges.taxes,discount,customer,products.product,payments,payments.paymentMethod,products.taxes,creator,products.options.modifierOption&sort=reference&page={}&filter[business_date_after]={}&filter[business_date_before]={}"
        # url = self.url + "/v5/orders?include=branch,charges,customer,products.product,payments,payments.paymentMethod,products.taxes,creator,products.options.modifierOption&sort=reference&page={}&filter[status]=5"
        # url = self.url + "/v5/orders?include=branch,charges.charge,discount,charges.taxes,discount,customer,products.product,payments,payments.paymentMethod,products.taxes,creator,products.options.modifierOption&sort=reference&page={}&filter[reference]=36954"
        res = self.foodic_import_data(url.format(self.page, from_date, to_date))
        # res = self.foodic_import_data(url.format(self.page))

        Order = self.env['pos.order']
        Order.set_orders_to_odoo(res, to_date)
        if res and res.get('meta', {}):
            last_page = int(res.get('meta').get('last_page'))
            current_page = int(res.get('meta').get('current_page'))
            if last_page > 1:
                for page_no in range(current_page + 1, last_page + 1):
                    if page_no % 30 == 0:
                        time.sleep(60)
                    res = self.foodic_import_data(url.format(page_no, from_date, to_date))
                    # res = self.foodic_import_data(url.format(page_no))
                    self.page = page_no
                    Order.set_orders_to_odoo(res, to_date)
                self.page = 1
                self.from_date = (datetime.datetime.now().date() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            return self.success_popup('Orders')

    def get_specific_orders(self, order_references):
        url = self.url + "/v5/orders?include=tags,branch,charges.charge,charges.taxes,discount,customer,products.product,payments,payments.paymentMethod,products.taxes,creator,products.options.modifierOption,combos.combo_size,combos.products.product,combos.products.options,combos.products.taxes,combos.products.options.modifierOption&sort=reference&page={}&filter[reference]={}".format(1, order_references)
        res = self.foodic_import_data(url)
        Order = self.env['pos.order']
        Order.set_orders_to_odoo(res)
        if res and res.get('meta', {}):
            last_page = int(res.get('meta').get('last_page'))
            current_page = int(res.get('meta').get('current_page'))
            if last_page > 1:
                for page_no in range(current_page + 1, last_page + 1):
                    if page_no % 30 == 0:
                        time.sleep(60)
                    res = self.foodic_import_data(url.format(page_no, order_references))
                    Order.set_orders_to_odoo(res)


    def cron_sync_pos_order(self):
        for connector in self.search([('state', '=', 'authenticated')]):
            connector.get_orders_methods()

    def cron_sync_products(self):
        for connector in self.search([('state', '=', 'authenticated')]):
            connector.get_products_methods()
