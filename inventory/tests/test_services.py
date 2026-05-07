from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from unittest.mock import patch

from django.db import DatabaseError, IntegrityError
from django.test import SimpleTestCase

from common.exceptions import ConflictApiError, NotFoundApiError
from inventory.models import Batch, Product
from inventory.expiry import calc_days_until_expiry, calc_expiry_progress, calc_expiry_status
from inventory.services import BatchOperationService, BatchService, ProductService


class ExpiryCalculationTests(SimpleTestCase):
    def test_days_until_expiry_handles_past_today_future_and_null(self):
        today = date(2026, 4, 27)

        self.assertEqual(calc_days_until_expiry(date(2026, 4, 26), today), -1)
        self.assertEqual(calc_days_until_expiry(date(2026, 4, 27), today), 0)
        self.assertEqual(calc_days_until_expiry(date(2026, 5, 7), today), 10)
        self.assertIsNone(calc_days_until_expiry(None, today))

    def test_expiry_progress_uses_relative_lifecycle(self):
        today = date(2026, 4, 27)

        thirty_day_progress = calc_expiry_progress(date(2026, 4, 12), 30, today)
        yearly_progress = calc_expiry_progress(date(2025, 10, 27), 365, today)

        self.assertAlmostEqual(thirty_day_progress, 0.5)
        self.assertAlmostEqual(yearly_progress, 0.4986)

    def test_expiry_status_thresholds(self):
        today = date(2026, 4, 27)

        self.assertEqual(calc_expiry_status(date(2026, 4, 12), 20, today), "normal")
        self.assertEqual(calc_expiry_status(date(2026, 4, 11), 20, today), "warning")
        self.assertEqual(calc_expiry_status(date(2026, 4, 8), 20, today), "critical")
        self.assertEqual(calc_expiry_status(date(2026, 4, 6), 20, today), "expired")

    def test_zero_shelf_life_is_expired(self):
        today = date(2026, 4, 27)

        self.assertEqual(calc_expiry_progress(date(2026, 4, 27), 0, today), 1.01)
        self.assertEqual(calc_expiry_status(date(2026, 4, 27), 0, today), "expired")


