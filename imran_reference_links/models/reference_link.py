from urllib.parse import urlsplit

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ReferenceLink(models.Model):
    _name = 'imran.reference.link'
    _description = 'Personal Reference Link'
    _order = 'favourite desc, name, id desc'
    _rec_names_search = ['name', 'url', 'notes']
    _check_company_auto = True

    name = fields.Char(string='Title', required=True)
    url = fields.Char(string='Web Address', required=True)
    category = fields.Selection([
        ('reference', 'Reference'), ('learning', 'Learning'), ('tool', 'Tool'),
    ], required=True, default='reference', index=True)
    favourite = fields.Boolean(string='Favourite', default=False, index=True)
    notes = fields.Text(string='Notes')
    active = fields.Boolean(default=True)
    user_id = fields.Many2one('res.users', string='Owner', required=True,
                             default=lambda self: self.env.user, readonly=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                default=lambda self: self.env.company, index=True)

    @api.constrains('url')
    def _check_url(self):
        for link in self:
            value = link.url or ''
            try:
                parsed = urlsplit(value)
                valid = (parsed.scheme in ('http', 'https') and bool(parsed.hostname)
                         and not parsed.username and not parsed.password
                         and '\\' not in value
                         and not any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value))
                parsed.port  # Reject malformed and out-of-range ports.
            except ValueError:
                valid = False
            if not valid:
                raise ValidationError(_('Enter a full http:// or https:// web address without spaces or login credentials.'))

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for values in vals_list:
            values = dict(values)
            values.setdefault('user_id', self.env.uid)
            values.setdefault('company_id', self.env.company.id)
            if not self.env.su and values['user_id'] != self.env.uid:
                raise AccessError(_('You can create reference links only for yourself.'))
            if not self.env.su and values['company_id'] not in self.env.companies.ids:
                raise AccessError(_('Select a company you are allowed to use.'))
            prepared.append(values)
        return super().create(prepared)

    def write(self, values):
        self.check_access('write')
        if not self.env.su and 'user_id' in values:
            raise AccessError(_('The link owner cannot be changed.'))
        if (not self.env.su and 'company_id' in values
                and values['company_id'] not in self.env.companies.ids):
            raise AccessError(_('Select a company you are allowed to use.'))
        return super().write(values)

    def action_toggle_favourite(self):
        self.check_access('write')
        for link in self:
            link.favourite = not link.favourite
        return True

    def action_open_link(self):
        self.ensure_one()
        self.check_access('read')
        self._check_url()
        return {'type': 'ir.actions.act_url', 'url': self.url, 'target': 'new'}
