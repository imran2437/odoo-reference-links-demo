from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestReferenceLink(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login='reference.link.owner', groups='base.group_user')
        cls.other = new_test_user(cls.env, login='reference.link.other', groups='base.group_user')

    def _link(self, **values):
        return self.env['imran.reference.link'].with_user(self.user).create({
            'name': 'Useful reference', 'url': 'https://example.org/reference', **values})

    def test_create_edit_favourite_and_open(self):
        link = self._link()
        self.assertEqual(link.user_id, self.user)
        self.assertEqual(link.company_id, self.env.company)
        self.assertEqual(link.category, 'reference')
        link.write({'notes': 'Read this later', 'category': 'learning'})
        link.action_toggle_favourite()
        self.assertTrue(link.favourite)
        self.assertEqual(link.action_open_link(), {'type':'ir.actions.act_url', 'url':link.url, 'target':'new'})
        link.action_toggle_favourite()
        self.assertFalse(link.favourite)

    def test_invalid_addresses_rejected_on_create(self):
        for url in ('javascript:alert(1)', 'data:text/html,test', 'file:///tmp/test', '//example.org',
                    'https://', 'https://user:password@example.org', 'https://example.org/a b',
                    'https://example.org/\npath', 'https://example.org\\path', 'https://example.org:99999',
                    'https://example.org:bad', 'https://[bad'):
            with self.subTest(url=url), self.assertRaises(ValidationError), self.cr.savepoint():
                self._link(url=url)

    def test_valid_addresses_and_rejected_update(self):
        for url in ('http://example.org', 'https://example.org/a?q=b#section', 'https://example.org:8443/a%20b'):
            self.assertEqual(self._link(url=url).action_open_link()['url'], url)
        link = self._link()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            link.write({'url':'javascript:alert(1)'})
        self.assertEqual(link.url, 'https://example.org/reference')

    def test_other_user_cannot_access_or_open(self):
        link = self._link()
        self.assertFalse(self.env['imran.reference.link'].with_user(self.other).search([('id','=',link.id)]))
        for action in (lambda: link.with_user(self.other).read(['url']),
                       lambda: link.with_user(self.other).write({'notes':'Denied'}),
                       lambda: link.with_user(self.other).action_toggle_favourite(),
                       lambda: link.with_user(self.other).action_open_link(),
                       lambda: link.with_user(self.other).unlink(),
                       lambda: link.with_user(self.other).copy()):
            with self.assertRaises(AccessError):
                action()

    def test_owner_cannot_be_overridden(self):
        link = self._link()
        with self.assertRaises(AccessError):
            link.write({'user_id':self.other.id})
        with self.assertRaises(AccessError):
            self._link(user_id=self.other.id)
        created = self.env['imran.reference.link'].with_user(self.user).with_context(default_user_id=self.other.id).create({
            'name':'My link', 'url':'https://example.org'})
        self.assertEqual(created.user_id, self.user)

    def test_company_isolation(self):
        company = self.env['res.company'].create({'name':'Reference Other Company'})
        self.user.company_ids = [Command.link(company.id)]
        link = self.env['imran.reference.link'].with_user(self.user).with_company(company).create({
            'name':'Company reference', 'url':'https://example.org'})
        with self.assertRaises(AccessError):
            link.with_context(allowed_company_ids=self.env.company.ids).action_open_link()
        with self.assertRaises(AccessError):
            self.env['imran.reference.link'].with_user(self.other).create({
                'name':'Denied', 'url':'https://example.org', 'company_id':company.id})
        other_link = self.env['imran.reference.link'].with_user(self.other).create({'name':'Own link','url':'https://example.org'})
        with self.assertRaises(AccessError):
            other_link.write({'company_id':company.id})

    def test_archive_restore_and_copy(self):
        link = self._link(notes='Personal reference', favourite=True)
        copied = link.copy({'name':'Another reference'})
        self.assertEqual((copied.url, copied.notes, copied.user_id), (link.url, link.notes, self.user))
        link.active = False
        links = self.env['imran.reference.link'].with_user(self.user)
        self.assertNotIn(link, links.search([]))
        self.assertIn(link, links.with_context(active_test=False).search([]))
        link.active = True
        self.assertIn(link, links.search([]))

    def test_search_order_and_batch_toggle(self):
        links = self.env['imran.reference.link'].with_user(self.user).create([
            {'name':'Alpha','url':'https://example.org','notes':'Reference keyword 63917'},
            {'name':'Beta','url':'https://example.org/tool','favourite':True}])
        model = self.env['imran.reference.link'].with_user(self.user)
        self.assertEqual(model.search([('id','in',links.ids)])[0], links[1])
        self.assertEqual(model.name_search('63917')[0][0], links[0].id)
        links.action_toggle_favourite()
        self.assertEqual(links.mapped('favourite'), [True,False])
