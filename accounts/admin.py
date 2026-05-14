from django.contrib import admin

from accounts.models import AuthToken


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "issued_at", "expires_at", "revoked_at")
    list_filter = ("revoked_at", "expires_at")
    search_fields = ("user__username", "token_hash")
    readonly_fields = ("token_hash", "issued_at", "expires_at", "revoked_at")
