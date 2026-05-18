from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def sync_component_permissions(sender, app_config, **kwargs):
    if app_config.label != "accounts":
        return

    from accounts.services import PermissionService

    PermissionService.sync_permissions()
