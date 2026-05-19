import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError
from django.db.models import Prefetch
from django.db import transaction
from django.utils import timezone

from accounts.models import AuthToken
from accounts.permissions import (
    COMPONENT_PERMISSION_CODES,
    COMPONENT_PERMISSIONS,
    PERMISSION_APP_LABEL,
    PERMISSION_CONTENT_TYPE_MODEL,
    catalog_as_dicts,
)
from common.cache_utils import CACHE_GROUP_AUTH_PERMISSIONS, CACHE_GROUP_AUTH_ROLES, invalidate_cache_groups
from common.exceptions import ConflictApiError, NotFoundApiError, UnauthenticatedApiError, ValidationApiError


class AuthTokenService:
    expires_in_seconds = 8 * 60 * 60
    remember_me_expires_in_seconds = 3 * 24 * 60 * 60

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
            "permissions": PermissionService.effective_permission_codes(user),
        }

    @classmethod
    def login(cls, *, request, username: str, password: str, remember_me: bool = False) -> dict:
        user = authenticate(request=request, username=username, password=password)
        if user is None or not user.is_active:
            raise UnauthenticatedApiError("Invalid username or password")

        token = cls.generate_token()
        issued_at = timezone.now()
        expires_in = cls.remember_me_expires_in_seconds if remember_me else cls.expires_in_seconds
        expires_at = issued_at + timedelta(seconds=expires_in)
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
            "expires_in": expires_in,
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


class PermissionService:
    @staticmethod
    def catalog() -> list[dict]:
        return catalog_as_dicts()

    @classmethod
    def sync_permissions(cls) -> None:
        content_type, _ = ContentType.objects.get_or_create(
            app_label=PERMISSION_APP_LABEL,
            model=PERMISSION_CONTENT_TYPE_MODEL,
        )
        for item in COMPONENT_PERMISSIONS:
            Permission.objects.update_or_create(
                content_type=content_type,
                codename=item.code,
                defaults={"name": item.name},
            )

    @staticmethod
    def grouped_catalog() -> list[dict]:
        groups: dict[str, dict] = {}
        for item in catalog_as_dicts():
            groups.setdefault(item["component"], {"component": item["component"], "permissions": []})
            groups[item["component"]]["permissions"].append(item)
        return list(groups.values())

    @classmethod
    def permission_queryset_for_codes(cls, codes: list[str]):
        cls.validate_permission_codes(codes)
        return Permission.objects.filter(
            content_type__app_label=PERMISSION_APP_LABEL,
            codename__in=codes,
        )

    @staticmethod
    def validate_permission_codes(codes: list[str]) -> None:
        unknown = sorted(set(codes) - COMPONENT_PERMISSION_CODES)
        if unknown:
            raise ValidationApiError(f"Unknown permission codes: {', '.join(unknown)}")

    @staticmethod
    def effective_permission_codes(user) -> list[str]:
        if getattr(user, "is_superuser", False):
            return sorted(COMPONENT_PERMISSION_CODES)
        if not getattr(user, "is_active", True):
            return []
        permission_strings = user.get_all_permissions()
        return sorted(
            permission.rsplit(".", 1)[-1]
            for permission in permission_strings
            if permission.rsplit(".", 1)[-1] in COMPONENT_PERMISSION_CODES
        )

    @classmethod
    def user_has_permission(cls, user, code: str) -> bool:
        if code not in COMPONENT_PERMISSION_CODES:
            return False
        return code in cls.effective_permission_codes(user)


