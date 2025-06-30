# -*- coding: utf-8 -*-
{
    "name": "Foodics Odoo Connector",
    "version": "18.0",
    "category": "Point Of Sale",
    "summary": "Sync data from foodics to odoo",
    "description": "With this application user will be able to sync branches, payment methods, categories, products and orders from foodics to odoo. from date and to date functionality.",
    "author": "Warlock Technologies Pvt Ltd.",
    "website": "http://warlocktechnologies.com",
    "support": "info@warlocktechnologies.com",
    "depends": ["point_of_sale", "stock", "product", "purchase", "pos_self_order"],
    "data": [
        "security/ir.model.access.csv",
        "data/demo_data.xml",
        "data/cron.xml",
        "views/connector_view.xml",
        "views/branches_view.xml",
        "views/payment_methods_view.xml",
        "views/categories_view.xml",
        "views/pos_orders_view.xml",
        "views/purchase_order_views.xml",
        "wizard/foodic_operation_views.xml"
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
    "price": 300,
    "currency": "USD",
    "images": ["static/image/screen_image.png"],
    "license": "OPL-1"
}


