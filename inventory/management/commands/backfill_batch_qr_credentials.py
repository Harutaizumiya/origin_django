from django.core.management.base import BaseCommand

from inventory.services import QrCredentialService


class Command(BaseCommand):
    help = "Backfill QR credentials for batches that do not have an active credential."

    def handle(self, *args, **options):
        count = QrCredentialService.backfill_missing_credentials(created_by="management_command")
        self.stdout.write(self.style.SUCCESS(f"Backfilled {count} batch QR credentials."))
