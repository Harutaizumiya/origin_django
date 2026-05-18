from datetime import timedelta

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.apps import AccountsConfig
from accounts.models import AuthToken
from accounts.services import AuthTokenService, PermissionService


@override_settings(AUTH_TOKEN_PEPPER="pepper")
class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        PermissionService.sync_permissions()
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
        permission = PermissionService.permission_queryset_for_codes(["products_read"]).get()
        self.user.user_permissions.add(permission)

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
        self.assertEqual(data["user"]["permissions"], ["products_read"])
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
        permission = PermissionService.permission_queryset_for_codes(["products_read"]).get()
        self.user.user_permissions.add(permission)
        token = self._login()

        response = self.client.get("/api/auth/me", **self._auth_header(token))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["username"], "operator")
        self.assertEqual(response.json()["data"]["first_name"], "Origin")
        self.assertEqual(response.json()["data"]["permissions"], ["products_read"])

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


class PermissionManagementApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        PermissionService.sync_permissions()
        self.superuser = User.objects.create_superuser(
            username="admin",
            password="admin123",
            email="admin@example.com",
        )
        self.normal_user = User.objects.create_user(username="normal", password="password")

    def _as_superuser(self):
        self.client.force_authenticate(user=self.superuser)

    def test_non_superuser_cannot_access_permission_management(self):
        self.client.force_authenticate(user=self.normal_user)

        response = self.client.get("/api/auth/permissions")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"code": 4031, "message": "forbidden", "data": None})

    def test_superuser_can_list_permission_catalog(self):
        self._as_superuser()

        response = self.client.get("/api/auth/permissions")

        self.assertEqual(response.status_code, 200)
        codes = [
            permission["code"]
            for group in response.json()["data"]["items"]
            for permission in group["permissions"]
        ]
        self.assertIn("products_read", codes)
        self.assertIn("batch_operations_loss", codes)

    def test_superuser_can_create_role_and_assign_to_user(self):
        self._as_superuser()
        role_response = self.client.post(
            "/api/auth/roles",
            {"name": "warehouse", "permission_codes": ["products_read", "batch_operations_loss"]},
            format="json",
        )

        user_response = self.client.post(
            "/api/auth/users",
            {
                "username": "worker",
                "password": "worker-password",
                "email": "worker@example.com",
                "group_ids": [role_response.json()["data"]["id"]],
                "permission_codes": ["qr_scans_create"],
            },
            format="json",
        )

        self.assertEqual(role_response.status_code, 201)
        self.assertEqual(role_response.json()["data"]["permissions"], ["batch_operations_loss", "products_read"])
        self.assertEqual(user_response.status_code, 201)
        data = user_response.json()["data"]
        self.assertEqual(data["username"], "worker")
        self.assertEqual(data["direct_permissions"], ["qr_scans_create"])
        self.assertEqual(
            data["effective_permissions"],
            ["batch_operations_loss", "products_read", "qr_scans_create"],
        )

    def test_role_delete_rejects_assigned_role(self):
        self._as_superuser()
        group = Group.objects.create(name="assigned")
        self.normal_user.groups.add(group)

        response = self.client.delete(f"/api/auth/roles/{group.id}")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"code": 4091, "message": "conflict", "data": None})

    def test_superuser_can_reset_user_password(self):
        self._as_superuser()

        response = self.client.post(
            f"/api/auth/users/{self.normal_user.id}/password",
            {"password": "new-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.normal_user.refresh_from_db()
        self.assertTrue(self.normal_user.check_password("new-password"))
