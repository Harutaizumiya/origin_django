from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.db import IntegrityError
from django.test import SimpleTestCase
from django.utils import timezone

from common.exceptions import NotFoundApiError
from inventory.models import Product
from inventory.services import BatchService


class BatchServiceTests(SimpleTestCase):
    @patch("inventory.services.Batch.objects.create")
    @patch("inventory.services.Product.objects.get")
    def test_create_batch_derives_expire_date_from_product_shelf_life(self, mock_product_get, mock_batch_create):
        mock_product_get.return_value = SimpleNamespace(id=1, shelf_life_days=30)
        mock_batch_create.return_value = SimpleNamespace(id=2)

        BatchService.create_batch(
            {
                "product_id": 1,
                "quantity": "5.00",
                "manufacture_date": date(2026, 4, 21),
                "status": "unopened",
                "remarks": None,
            }
        )

        payload = mock_batch_create.call_args.kwargs
        self.assertEqual(payload["expire_date"], timezone.make_aware(datetime(2026, 5, 21, 0, 0)))
        self.assertEqual(payload["product"].id, 1)

    @patch("inventory.services.Product.objects.get")
    def test_create_batch_raises_not_found_for_missing_product(self, mock_product_get):
        mock_product_get.side_effect = Product.DoesNotExist

        with self.assertRaises(NotFoundApiError):
            BatchService.create_batch(
                {
                    "product_id": 99,
                    "quantity": "5.00",
                    "manufacture_date": date(2026, 4, 21),
                }
            )

    @patch("inventory.services.BatchService._sync_batch_id_sequence")
    @patch("inventory.services.Batch.objects.create")
    @patch("inventory.services.Product.objects.get")
    def test_create_batch_retries_after_sequence_sync(self, mock_product_get, mock_batch_create, mock_sync_sequence):
        mock_product_get.return_value = SimpleNamespace(id=1, shelf_life_days=30)
        mock_batch_create.side_effect = [
            IntegrityError('duplicate key value violates unique constraint "batches_pkey"'),
            SimpleNamespace(id=5),
        ]

        batch = BatchService.create_batch(
            {
                "product_id": 1,
                "quantity": "5.00",
                "manufacture_date": date(2026, 4, 21),
            }
        )

        self.assertEqual(batch.id, 5)
        self.assertEqual(mock_batch_create.call_count, 2)
        mock_sync_sequence.assert_called_once()
