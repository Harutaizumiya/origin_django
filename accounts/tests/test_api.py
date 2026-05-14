from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.apps import AccountsConfig
from accounts.models import AuthToken
from accounts.services import AuthTokenService


@override_settings(AUTH_TOKEN_PEPPER="pepper")
class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="operator",
            password="correct-password",
            email="operator@example.com",
            first_name="Origin",
            last_name="User",
        )

    def _login(self) -> str:
        response = self.client.post(
            "/api/auth/login",
            {"username": "operator", "password": "correct-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]["token"]

    @staticmethod
    def _auth_header(token: str) -> dict:
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_accounts_app_imports(self):
        self.assertEqual(AccountsConfig.name, "accounts")

    def test_users_routes_are_not_exposed(self):
        response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 404)

    def test_login_success_returns_bearer_token_and_user(self):
        response = self.client.post(
            "/api/auth/login",
            {"username": "operator", "password": "correct-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        data = payload["data"]
        self.assertEqual(data["token_type"], "Bearer")
        self.assertEqual(data["expires_in"], 28800)
        self.assertEqual(data["user"]["username"], "operator")
        self.assertEqual(data["user"]["email"], "operator@example.com")
        self.assertNotEqual(AuthToken.objects.get().token_hash, data["token"])

    def test_login_rejects_bad_password(self):
        response = self.client.post(
            "/api/auth/login",
            {"username": "operator", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"code": 4011, "message": "unauthenticated", "data": None})

    def test_me_returns_current_user(self):
        token = self._login()

        response = self.client.get("/api/auth/me", **self._auth_header(token))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["username"], "operator")
        self.assertEqual(response.json()["data"]["first_name"], "Origin")

    def test_logout_revokes_current_token(self):
        token = self._login()

        logout_response = self.client.post("/api/auth/logout", {}, format="json", **self._auth_header(token))
        me_response = self.client.get("/api/auth/me", **self._auth_header(token))

        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(logout_response.json()["data"], {"revoked": True})
        self.assertIsNotNone(AuthToken.objects.get().revoked_at)
        self.assertEqual(me_response.status_code, 401)
        self.assertEqual(me_response.json(), {"code": 4011, "message": "unauthenticated", "data": None})

    def test_expired_token_returns_unauthenticated(self):
        token = "expired-token"
        AuthToken.objects.create(
            user=self.user,
            token_hash=AuthTokenService.hash_token(token),
            issued_at=timezone.now() - timedelta(hours=9),
            expires_at=timezone.now() - timedelta(hours=1),
        )

        response = self.client.get("/api/auth/me", **self._auth_header(token))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"code": 4011, "message": "unauthenticated", "data": None})
