from django.conf import settings
from django.middleware.csrf import get_token
from rest_framework.permissions import AllowAny, IsAuthenticated

from accounts.permissions import SuperAdminPermission
from accounts.schemas import (
    AuthAdminUserSerializer,
    AuthUserSerializer,
    CsrfTokenSerializer,
    LoginSerializer,
    LogoutResultSerializer,
    PermissionGroupSerializer,
    RoleInputSerializer,
    RoleOutputSerializer,
    RoleUpdateSerializer,
    UserCreateSerializer,
    UserPasswordResetSerializer,
    UserUpdateSerializer,
)
from accounts.services import AuthTokenService, PermissionService, RoleService, UserAdminService
from common.responses import success_response
from common.views import ServiceAPIView


def set_auth_cookie(response, *, token: str, max_age: int):
    response.set_cookie(
        settings.AUTH_TOKEN_COOKIE_NAME,
        token,
        max_age=max_age,
        path=settings.AUTH_TOKEN_COOKIE_PATH,
        secure=settings.AUTH_TOKEN_COOKIE_SECURE,
        httponly=True,
        samesite=settings.AUTH_TOKEN_COOKIE_SAMESITE,
    )


def clear_auth_cookie(response):
    response.delete_cookie(
        settings.AUTH_TOKEN_COOKIE_NAME,
        path=settings.AUTH_TOKEN_COOKIE_PATH,
        samesite=settings.AUTH_TOKEN_COOKIE_SAMESITE,
    )


class CsrfTokenView(ServiceAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        output = CsrfTokenSerializer({"csrf_token": get_token(request)})
        return success_response(output.data)


class LoginView(ServiceAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = AuthTokenService.login(
            request=request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
            remember_me=serializer.validated_data["remember_me"],
        )
        output = AuthUserSerializer(result["user"])
        response = success_response(output.data)
        set_auth_cookie(response, token=result["token"], max_age=result["expires_in"])
        return response


class LogoutView(ServiceAPIView):
    def post(self, request):
        result = AuthTokenService.logout(getattr(request, "auth", None))
        output = LogoutResultSerializer(result)
        response = success_response(output.data)
        clear_auth_cookie(response)
        return response


class MeView(ServiceAPIView):
    def get(self, request):
        output = AuthUserSerializer(AuthTokenService.serialize_user(request.user))
        return success_response(output.data)


class PermissionCollectionView(ServiceAPIView):
    permission_classes = [IsAuthenticated, SuperAdminPermission]

    def get(self, request):
        PermissionService.sync_permissions()
        output = PermissionGroupSerializer(PermissionService.grouped_catalog(), many=True)
        return success_response({"items": output.data, "pagination": None})


class RoleCollectionView(ServiceAPIView):
    permission_classes = [IsAuthenticated, SuperAdminPermission]

    def get(self, request):
        output = RoleOutputSerializer(RoleService.list_roles(), many=True)
        return success_response({"items": output.data, "pagination": None})

    def post(self, request):
        serializer = RoleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = RoleService.create_role(serializer.validated_data)
        return success_response(RoleOutputSerializer(role).data, status_code=201)


class RoleDetailView(ServiceAPIView):
    permission_classes = [IsAuthenticated, SuperAdminPermission]

    def get(self, request, role_id: int):
        role = RoleService.serialize_role(RoleService.get_role(role_id))
        return success_response(RoleOutputSerializer(role).data)

    def patch(self, request, role_id: int):
        serializer = RoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = RoleService.update_role(role_id, serializer.validated_data)
        return success_response(RoleOutputSerializer(role).data)

    def delete(self, request, role_id: int):
        return success_response(RoleService.delete_role(role_id))


class UserCollectionView(ServiceAPIView):
    permission_classes = [IsAuthenticated, SuperAdminPermission]

    def get(self, request):
        output = AuthAdminUserSerializer(UserAdminService.list_users(), many=True)
        return success_response({"items": output.data, "pagination": None})

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserAdminService.create_user(serializer.validated_data)
        return success_response(AuthAdminUserSerializer(user).data, status_code=201)


class UserDetailView(ServiceAPIView):
    permission_classes = [IsAuthenticated, SuperAdminPermission]

    def get(self, request, user_id: int):
        user = UserAdminService.serialize_user(UserAdminService.get_user(user_id))
        return success_response(AuthAdminUserSerializer(user).data)

    def patch(self, request, user_id: int):
        serializer = UserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserAdminService.update_user(user_id, serializer.validated_data)
        return success_response(AuthAdminUserSerializer(user).data)


class UserPasswordView(ServiceAPIView):
    permission_classes = [IsAuthenticated, SuperAdminPermission]

    def post(self, request, user_id: int):
        serializer = UserPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return success_response(UserAdminService.reset_password(user_id, serializer.validated_data["password"]))
