from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

from django.db import IntegrityError
from django.test import SimpleTestCase

from common.exceptions import NotFoundApiError
from inventory.models import Product
from inventory.services import BatchService, ProductService


class ProductServiceTests(SimpleTestCase):
    @patch("inventory.services.Product.objects.create")
    def test_create_product_refreshes_database_timestamps(self, mock_create):
        product = Mock()
        mock_create.return_value = product

        result = ProductService.create_product(
            {
                "barcode": "123456",
                "product_name": "Milk",
                "shelf_life_days": 7,
                "manufacturer": "Factory",
            }
        )

        self.assertIs(result, product)
        product.refresh_from_db.assert_called_once_with(fields=["created_at", "updated_at"])

    @patch("inventory.services.Product.objects.get")
    def test_update_product_refreshes_updated_at_after_save(self, mock_get):
        product = Mock()
        mock_get.return_value = product

        result = ProductService.update_product(1, {"product_name": "New Name"})

        self.assertIs(result, product)
        product.save.assert_called_once_with(update_fields=["product_name"])
        product.refresh_from_db.assert_called_once_with(fields=["updated_at"])


class BatchServiceTests(SimpleTestCase):
    @patch("inventory.services.Batch.objects.create")
    @patch("inventory.services.Product.objects.get")
    def test_create_batch_derives_expire_date_from_product_shelf_life(self, mock_product_get, mock_batch_create):
        mock_product_get.return_value = SimpleNamespace(id=1, shelf_life_days=30)
        batch = Mock(id=2)
        mock_batch_create.return_value = batch

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
        self.assertEqual(payload["expire_date"], date(2026, 5, 21))
        self.assertEqual(payload["product"].id, 1)
        batch.refresh_from_db.assert_called_once_with(fields=["received_at"])

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
        created_batch = Mock(id=5)
        mock_batch_create.side_effect = [
            IntegrityError('duplicate key value violates unique constraint "batches_pkey"'),
            created_batch,
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
        created_batch.refresh_from_db.assert_called_once_with(fields=["received_at"])