class ProductServiceTests(SimpleTestCase):
    @patch("inventory.services.Product.objects.all")
    def test_list_products_translates_database_errors_to_conflict(self, mock_all):
        mock_all.side_effect = DatabaseError("db unavailable")

        with self.assertRaises(ConflictApiError):
            ProductService.list_products(search=None, page=1, size=20)

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.Product.objects.create")
    def test_create_product_refreshes_database_timestamps(self, mock_create, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
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

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.Product.objects.create")
    def test_create_product_translates_database_errors_to_conflict(self, mock_create, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
        mock_create.side_effect = DatabaseError("db unavailable")

        with self.assertRaises(ConflictApiError):
            ProductService.create_product(
                {
                    "barcode": "123456",
                    "product_name": "Milk",
                    "shelf_life_days": 7,
                    "manufacturer": "Factory",
                }
            )

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.Product.objects.get")
    def test_update_product_refreshes_updated_at_after_save(self, mock_get, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
        product = Mock()
        mock_get.return_value = product

        result = ProductService.update_product(1, {"product_name": "New Name"})

        self.assertIs(result, product)
        product.save.assert_called_once_with(update_fields=["product_name"])
        product.refresh_from_db.assert_called_once_with(fields=["updated_at"])

    @patch("inventory.services.Product.objects.get")
    def test_get_product_translates_database_errors_to_conflict(self, mock_get):
        mock_get.side_effect = DatabaseError("db unavailable")

        with self.assertRaises(ConflictApiError):
            ProductService.get_product(1)


class BatchServiceTests(SimpleTestCase):
    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.Batch.objects.create")
    @patch("inventory.services.Product.objects.get")
    def test_create_batch_derives_expire_date_from_product_shelf_life(self, mock_product_get, mock_batch_create, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
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

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchService._sync_batch_id_sequence")
    @patch("inventory.services.Batch.objects.create")
    @patch("inventory.services.Product.objects.get")
    def test_create_batch_retries_after_sequence_sync(self, mock_product_get, mock_batch_create, mock_sync_sequence, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
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

    @patch("inventory.services.Batch.objects.select_related")
    def test_get_batch_translates_database_errors_to_conflict(self, mock_select_related):
        mock_select_related.return_value.get.side_effect = DatabaseError("db unavailable")

        with self.assertRaises(ConflictApiError):
            BatchService.get_batch(1)

    @patch("inventory.services.timezone.localdate")
    @patch("inventory.services.Batch.objects")
    def test_list_expiry_alerts_returns_default_unopened_lifecycle_alerts(self, mock_batch_objects, mock_localdate):
        mock_localdate.return_value = date(2026, 4, 27)
        mock_batch_objects.select_related.return_value = FakeBatchQuerySet(
            [
                fake_batch(1, status="unopened", manufacture_date=date(2026, 4, 8), expire_date=date(2026, 4, 28)),
                fake_batch(2, status="opened", manufacture_date=date(2026, 4, 8), expire_date=date(2026, 4, 28)),
                fake_batch(3, status="unopened", manufacture_date=date(2026, 4, 25), expire_date=date(2026, 5, 1)),
            ]
        )

        batches, total = BatchService.list_expiry_alerts(
            product_id=None,
            status="unopened",
            category=None,
            location=None,
            expiry_status=None,
            days_lte=30,
            include_expired=True,
            page=1,
            size=20,
        )

        self.assertEqual(total, 1)
        self.assertEqual([batch.id for batch in batches], [1])

    @patch("inventory.services.timezone.localdate")
    @patch("inventory.services.Batch.objects")
    def test_list_expiry_alerts_can_exclude_expired_batches(self, mock_batch_objects, mock_localdate):
        mock_localdate.return_value = date(2026, 4, 27)
        mock_batch_objects.select_related.return_value = FakeBatchQuerySet(
            [
                fake_batch(1, status="unopened", manufacture_date=date(2026, 4, 1), expire_date=date(2026, 4, 26)),
                fake_batch(2, status="unopened", manufacture_date=date(2026, 4, 8), expire_date=date(2026, 4, 28)),
            ]
        )

        batches, total = BatchService.list_expiry_alerts(
            product_id=None,
            status="unopened",
            category=None,
            location=None,
            expiry_status=None,
            days_lte=30,
            include_expired=False,
            page=1,
            size=20,
        )

        self.assertEqual(total, 1)
        self.assertEqual([batch.id for batch in batches], [2])

    @patch("inventory.services.timezone.localdate")
    @patch("inventory.services.Batch.objects")
    def test_list_expiry_alerts_applies_days_window(self, mock_batch_objects, mock_localdate):
        mock_localdate.return_value = date(2026, 4, 27)
        mock_batch_objects.select_related.return_value = FakeBatchQuerySet(
            [
                fake_batch(1, status="unopened", manufacture_date=date(2026, 4, 8), expire_date=date(2026, 4, 30)),
                fake_batch(2, status="unopened", manufacture_date=date(2026, 4, 8), expire_date=date(2026, 5, 1)),
            ]
        )

        batches, total = BatchService.list_expiry_alerts(
            product_id=None,
            status="unopened",
            category=None,
            location=None,
            expiry_status=None,
            days_lte=3,
            include_expired=True,
            page=1,
            size=20,
        )

        self.assertEqual(total, 1)
        self.assertEqual([batch.id for batch in batches], [1])


class BatchOperationServiceTests(SimpleTestCase):
    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchOperation.objects.create")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_create_add_operation_increases_quantity_and_writes_snapshot(
        self, mock_select_for_update, mock_operation_create, mock_atomic
    ):
        mock_atomic.return_value.__enter__.return_value = None
        batch = Mock(id=3, quantity=Decimal("8.50"))
        mock_select_for_update.return_value.get.return_value = batch
        operation = Mock(id=9)
        mock_operation_create.return_value = operation

        result_operation, result_batch = BatchOperationService.create_operation(
            3,
            {
                "operation_type": "add",
                "quantity": Decimal("2.00"),
                "remarks": "restock",
            },
        )

        self.assertIs(result_operation, operation)
        self.assertIs(result_batch, batch)
        self.assertEqual(batch.quantity, Decimal("10.50"))
        batch.save.assert_called_once_with(update_fields=["quantity"])
        mock_operation_create.assert_called_once_with(
            batch=batch,
            operation_type="add",
            quantity=Decimal("2.00"),
            quantity_after=Decimal("10.50"),
            remarks="restock",
        )
        operation.refresh_from_db.assert_called_once_with(fields=["created_at"])

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchOperation.objects.create")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_create_deduct_operation_decreases_quantity_and_writes_snapshot(
        self, mock_select_for_update, mock_operation_create, mock_atomic
    ):
        mock_atomic.return_value.__enter__.return_value = None
        batch = Mock(id=3, quantity=Decimal("8.50"))
        mock_select_for_update.return_value.get.return_value = batch
        mock_operation_create.return_value = Mock()

        BatchOperationService.create_operation(
            3,
            {
                "operation_type": "deduct",
                "quantity": Decimal("2.00"),
            },
        )

        self.assertEqual(batch.quantity, Decimal("6.50"))
        self.assertEqual(mock_operation_create.call_args.kwargs["quantity_after"], Decimal("6.50"))

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_create_operation_rejects_insufficient_quantity(self, mock_select_for_update, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
        batch = Mock(id=3, quantity=Decimal("1.00"))
        mock_select_for_update.return_value.get.return_value = batch

        with self.assertRaises(ConflictApiError):
            BatchOperationService.create_operation(
                3,
                {
                    "operation_type": "loss",
                    "quantity": Decimal("2.00"),
                },
            )

        batch.save.assert_not_called()

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_create_operation_rejects_null_batch_quantity(self, mock_select_for_update, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
        batch = Mock(id=3, quantity=None)
        mock_select_for_update.return_value.get.return_value = batch

        with self.assertRaises(ConflictApiError):
            BatchOperationService.create_operation(
                3,
                {
                    "operation_type": "add",
                    "quantity": Decimal("2.00"),
                },
            )

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_create_operation_raises_not_found_for_missing_batch(self, mock_select_for_update, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
        mock_select_for_update.return_value.get.side_effect = Batch.DoesNotExist

        with self.assertRaises(NotFoundApiError):
            BatchOperationService.create_operation(
                99,
                {
                    "operation_type": "add",
                    "quantity": Decimal("2.00"),
                },
            )

    @patch("inventory.services.BatchOperation.objects.filter")
    @patch("inventory.services.Batch.objects.only")
    def test_list_operations_filters_and_orders_by_batch_history(self, mock_only, mock_filter):
        mock_only.return_value.get.return_value = Mock(id=3)
        queryset = Mock()
        filtered_queryset = MagicMock()
        filtered_queryset.count.return_value = 1
        filtered_queryset.__getitem__ = Mock(return_value=["operation"])
        queryset.order_by.return_value.filter.return_value = filtered_queryset
        mock_filter.return_value = queryset

        operations, total = BatchOperationService.list_operations(
            batch_id=3,
            operation_type="loss",
            page=1,
            size=20,
        )

        self.assertEqual(operations, ["operation"])
        self.assertEqual(total, 1)
        mock_filter.assert_called_once_with(batch_id=3)
        queryset.order_by.assert_called_once_with("-created_at", "-id")
        queryset.order_by.return_value.filter.assert_called_once_with(operation_type="loss")


def fake_batch(
    batch_id,
    *,
    status,
    manufacture_date,
    expire_date,
    shelf_life_days=20,
    category="drink",
    location="A-01",
):
    return SimpleNamespace(
        id=batch_id,
        product_id=1,
        status=status,
        manufacture_date=manufacture_date,
        expire_date=expire_date,
        product=SimpleNamespace(shelf_life_days=shelf_life_days, category=category, location=location),
    )


class FakeBatchQuerySet:
    def __init__(self, batches):
        self.batches = list(batches)

    def exclude(self, **kwargs):
        batches = self.batches
        if kwargs.get("expire_date__isnull") is True:
            batches = [batch for batch in batches if batch.expire_date is not None]
        return FakeBatchQuerySet(batches)

    def filter(self, **kwargs):
        batches = self.batches
        for key, value in kwargs.items():
            if key == "product_id":
                batches = [batch for batch in batches if batch.product_id == value]
            elif key == "status":
                batches = [batch for batch in batches if batch.status == value]
            elif key == "product__category":
                batches = [batch for batch in batches if batch.product.category == value]
            elif key == "product__location":
                batches = [batch for batch in batches if batch.product.location == value]
            elif key == "expire_date__lte":
                batches = [batch for batch in batches if batch.expire_date <= value]
            elif key == "expire_date__gte":
                batches = [batch for batch in batches if batch.expire_date >= value]
        return FakeBatchQuerySet(batches)

    def __iter__(self):
        return iter(self.batches)