class RoleService:
    @staticmethod
    def component_permission_queryset():
        return Permission.objects.filter(
            content_type__app_label=PERMISSION_APP_LABEL,
            codename__in=COMPONENT_PERMISSION_CODES,
        )

    @classmethod
    def serialize_role(cls, group: Group) -> dict:
        prefetched_permissions = getattr(group, "component_permissions", None)
        if prefetched_permissions is None:
            prefetched_permissions = group.permissions.filter(
                content_type__app_label=PERMISSION_APP_LABEL,
                codename__in=COMPONENT_PERMISSION_CODES,
            )
        permissions = sorted(permission.codename for permission in prefetched_permissions)
        return {
            "id": group.id,
            "name": group.name,
            "permissions": permissions,
        }

    @classmethod
    def list_roles(cls) -> list[dict]:
        groups = Group.objects.order_by("id").prefetch_related(
            Prefetch("permissions", queryset=cls.component_permission_queryset(), to_attr="component_permissions")
        )
        return [cls.serialize_role(group) for group in groups]

    @classmethod
    def get_role(cls, role_id: int) -> Group:
        try:
            return Group.objects.prefetch_related(
                Prefetch("permissions", queryset=cls.component_permission_queryset(), to_attr="component_permissions")
            ).get(pk=role_id)
        except Group.DoesNotExist as exc:
            raise NotFoundApiError(f"Role {role_id} not found") from exc

    @classmethod
    @transaction.atomic
    def create_role(cls, data: dict) -> dict:
        name = data["name"]
        if Group.objects.filter(name=name).exists():
            raise ConflictApiError("Role name already exists")
        group = Group.objects.create(name=name)
        permission_codes = data.get("permission_codes", [])
        group.permissions.set(PermissionService.permission_queryset_for_codes(permission_codes))
        invalidate_cache_groups(CACHE_GROUP_AUTH_PERMISSIONS, CACHE_GROUP_AUTH_ROLES)
        return cls.serialize_role(group)

    @classmethod
    @transaction.atomic
    def update_role(cls, role_id: int, data: dict) -> dict:
        group = cls.get_role(role_id)
        if "name" in data and data["name"] != group.name:
            if Group.objects.filter(name=data["name"]).exclude(pk=group.pk).exists():
                raise ConflictApiError("Role name already exists")
            group.name = data["name"]
            group.save(update_fields=["name"])
        if "permission_codes" in data:
            group.permissions.set(PermissionService.permission_queryset_for_codes(data["permission_codes"]))
        invalidate_cache_groups(CACHE_GROUP_AUTH_PERMISSIONS, CACHE_GROUP_AUTH_ROLES)
        return cls.serialize_role(group)

    @classmethod
    @transaction.atomic
    def delete_role(cls, role_id: int) -> dict:
        group = cls.get_role(role_id)
        if group.user_set.exists():
            raise ConflictApiError("Role is assigned to users")
        deleted_id = group.id
        group.delete()
        invalidate_cache_groups(CACHE_GROUP_AUTH_PERMISSIONS, CACHE_GROUP_AUTH_ROLES)
        return {"id": deleted_id}


