from django.contrib import admin

from inventory.models import InventoryAuditLog


@admin.register(InventoryAuditLog)
class InventoryAuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "resource_type", "resource_id", "action", "actor", "created_at")
    list_filter = ("resource_type", "action", "created_at")
    search_fields = ("resource_id", "actor__username")
    readonly_fields = ("resource_type", "resource_id", "action", "actor", "snapshot", "created_at")
