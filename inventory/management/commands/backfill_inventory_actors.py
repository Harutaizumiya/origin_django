from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from inventory.models import BatchOperation, QrScanAuditLog


class Command(BaseCommand):
    help = "Backfill inventory actor foreign keys for historical operation and QR audit records."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")

    def handle(self, *args, **options):
        username = options["username"]
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"User {username!r} does not exist") from exc

        operation_count = BatchOperation.objects.filter(operator__isnull=True).update(operator=user)
        scan_count = QrScanAuditLog.objects.filter(scanner_user_account__isnull=True).update(
            scanner_user_account=user,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled {operation_count} batch operations and {scan_count} QR scan audit logs to {username}."
            )
        )