class UserAdminService:
    @staticmethod
    def _user_model():
        return get_user_model()

    @classmethod
    def _groups_for_ids(cls, group_ids: list[int]):
        groups = list(Group.objects.filter(id__in=group_ids))
        found_ids = {group.id for group in groups}
        missing_ids = sorted(set(group_ids) - found_ids)
        if missing_ids:
            raise ValidationApiError(f"Unknown group ids: {', '.join(str(group_id) for group_id in missing_ids)}")
        return groups

    @classmethod
    def serialize_user(cls, user) -> dict:
        group_objects = getattr(user, "component_groups", None)
        if group_objects is None:
            group_objects = user.groups.order_by("id").prefetch_related(
                Prefetch(
                    "permissions",
                    queryset=RoleService.component_permission_queryset(),
                    to_attr="component_permissions",
                )
            )
        groups = [RoleService.serialize_role(group) for group in group_objects]

        direct_permission_objects = getattr(user, "component_user_permissions", None)
        if direct_permission_objects is None:
            direct_permission_objects = user.user_permissions.filter(
                content_type__app_label=PERMISSION_APP_LABEL,
                codename__in=COMPONENT_PERMISSION_CODES,
            )
        direct_permissions = sorted(permission.codename for permission in direct_permission_objects)
        effective_permissions = cls._effective_permission_codes(
            user,
            groups=groups,
            direct_permissions=direct_permissions,
        )
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "groups": groups,
            "direct_permissions": direct_permissions,
            "effective_permissions": effective_permissions,
        }

    @staticmethod
    def _effective_permission_codes(user, *, groups: list[dict], direct_permissions: list[str]) -> list[str]:
        if getattr(user, "is_superuser", False):
            return sorted(COMPONENT_PERMISSION_CODES)
        if not getattr(user, "is_active", True):
            return []
        group_permissions = {
            permission
            for group in groups
            for permission in group["permissions"]
        }
        return sorted(group_permissions | set(direct_permissions))

    @classmethod
    def list_users(cls) -> list[dict]:
        component_permissions = RoleService.component_permission_queryset()
        users = (
            cls._user_model()
            .objects.order_by("id")
            .prefetch_related(
                Prefetch(
                    "groups",
                    queryset=Group.objects.order_by("id").prefetch_related(
                        Prefetch("permissions", queryset=component_permissions, to_attr="component_permissions")
                    ),
                    to_attr="component_groups",
                ),
                Prefetch(
                    "user_permissions",
                    queryset=component_permissions,
                    to_attr="component_user_permissions",
                ),
            )
        )
        return [cls.serialize_user(user) for user in users]

    @classmethod
    def get_user(cls, user_id: int):
        try:
            return (
                cls._user_model()
                .objects.prefetch_related(
                    Prefetch(
                        "groups",
                        queryset=Group.objects.order_by("id").prefetch_related(
                            Prefetch(
                                "permissions",
                                queryset=RoleService.component_permission_queryset(),
                                to_attr="component_permissions",
                            )
                        ),
                        to_attr="component_groups",
                    ),
                    Prefetch(
                        "user_permissions",
                        queryset=RoleService.component_permission_queryset(),
                        to_attr="component_user_permissions",
                    ),
                )
                .get(pk=user_id)
            )
        except cls._user_model().DoesNotExist as exc:
            raise NotFoundApiError(f"User {user_id} not found") from exc

    @classmethod
    @transaction.atomic
    def create_user(cls, data: dict) -> dict:
        model = cls._user_model()
        if model.objects.filter(username=data["username"]).exists():
            raise ConflictApiError("Username already exists")

        user = model.objects.create_user(
            username=data["username"],
            password=data["password"],
            email=data.get("email", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            is_active=data.get("is_active", True),
            is_staff=data.get("is_staff", False),
        )
        if "group_ids" in data:
            user.groups.set(cls._groups_for_ids(data["group_ids"]))
        if "permission_codes" in data:
            user.user_permissions.set(PermissionService.permission_queryset_for_codes(data["permission_codes"]))
        invalidate_cache_groups(CACHE_GROUP_AUTH_PERMISSIONS, CACHE_GROUP_AUTH_ROLES)
        return cls.serialize_user(user)

    @classmethod
    @transaction.atomic
    def update_user(cls, user_id: int, data: dict) -> dict:
        user = cls.get_user(user_id)
        update_fields = []
        for field in ("email", "first_name", "last_name", "is_active", "is_staff"):
            if field in data:
                setattr(user, field, data[field])
                update_fields.append(field)
        if update_fields:
            user.save(update_fields=update_fields)
        if "group_ids" in data:
            user.groups.set(cls._groups_for_ids(data["group_ids"]))
        if "permission_codes" in data:
            user.user_permissions.set(PermissionService.permission_queryset_for_codes(data["permission_codes"]))
        if "group_ids" in data or "permission_codes" in data:
            invalidate_cache_groups(CACHE_GROUP_AUTH_PERMISSIONS, CACHE_GROUP_AUTH_ROLES)
        return cls.serialize_user(user)

    @classmethod
    @transaction.atomic
    def reset_password(cls, user_id: int, password: str) -> dict:
        user = cls.get_user(user_id)
        user.set_password(password)
        user.save(update_fields=["password"])
        return {"id": user.id, "password_reset": True}
