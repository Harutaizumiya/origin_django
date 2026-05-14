import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import DatabaseError
from django.utils import timezone

from accounts.models import AuthToken
from common.exceptions import ConflictApiError, UnauthenticatedApiError


class AuthTokenService:
    token_type = "Bearer"
    expires_in_seconds = 8 * 60 * 60

    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        pepper = getattr(settings, "AUTH_TOKEN_PEPPER", settings.SECRET_KEY)
        return hashlib.sha256(f"{token}{pepper}".encode("utf-8")).hexdigest()

    @staticmethod
    def serialize_user(user) -> dict:
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
        }

    @classmethod
    def login(cls, *, request, username: str, password: str) -> dict:
        user = authenticate(request=request, username=username, password=password)
        if user is None or not user.is_active:
            raise UnauthenticatedApiError("Invalid username or password")

        token = cls.generate_token()
        issued_at = timezone.now()
        expires_at = issued_at + timedelta(seconds=cls.expires_in_seconds)
        try:
            AuthToken.objects.create(
                user=user,
                token_hash=cls.hash_token(token),
                issued_at=issued_at,
                expires_at=expires_at,
            )
        except DatabaseError as exc:
            raise ConflictApiError("Unable to issue auth token") from exc

        return {
            "token": token,
            "token_type": cls.token_type,
            "expires_in": cls.expires_in_seconds,
            "expires_at": expires_at,
            "user": cls.serialize_user(user),
        }

    @classmethod
    def get_valid_auth_token(cls, token: str) -> AuthToken | None:
        try:
            auth_token = AuthToken.objects.select_related("user").filter(token_hash=cls.hash_token(token)).first()
        except DatabaseError as exc:
            raise ConflictApiError("Unable to validate auth token") from exc
        if auth_token is None:
            return None
        if not auth_token.is_active:
            return None
        if not auth_token.user.is_active:
            return None
        return auth_token

    @staticmethod
    def logout(auth_token: AuthToken | None) -> dict:
        if auth_token is not None and auth_token.revoked_at is None:
            auth_token.revoked_at = timezone.now()
            try:
                auth_token.save(update_fields=["revoked_at"])
            except DatabaseError as exc:
                raise ConflictApiError("Unable to revoke auth token") from exc
        return {"revoked": True}
