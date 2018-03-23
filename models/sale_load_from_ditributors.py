import base64
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleLoadFromDistributorsWizard(models.TransientModel):
    _name = 'sale.load.from_distributors_wizard'

    edi_file = fields.Binary(
        filters='*.txt',
        required=True,
    )

    def get_partner_by_ref(self, ref):
        partner_obj = self.env['res.partner']
        partners = partner_obj.search([('ref', '=', ref)], limit=1)
        if len(partners):
            return partners[0]
        return False

    def get_pricelist_by_name(self, name):
        pricelist_obj = self.env['product.pricelist']
        pricelists = pricelist_obj.search([('name', '=', name)], limit=1)
        if len(pricelists):
            return pricelists[0]
        return False

    def get_product_by_ref(self, ref):
        pricelist_obj = self.env['product.product']
        pricelists = pricelist_obj.search(
            [('default_code', '=', ref)], limit=1)
        if len(pricelists):
            return pricelists[0]
        return False

    def get_partner_by_parent_and_name(self, parent, name):
        partner_obj = self.env['res.partner']
        partners = partner_obj.search(
            [('parent_id', '=', parent.id), ('name', '=', name)], limit=1)
        if len(partners):
            return partners[0]
        return False

    @api.one
    def action_load(self):
        file_content = base64.decodestring(self.edi_file)
        line_n = 1
        sale_order = {}
        sale_order_lines = []
        sale_orders = []
        for line in file_content.splitlines():
            elements = line.split()
            if elements:
                if elements[0] == 'R':
                    if sale_order:
                        sale_orders.append((sale_order, sale_order_lines))
                        sale_order = {}
                        sale_order_lines = []
                    if len(elements) >= 5:
                        partner = self.get_partner_by_ref(elements[1])
                        if not partner:
                            raise ValidationError(
                                _('Invalid partner ref `' + elements[1] + '` in line ' + str(line_n)))
                        pricelist = self.get_pricelist_by_name(elements[4])
                        if not pricelist:
                            raise ValidationError(
                                _('Invalid price list `' + elements[4] + '` in line ' + str(line_n)))
                        if len(self.env['sale.order'].search([('name', '=', elements[2])])):
                            raise ValidationError(
                                _('Sale order `' + elements[2] + '` already exist in line ' + str(line_n)))

                        sale_order['partner_id'] = partner.id
                        sale_order['client_order_ref'] = elements[2]
                        sale_order['commitment_date'] = elements[3],
                        sale_order['pricelist_id'] = pricelist.id

                        if len(elements) > 5:
                            partner_shipping_name = ''
                            for element in elements[5:]:
                                partner_shipping_name += element + ' '
                            partner_shipping_name = partner_shipping_name[:-1]
                            partner_shipping = self.get_partner_by_parent_and_name(
                                partner, partner_shipping_name)
                            if not partner_shipping:
                                raise ValidationError(
                                    _('Invalid partner shipping name `' + partner_shipping_name + '` in line ' + str(line_n)))
                            sale_order['partner_shipping_id'] = partner_shipping.id
                    else:
                        raise ValidationError(
                            _('Invalid args number in `' + line + '` in line ' + str(line_n)))
                elif len(elements) == 3:
                    product = self.get_product_by_ref(elements[1])
                    if not product:
                        raise ValidationError(
                            _('Invalid product ref `' + elements[1] + '` in line ' + str(line_n)))
                    sale_order_lines.append({
                        'price_unit': float(elements[2]),
                        'product_id': product.id,
                        'product_uom_qty': int(elements[0]),
                    })
                else:
                    raise ValidationError(
                        _('Invalid args number in `' + line + '` in line ' + str(line_n)))
            line_n += 1
        if sale_order:
            sale_orders.append((sale_order, sale_order_lines))
        for sale_order2, sale_order_lines in sale_orders:
            date_string = sale_order2['commitment_date'][0]
            sale_order_id = self.env['sale.order'].create(sale_order2)
            sale_order_id.commitment_date = fields.Datetime.from_string(
                date_string)
            for sale_order_line in sale_order_lines:
                sale_order_line['order_id'] = sale_order_id.id
                self.env['sale.order.line'].create(sale_order_line)
