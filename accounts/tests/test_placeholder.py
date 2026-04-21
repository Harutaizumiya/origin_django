from django.test import SimpleTestCase

from accounts.apps import AccountsConfig
from accounts.schemas import AccountPlaceholderSerializer
from accounts.services import AccountPlaceholderService


class AccountsPlaceholderTests(SimpleTestCase):
    def test_accounts_app_imports(self):
        self.assertEqual(AccountsConfig.name, "accounts")
        self.assertEqual(AccountPlaceholderService.healthcheck(), "accounts-placeholder")
        self.assertEqual(AccountPlaceholderSerializer().data, {})

    def test_users_routes_are_not_exposed(self):
        response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 404)
