from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)
    remember_me = serializers.BooleanField(required=False, default=False)


class AuthUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    is_staff = serializers.BooleanField()
    is_superuser = serializers.BooleanField()
    permissions = serializers.ListField(child=serializers.CharField())


class LogoutResultSerializer(serializers.Serializer):
    revoked = serializers.BooleanField()


class CsrfTokenSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()


class PermissionSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    component = serializers.CharField()
    action = serializers.CharField()
    description = serializers.CharField()


class PermissionGroupSerializer(serializers.Serializer):
    component = serializers.CharField()
    permissions = PermissionSerializer(many=True)


class RoleInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    permission_codes = serializers.ListField(child=serializers.CharField(), required=False)


class RoleUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    permission_codes = serializers.ListField(child=serializers.CharField(), required=False)


class RoleOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    permissions = serializers.ListField(child=serializers.CharField())


class AuthAdminUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    is_active = serializers.BooleanField()
    is_staff = serializers.BooleanField()
    is_superuser = serializers.BooleanField()
    groups = RoleOutputSerializer(many=True)
    direct_permissions = serializers.ListField(child=serializers.CharField())
    effective_permissions = serializers.ListField(child=serializers.CharField())


class UserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(trim_whitespace=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)
    group_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    permission_codes = serializers.ListField(child=serializers.CharField(), required=False)


class UserUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)
    group_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    permission_codes = serializers.ListField(child=serializers.CharField(), required=False)


class UserPasswordResetSerializer(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False)
