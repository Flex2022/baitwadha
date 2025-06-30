# -*- coding: utf-8 -*-

from odoo import models, fields


class PopMessage(models.TransientModel):
    _name = "pop.message"
    _description = "Connection Message"

    name = fields.Char("Message", readonly=True)
