from odoo import fields, models, _


class ResPartner(models.Model):
	_inherit = 'res.partner'

	foodic_partner_id = fields.Char('Foodic Partner Id')

	def set_partner_to_odoo(self, res):
		ResPartner = self.env['res.partner']
		i = 0
		for foodic_partner in res.get('data'):
			vals = {'foodic_partner_id': foodic_partner.get('id'),
				'name': foodic_partner.get('name'),
				'phone': foodic_partner.get('phone'),
				'email': foodic_partner.get('email'),
			}
			
			partner = ResPartner.search([('foodic_partner_id', '=', foodic_partner.get('id'))])
			if not partner:
				ResPartner.create(vals)
			else:
				ResPartner.write(vals)

			i+=1
			if i%100 == 0:
				self.env.cr.commit()

