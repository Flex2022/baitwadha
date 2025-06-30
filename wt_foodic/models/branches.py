# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.tests.common import Form


class PosConfig(models.Model):
    _inherit = 'pos.config'

    foodic_branch_id = fields.Char('Foodic Branch Id')
    opening_from = fields.Char('Opening From')
    opening_to = fields.Char('Opening To')
    reference = fields.Char('Reference')
    name_localized = fields.Char('Name Localized')
    phone = fields.Char('Phone')

    def set_branches_to_odoo(self, res):
        i = 0
        for branch in res.get('data'):
            i += 1
            vals = {
                'foodic_branch_id': branch.get('id'),
                'name': branch.get('name'),
                'self_ordering_mode': 'nothing',
                'name_localized': branch.get('name_localized'),
                'reference': branch.get('reference'),
                'phone': branch.get('phone'),
                'opening_from': branch.get('opening_from'),
                'opening_to': branch.get('opening_to'),
                'module_pos_restaurant': True,
            }
            branch_id = self.search([('foodic_branch_id', '=', branch.get('id'))], limit=1)
            if branch_id:
                branch_id.update(vals)
            else:
                branch_id.create(vals)
            if i % 100 == 0:
                self.env.cr.commit()
        self.env.cr.commit()

    def cron_auto_close_session(self):
        # pass
        for rec in self.search([]):
            session = rec.current_session_id
            if session:
                if any(order.state == 'draft' for order in session.order_ids) or session.state == 'closed':
                    continue
                if session.state == 'closing_control':
                    action = session.action_pos_session_closing_control()
                    if isinstance(action, dict):
                        wizard = self.env['pos.close.session.wizard'].browse(action['res_id'])
                        wizard.with_context(action['context']).close_session()
                else:
                    res = session.get_closing_control_data()
                    if rec.cash_control:
                        if res.get('default_cash_details'):
                            session.post_closing_cash_details(res.get('default_cash_details', {}).get('amount', 0))
                    session.update_closing_control_state_session('')
                    rec._cr.commit()
                    bankPaymentMethodDiffPairs = []
                    bank_payment_methods = filter(lambda pm: pm.get('type') == 'bank', res.get('other_payment_methods'))
                    if bank_payment_methods:
                        bankPaymentMethodDiffPairs = list(map(lambda pm: [pm.get('id'), 0] ,bank_payment_methods))
                    response = session.close_session_from_ui(bankPaymentMethodDiffPairs)
                    if isinstance(response, dict) and response.get('message') == 'Force Close Session':
                        action = session.action_pos_session_closing_control()
                        if isinstance(action, dict):
                            wizard = self.env['pos.close.session.wizard'].browse(action['res_id'])
                            wizard.with_context(action['context']).close_session()
                            
                    #     balance = sum(session.move_id.line_ids.mapped('balance'))
                    #     session.action_pos_session_closing_control(session._get_balancing_account(), balance)
                    #     # session = self.env["pos.session"].browse(self.env.context["active_ids"])
                        
                    #     # wizard = self.env['pos.close.session.wizard'].browse(session.id)
                    #     # self.env['pos.close.session.wizard']

                    #     # wizard.with_context(**rec.env.context, active_ids=session.ids, active_model='pos.session').close_session()
                    #     # wizard.close_session()