from django.urls import path

from accounts.views import (
    LoginView,
    LogoutView,
    MeView,
    PermissionCollectionView,
    RoleCollectionView,
    RoleDetailView,
    UserCollectionView,
    UserDetailView,
    UserPasswordView,
)

urlpatterns = [
    path("login", LoginView.as_view(), name="auth-login"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
    path("me", MeView.as_view(), name="auth-me"),
    path("permissions", PermissionCollectionView.as_view(), name="auth-permissions"),
    path("roles", RoleCollectionView.as_view(), name="auth-roles"),
    path("roles/<int:role_id>", RoleDetailView.as_view(), name="auth-role-detail"),
    path("users", UserCollectionView.as_view(), name="auth-users"),
    path("users/<int:user_id>", UserDetailView.as_view(), name="auth-user-detail"),
    path("users/<int:user_id>/password", UserPasswordView.as_view(), name="auth-user-password"),
]
