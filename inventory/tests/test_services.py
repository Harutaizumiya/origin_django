import hashlib
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, Mock, call
from unittest.mock import patch

from django.db import DatabaseError, IntegrityError
from django.test import SimpleTestCase, override_settings

from common.cache_utils import CACHE_GROUP_INVENTORY_READ, CACHE_GROUP_PRODUCT_CATEGORIES
from common.exceptions import ConflictApiError, NotFoundApiError
from inventory.models import Batch, InventoryAuditLog, Product
from inventory.expiry import calc_days_until_expiry, calc_expiry_progress, calc_expiry_status
from inventory.services import (
    AnalyticsService,
    BatchOperationService,
    BatchService,
    DashboardService,
    ProductService,
    QrCredentialService,
    QrScanService,
)


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

    @patch("inventory.services.invalidate_cache_groups")
    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.Product.objects.create")
    def test_create_product_refreshes_database_timestamps(self, mock_create, mock_atomic, mock_invalidate):
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
        mock_invalidate.assert_called_once_with(CACHE_GROUP_INVENTORY_READ, CACHE_GROUP_PRODUCT_CATEGORIES)

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

    @patch("inventory.services.InventoryAuditLog.objects.create")
    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.Product.objects.get")
    def test_delete_product_records_actor_and_snapshot_before_delete(self, mock_get, mock_atomic, mock_audit_create):
        mock_atomic.return_value.__enter__.return_value = None
        actor = Mock(id=123)
        product = Mock(
            id=7,
            barcode="123456",
            product_name="Milk",
            shelf_life_days=12,
            location="A-01",
            category="drink",
            unit="box",
            manufacturer="Factory",
            created_at=None,
            updated_at=None,
        )
        mock_get.return_value = product

        result = ProductService.delete_product(7, actor=actor)

        self.assertEqual(result, {"id": 7})
        mock_audit_create.assert_called_once()
        self.assertEqual(mock_audit_create.call_args.kwargs["resource_type"], InventoryAuditLog.RESOURCE_PRODUCT)
        self.assertEqual(mock_audit_create.call_args.kwargs["resource_id"], "7")
        self.assertEqual(mock_audit_create.call_args.kwargs["action"], InventoryAuditLog.ACTION_DELETE)
        self.assertIs(mock_audit_create.call_args.kwargs["actor"], actor)
        self.assertEqual(mock_audit_create.call_args.kwargs["snapshot"]["barcode"], "123456")
        product.delete.assert_called_once()


class BatchServiceTests(SimpleTestCase):
    @patch("inventory.services.QrCredentialService.issue_for_batch")
    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.Batch.objects.create")
    @patch("inventory.services.Product.objects.get")
    def test_create_batch_derives_expire_date_from_product_shelf_life(
        self, mock_product_get, mock_batch_create, mock_atomic, mock_issue_qr
    ):
        mock_atomic.return_value.__enter__.return_value = None
        mock_product_get.return_value = SimpleNamespace(id=1, shelf_life_days=30)
        batch = Mock(id=2)
        mock_batch_create.return_value = batch

        BatchService.create_batch(
            {
                "product_id": 1,
                "manufacture_date": date(2026, 4, 21),
                "status": "unopened",
                "remarks": None,
            }
        )

        payload = mock_batch_create.call_args.kwargs
        self.assertEqual(payload["expire_date"], date(2026, 5, 21))
        self.assertEqual(payload["product"].id, 1)
        self.assertEqual(payload["quantity"], Decimal("0.00"))
        mock_issue_qr.assert_called_once_with(batch)
        batch.refresh_from_db.assert_called_once_with(fields=["received_at"])

    @patch("inventory.services.Product.objects.get")
    def test_create_batch_raises_not_found_for_missing_product(self, mock_product_get):
        mock_product_get.side_effect = Product.DoesNotExist

        with self.assertRaises(NotFoundApiError):
            BatchService.create_batch(
                {
                    "product_id": 99,
                    "manufacture_date": date(2026, 4, 21),
                }
            )

    @patch("inventory.services.QrCredentialService.issue_for_batch")
    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchService._sync_batch_id_sequence")
    @patch("inventory.services.Batch.objects.create")
    @patch("inventory.services.Product.objects.get")
    def test_create_batch_retries_after_sequence_sync(
        self, mock_product_get, mock_batch_create, mock_sync_sequence, mock_atomic, mock_issue_qr
    ):
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
                "manufacture_date": date(2026, 4, 21),
            }
        )

        self.assertEqual(batch.id, 5)
        self.assertEqual(mock_batch_create.call_count, 2)
        mock_sync_sequence.assert_called_once()
        mock_issue_qr.assert_called_once_with(created_batch)
        created_batch.refresh_from_db.assert_called_once_with(fields=["received_at"])

    @patch("inventory.services.Batch.objects.select_related")
    def test_get_batch_translates_database_errors_to_conflict(self, mock_select_related):
        mock_select_related.return_value.get.side_effect = DatabaseError("db unavailable")

        with self.assertRaises(ConflictApiError):
            BatchService.get_batch(1)

    @patch("inventory.services.InventoryAuditLog.objects.create")
    @patch("inventory.services.transaction.atomic")
    @patch.object(BatchService, "get_batch")
    def test_delete_batch_records_actor_and_snapshot_before_delete(self, mock_get_batch, mock_atomic, mock_audit_create):
        mock_atomic.return_value.__enter__.return_value = None
        actor = Mock(id=123)
        batch = fake_batch(
            3,
            status="opened",
            quantity=Decimal("8.50"),
            manufacture_date=date(2026, 4, 1),
            expire_date=date(2026, 5, 1),
        )
        batch.delete = Mock()
        mock_get_batch.return_value = batch

        result = BatchService.delete_batch(3, actor=actor)

        self.assertEqual(result, {"id": 3})
        mock_audit_create.assert_called_once()
        self.assertEqual(mock_audit_create.call_args.kwargs["resource_type"], InventoryAuditLog.RESOURCE_BATCH)
        self.assertEqual(mock_audit_create.call_args.kwargs["resource_id"], "3")
        self.assertEqual(mock_audit_create.call_args.kwargs["action"], InventoryAuditLog.ACTION_DELETE)
        self.assertIs(mock_audit_create.call_args.kwargs["actor"], actor)
        self.assertEqual(mock_audit_create.call_args.kwargs["snapshot"]["batch_code"], "BATCH-003")
        self.assertEqual(mock_audit_create.call_args.kwargs["snapshot"]["quantity"], "8.50")
        batch.delete.assert_called_once()

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


class DashboardServiceTests(SimpleTestCase):
    @patch("inventory.services.timezone.localdate")
    @patch.object(DashboardService, "_active_batches")
    def test_get_overview_aggregates_active_inventory_risk_and_distribution(
        self,
        mock_active_batches,
        mock_localdate,
    ):
        mock_localdate.return_value = date(2026, 5, 13)
        mock_active_batches.return_value = [
            fake_batch(
                1,
                status="unopened",
                quantity=Decimal("10.00"),
                received_at=date(2026, 5, 1),
                manufacture_date=date(2026, 4, 25),
                expire_date=date(2026, 5, 15),
                category="drink",
            ),
            fake_batch(
                2,
                status="opened",
                quantity=Decimal("5.00"),
                received_at=date(2026, 4, 1),
                manufacture_date=date(2026, 4, 1),
                expire_date=date(2026, 5, 12),
                category="drink",
            ),
            fake_batch(
                3,
                status="opened",
                quantity=Decimal("2.00"),
                received_at=date(2026, 5, 10),
                manufacture_date=date(2026, 5, 1),
                expire_date=date(2026, 6, 30),
                category="snack",
            ),
        ]

        overview = DashboardService.get_overview()

        self.assertEqual(overview["current_inventory_quantity"], Decimal("17.00"))
        self.assertEqual(overview["near_expiry_batch_count"], 1)
        self.assertEqual(overview["expired_batch_count"], 1)
        self.assertEqual(overview["batch_health_rate"], 0.3333)
        self.assertEqual([batch.id for batch in overview["top_near_expiry_batches"]], [1])
        may_15 = next(item for item in overview["expiry_trend_30d"] if item["date"] == "2026-05-15")
        self.assertEqual(may_15["batch_count"], 1)
        self.assertEqual(may_15["quantity"], Decimal("10.00"))
        self.assertEqual(overview["category_inventory_distribution"][0]["category"], "drink")
        self.assertEqual(overview["category_inventory_distribution"][0]["quantity"], Decimal("15.00"))


class AnalyticsServiceTests(SimpleTestCase):
    @patch("inventory.services.timezone.localdate")
    @patch.object(AnalyticsService, "_effective_operations")
    @patch.object(AnalyticsService, "_active_batches")
    def test_get_summary_aggregates_range_operations_and_current_inventory(
        self,
        mock_active_batches,
        mock_effective_operations,
        mock_localdate,
    ):
        mock_localdate.return_value = date(2026, 5, 13)
        mock_active_batches.return_value = [
            fake_batch(
                1,
                status="unopened",
                quantity=Decimal("10.00"),
                received_at=datetime(2026, 5, 1, 9, 0, 0),
                manufacture_date=date(2026, 4, 25),
                expire_date=date(2026, 5, 15),
                category="drink",
            ),
            fake_batch(
                2,
                status="opened",
                quantity=Decimal("4.00"),
                received_at=datetime(2026, 4, 10, 9, 0, 0),
                manufacture_date=date(2026, 5, 1),
                expire_date=date(2026, 6, 1),
                category="snack",
            ),
        ]
        mock_effective_operations.return_value = [
            fake_operation("loss", Decimal("2.00"), datetime(2026, 5, 5, 10, 0, 0), category="drink"),
            fake_operation("deduct", Decimal("1.00"), datetime(2026, 4, 20, 10, 0, 0), category="drink"),
            fake_operation("add", Decimal("5.00"), datetime(2026, 4, 15, 10, 0, 0), category="snack"),
        ]

        summary = AnalyticsService.get_summary(range_value="3m")

        self.assertEqual(summary["period"], {"start": "2026-03-01", "end": "2026-05-13"})
        self.assertEqual(summary["inventory_change_count"], 3)
        self.assertEqual(summary["current_month_loss_quantity"], Decimal("2.00"))
        self.assertEqual(summary["average_stock_age_days"], 22.5)
        april = next(item for item in summary["monthly_inventory_loss_trend"] if item["month"] == "2026-04")
        may = next(item for item in summary["monthly_inventory_loss_trend"] if item["month"] == "2026-05")
        self.assertEqual(april["inventory_quantity"], Decimal("4.00"))
        self.assertEqual(april["loss_quantity"], Decimal("0"))
        self.assertEqual(may["inventory_quantity"], Decimal("10.00"))
        self.assertEqual(may["loss_quantity"], Decimal("2.00"))
        drink_summary = next(item for item in summary["category_operation_summary"] if item["category"] == "drink")
        self.assertEqual(drink_summary["inbound_quantity"], Decimal("0"))
        self.assertEqual(drink_summary["outbound_loss_quantity"], Decimal("3.00"))
        self.assertEqual(drink_summary["operation_count"], 2)
        self.assertEqual([batch.id for batch in summary["high_risk_inventory_ranking"]], [1, 2])


class QrCredentialServiceTests(SimpleTestCase):
    @override_settings(QR_TOKEN_PEPPER="pepper")
    def test_hash_token_uses_server_pepper(self):
        expected = hashlib.sha256("tokenpepper".encode("utf-8")).hexdigest()

        self.assertEqual(QrCredentialService.hash_token("token"), expected)

    @override_settings(QR_TOKEN_PEPPER="pepper")
    @patch("inventory.services.BatchQrCredential.objects.create")
    @patch("inventory.services.secrets.token_urlsafe")
    def test_issue_for_batch_stores_hash_and_returns_qr_code(self, mock_token_urlsafe, mock_create):
        mock_token_urlsafe.return_value = "plain-token"
        credential = Mock()
        mock_create.return_value = credential
        batch = SimpleNamespace(id=3, batch_code="BATCH-001")

        result_credential, qr_code = QrCredentialService.issue_for_batch(batch, created_by="tester")

        self.assertIs(result_credential, credential)
        self.assertEqual(qr_code, "OB1|BATCH-001|plain-token")
        self.assertEqual(mock_create.call_args.kwargs["batch"], batch)
        self.assertEqual(mock_create.call_args.kwargs["batch_code"], "BATCH-001")
        self.assertEqual(mock_create.call_args.kwargs["created_by"], "tester")
        self.assertEqual(
            mock_create.call_args.kwargs["token_hash"],
            hashlib.sha256("plain-tokenpepper".encode("utf-8")).hexdigest(),
        )
        self.assertNotIn("token", mock_create.call_args.kwargs)

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.QrCredentialService.issue_for_batch")
    @patch("inventory.services.Batch.objects.exclude")
    @patch("inventory.services.BatchQrCredential.objects.filter")
    def test_backfill_skips_batches_with_active_credentials(
        self, mock_filter, mock_exclude, mock_issue_for_batch, mock_atomic
    ):
        mock_atomic.return_value.__enter__.return_value = None
        active_batch_ids = Mock()
        mock_filter.return_value.values_list.return_value = active_batch_ids
        batch = SimpleNamespace(id=3, batch_code="BATCH-001")
        mock_exclude.return_value = [batch]

        count = QrCredentialService.backfill_missing_credentials()

        self.assertEqual(count, 1)
        mock_filter.assert_called_once_with(revoked_at__isnull=True)
        mock_filter.return_value.values_list.assert_called_once_with("batch_id", flat=True)
        mock_exclude.assert_called_once_with(id__in=active_batch_ids)
        mock_issue_for_batch.assert_called_once_with(batch, created_by="backfill")


class QrScanServiceTests(SimpleTestCase):
    @override_settings(QR_SCAN_NEAR_EXPIRY_DAYS=7)
    @patch("inventory.expiry.timezone.localdate")
    def test_result_for_batch_uses_server_date_and_near_expiry_threshold(self, mock_localdate):
        mock_localdate.return_value = date(2026, 5, 12)
        product = SimpleNamespace(product_name="Milk")

        valid = QrScanService._result_for_batch(
            SimpleNamespace(id=1, batch_code="BATCH-001", expire_date=date(2026, 5, 20), product=product)
        )
        near_expiry = QrScanService._result_for_batch(
            SimpleNamespace(id=2, batch_code="BATCH-002", expire_date=date(2026, 5, 19), product=product)
        )
        expired = QrScanService._result_for_batch(
            SimpleNamespace(id=3, batch_code="BATCH-003", expire_date=date(2026, 5, 11), product=product)
        )

        self.assertEqual(valid["status"], "valid")
        self.assertEqual(valid["remainingDays"], 8)
        self.assertEqual(near_expiry["status"], "near_expiry")
        self.assertEqual(near_expiry["remainingDays"], 7)
        self.assertEqual(expired["status"], "expired")
        self.assertEqual(expired["remainingDays"], -1)

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.QrScanAuditLog.objects.create")
    def test_scan_invalid_qr_records_audit_and_returns_invalid_result(self, mock_create_audit, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
        audit = Mock(id="scan_1")
        mock_create_audit.return_value = audit

        result = QrScanService.scan_qr(
            {"qr": "bad", "source": "mobile_camera"},
            {"ip_address": "127.0.0.1", "user_agent": "api-test", "scanner_user_id": 123},
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["message"], "二维码格式错误")
        self.assertEqual(mock_create_audit.call_args.kwargs["raw_qr"], "bad")
        self.assertEqual(mock_create_audit.call_args.kwargs["ip_address"], "127.0.0.1")
        self.assertEqual(mock_create_audit.call_args.kwargs["scanner_user_account_id"], 123)
        self.assertEqual(audit.result_status, "invalid")
        self.assertEqual(audit.failure_reason, "invalid_format")
        audit.save.assert_called_once()

    @override_settings(QR_TOKEN_PEPPER="pepper")
    @patch("inventory.services.BatchQrCredential.objects.filter")
    def test_scan_with_unknown_token_returns_invalid(self, mock_filter):
        mock_filter.return_value.order_by.return_value.first.return_value = None

        result = QrScanService._resolve_scan_result("OB1|BATCH-001|bad-token")

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["batchCode"], "BATCH-001")
        self.assertEqual(result["_failure_reason"], "token_mismatch")
        mock_filter.assert_called_once_with(
            batch_code="BATCH-001",
            token_hash=hashlib.sha256("bad-tokenpepper".encode("utf-8")).hexdigest(),
        )

    @patch("inventory.services.BatchQrCredential.objects.filter")
    def test_scan_with_revoked_credential_returns_revoked(self, mock_filter):
        credential = SimpleNamespace(batch_id=3, batch_code="BATCH-001", revoked_at=object())
        mock_filter.return_value.order_by.return_value.first.return_value = credential

        result = QrScanService._resolve_scan_result("OB1|BATCH-001|token")

        self.assertEqual(result["status"], "revoked")
        self.assertEqual(result["_batch_id"], 3)
        self.assertEqual(result["_failure_reason"], "credential_revoked")

    @patch("inventory.services.Batch.objects.select_related")
    @patch("inventory.services.BatchQrCredential.objects.filter")
    def test_scan_with_missing_batch_returns_not_found(self, mock_filter, mock_select_related):
        credential = SimpleNamespace(batch_id=3, batch_code="BATCH-001", revoked_at=None)
        mock_filter.return_value.order_by.return_value.first.return_value = credential
        mock_select_related.return_value.get.side_effect = Batch.DoesNotExist

        result = QrScanService._resolve_scan_result("OB1|BATCH-001|token")

        self.assertEqual(result["status"], "not_found")
        self.assertEqual(result["_batch_id"], 3)
        self.assertEqual(result["_failure_reason"], "batch_not_found")

    @patch("inventory.services.Batch.objects.select_related")
    @patch("inventory.services.BatchQrCredential.objects.filter")
    @patch("inventory.expiry.timezone.localdate")
    def test_scan_with_valid_credential_returns_batch_status(self, mock_localdate, mock_filter, mock_select_related):
        mock_localdate.return_value = date(2026, 5, 12)
        credential = SimpleNamespace(batch_id=3, batch_code="BATCH-001", revoked_at=None)
        batch = SimpleNamespace(
            id=3,
            batch_code="BATCH-001",
            expire_date=date(2026, 8, 11),
            product=SimpleNamespace(product_name="Milk"),
        )
        mock_filter.return_value.order_by.return_value.first.return_value = credential
        mock_select_related.return_value.get.return_value = batch

        result = QrScanService._resolve_scan_result("OB1|BATCH-001|token")

        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["productName"], "Milk")
        self.assertEqual(result["remainingDays"], 91)

    @patch("inventory.services.QrScanAuditLog.objects.create")
    @patch("inventory.services.QrScanAuditLog.objects.filter")
    def test_duplicate_client_scan_id_returns_existing_result_without_new_audit(self, mock_filter, mock_create_audit):
        audit = SimpleNamespace(
            id="scan_existing",
            batch_id=None,
            batch_code="BATCH-001",
            result_status="invalid",
            result_message="二维码无效",
        )
        mock_filter.return_value.order_by.return_value.first.return_value = audit

        result = QrScanService.scan_qr(
            {
                "qr": "OB1|BATCH-001|token",
                "source": "mobile_camera",
                "device_id": "device-001",
                "client_scan_id": "client-1",
            },
            {},
        )

        self.assertEqual(result["auditId"], "scan_existing")
        self.assertEqual(result["clientScanId"], "client-1")
        mock_create_audit.assert_not_called()


class BatchOperationServiceTests(SimpleTestCase):
    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchOperation.objects.create")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_create_add_operation_increases_quantity_and_writes_snapshot(
        self, mock_select_for_update, mock_operation_create, mock_atomic
    ):
        mock_atomic.return_value.__enter__.return_value = None
        batch = Mock(id=3, quantity=Decimal("8.50"), status="opened")
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
        self.assertEqual(batch.status, "opened")
        batch.save.assert_called_once_with(update_fields=["quantity"])
        mock_operation_create.assert_called_once_with(
            batch=batch,
            reversed_operation=None,
            operation_type="add",
            quantity=Decimal("2.00"),
            quantity_after=Decimal("10.50"),
            remarks="restock",
            operator=None,
        )
        operation.refresh_from_db.assert_called_once_with(fields=["created_at"])

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchOperation.objects.create")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_create_operation_records_operator(self, mock_select_for_update, mock_operation_create, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
        actor = Mock(id=123)
        batch = Mock(id=3, quantity=Decimal("8.50"), status="opened")
        mock_select_for_update.return_value.get.return_value = batch
        mock_operation_create.return_value = Mock()

        BatchOperationService.create_operation(
            3,
            {
                "operation_type": "loss",
                "quantity": Decimal("2.00"),
            },
            actor=actor,
        )

        self.assertIs(mock_operation_create.call_args.kwargs["operator"], actor)

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchOperation.objects.create")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_create_deduct_operation_decreases_quantity_and_writes_snapshot(
        self, mock_select_for_update, mock_operation_create, mock_atomic
    ):
        mock_atomic.return_value.__enter__.return_value = None
        batch = Mock(id=3, quantity=Decimal("8.50"), status="opened")
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
    @patch("inventory.services.BatchOperation.objects.create")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_create_operation_marks_batch_used_up_when_quantity_reaches_zero(
        self, mock_select_for_update, mock_operation_create, mock_atomic
    ):
        mock_atomic.return_value.__enter__.return_value = None
        batch = Mock(id=3, quantity=Decimal("2.00"), status="opened")
        mock_select_for_update.return_value.get.return_value = batch
        mock_operation_create.return_value = Mock()

        BatchOperationService.create_operation(
            3,
            {
                "operation_type": "deduct",
                "quantity": Decimal("2.00"),
            },
        )

        self.assertEqual(batch.quantity, Decimal("0"))
        self.assertEqual(batch.status, "used_up")
        batch.save.assert_called_once_with(update_fields=["quantity", "status"])

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchOperation.objects.create")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_create_add_operation_resets_used_up_batch_status_to_null(
        self, mock_select_for_update, mock_operation_create, mock_atomic
    ):
        mock_atomic.return_value.__enter__.return_value = None
        batch = Mock(id=3, quantity=Decimal("0"), status="used_up")
        mock_select_for_update.return_value.get.return_value = batch
        mock_operation_create.return_value = Mock()

        BatchOperationService.create_operation(
            3,
            {
                "operation_type": "add",
                "quantity": Decimal("2.00"),
            },
        )

        self.assertEqual(batch.quantity, Decimal("2.00"))
        self.assertIsNone(batch.status)
        batch.save.assert_called_once_with(update_fields=["quantity", "status"])

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_create_operation_rejects_insufficient_quantity(self, mock_select_for_update, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
        batch = Mock(id=3, quantity=Decimal("1.00"), status="opened")
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
        batch = Mock(id=3, quantity=None, status="opened")
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
        annotated_queryset = Mock()
        filtered_queryset = MagicMock()
        filtered_queryset.count.return_value = 1
        filtered_queryset.__getitem__ = Mock(return_value=["operation"])
        queryset.annotate.return_value = annotated_queryset
        annotated_queryset.order_by.return_value.filter.return_value = filtered_queryset
        reversal_queryset = Mock()
        mock_filter.side_effect = [reversal_queryset, queryset]

        operations, total = BatchOperationService.list_operations(
            batch_id=3,
            operation_type="loss",
            page=1,
            size=20,
        )

        self.assertEqual(operations, ["operation"])
        self.assertEqual(total, 1)
        self.assertEqual(
            mock_filter.call_args_list,
            [
                call(reversed_operation_id=ANY),
                call(batch_id=3),
            ],
        )
        queryset.annotate.assert_called_once()
        annotated_queryset.order_by.assert_called_once_with("-created_at", "-id")
        annotated_queryset.order_by.return_value.filter.assert_called_once_with(operation_type="loss")

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchOperation.objects")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_revert_add_operation_creates_deduct_reversal(self, mock_batch_select_for_update, mock_operation_objects, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
        original_operation = Mock(
            id=7,
            batch_id=3,
            operation_type="add",
            quantity=Decimal("2.00"),
            reversed_operation_id=None,
        )
        batch = Mock(id=3, quantity=Decimal("8.50"), status="opened")
        reversal_operation = Mock(id=8)
        mock_operation_objects.select_for_update.return_value.get.return_value = original_operation
        mock_operation_objects.filter.return_value.exists.return_value = False
        mock_operation_objects.create.return_value = reversal_operation
        mock_batch_select_for_update.return_value.get.return_value = batch

        result_operation, result_batch = BatchOperationService.revert_operation(
            batch_id=3,
            operation_id=7,
            data={"remarks": "undo mistake"},
        )

        self.assertIs(result_operation, reversal_operation)
        self.assertIs(result_batch, batch)
        self.assertEqual(batch.quantity, Decimal("6.50"))
        self.assertEqual(batch.status, "opened")
        batch.save.assert_called_once_with(update_fields=["quantity"])
        mock_operation_objects.create.assert_called_once_with(
            batch=batch,
            reversed_operation=original_operation,
            operation_type="deduct",
            quantity=Decimal("2.00"),
            quantity_after=Decimal("6.50"),
            remarks="undo mistake",
            operator=None,
        )
        reversal_operation.refresh_from_db.assert_called_once_with(fields=["created_at"])

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchOperation.objects")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_revert_deduct_operation_creates_add_reversal(self, mock_batch_select_for_update, mock_operation_objects, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
        original_operation = Mock(
            id=7,
            batch_id=3,
            operation_type="deduct",
            quantity=Decimal("2.00"),
            reversed_operation_id=None,
        )
        batch = Mock(id=3, quantity=Decimal("6.50"), status="opened")
        mock_operation_objects.select_for_update.return_value.get.return_value = original_operation
        mock_operation_objects.filter.return_value.exists.return_value = False
        mock_operation_objects.create.return_value = Mock()
        mock_batch_select_for_update.return_value.get.return_value = batch

        BatchOperationService.revert_operation(batch_id=3, operation_id=7, data={})

        self.assertEqual(batch.quantity, Decimal("8.50"))
        self.assertEqual(mock_operation_objects.create.call_args.kwargs["operation_type"], "add")
        self.assertEqual(mock_operation_objects.create.call_args.kwargs["quantity_after"], Decimal("8.50"))

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchOperation.objects")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_revert_operation_resets_used_up_batch_status_to_null(
        self, mock_batch_select_for_update, mock_operation_objects, mock_atomic
    ):
        mock_atomic.return_value.__enter__.return_value = None
        original_operation = Mock(
            id=7,
            batch_id=3,
            operation_type="deduct",
            quantity=Decimal("2.00"),
            reversed_operation_id=None,
        )
        batch = Mock(id=3, quantity=Decimal("0"), status="used_up")
        mock_operation_objects.select_for_update.return_value.get.return_value = original_operation
        mock_operation_objects.filter.return_value.exists.return_value = False
        mock_operation_objects.create.return_value = Mock()
        mock_batch_select_for_update.return_value.get.return_value = batch

        BatchOperationService.revert_operation(batch_id=3, operation_id=7, data={})

        self.assertEqual(batch.quantity, Decimal("2.00"))
        self.assertIsNone(batch.status)
        batch.save.assert_called_once_with(update_fields=["quantity", "status"])

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchOperation.objects")
    def test_revert_operation_rejects_already_reverted_operation(self, mock_operation_objects, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
        original_operation = Mock(id=7, reversed_operation_id=None)
        mock_operation_objects.select_for_update.return_value.get.return_value = original_operation
        mock_operation_objects.filter.return_value.exists.return_value = True

        with self.assertRaises(ConflictApiError):
            BatchOperationService.revert_operation(batch_id=3, operation_id=7, data={})

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchOperation.objects")
    def test_revert_operation_rejects_reversal_operation(self, mock_operation_objects, mock_atomic):
        mock_atomic.return_value.__enter__.return_value = None
        reversal_operation = Mock(id=8, reversed_operation_id=7)
        mock_operation_objects.select_for_update.return_value.get.return_value = reversal_operation

        with self.assertRaises(ConflictApiError):
            BatchOperationService.revert_operation(batch_id=3, operation_id=8, data={})

    @patch("inventory.services.transaction.atomic")
    @patch("inventory.services.BatchOperation.objects")
    @patch("inventory.services.Batch.objects.select_for_update")
    def test_revert_add_operation_rejects_insufficient_quantity(
        self, mock_batch_select_for_update, mock_operation_objects, mock_atomic
    ):
        mock_atomic.return_value.__enter__.return_value = None
        original_operation = Mock(
            id=7,
            batch_id=3,
            operation_type="add",
            quantity=Decimal("2.00"),
            reversed_operation_id=None,
        )
        batch = Mock(id=3, quantity=Decimal("1.00"), status="opened")
        mock_operation_objects.select_for_update.return_value.get.return_value = original_operation
        mock_operation_objects.filter.return_value.exists.return_value = False
        mock_batch_select_for_update.return_value.get.return_value = batch

        with self.assertRaises(ConflictApiError):
            BatchOperationService.revert_operation(batch_id=3, operation_id=7, data={})

        batch.save.assert_not_called()


class BackfillInventoryActorsCommandTests(SimpleTestCase):
    @patch("inventory.management.commands.backfill_inventory_actors.QrScanAuditLog.objects.filter")
    @patch("inventory.management.commands.backfill_inventory_actors.BatchOperation.objects.filter")
    @patch("inventory.management.commands.backfill_inventory_actors.get_user_model")
    def test_backfill_inventory_actors_updates_missing_actor_fields(
        self,
        mock_get_user_model,
        mock_batch_operation_filter,
        mock_qr_scan_filter,
    ):
        from inventory.management.commands.backfill_inventory_actors import Command

        user = Mock(username="admin")
        user_model = Mock()
        user_model.objects.get.return_value = user
        mock_get_user_model.return_value = user_model
        mock_batch_operation_filter.return_value.update.return_value = 2
        mock_qr_scan_filter.return_value.update.return_value = 3

        Command().handle(username="admin")

        user_model.objects.get.assert_called_once_with(username="admin")
        mock_batch_operation_filter.assert_called_once_with(operator__isnull=True)
        mock_batch_operation_filter.return_value.update.assert_called_once_with(operator=user)
        mock_qr_scan_filter.assert_called_once_with(scanner_user_account__isnull=True)
        mock_qr_scan_filter.return_value.update.assert_called_once_with(scanner_user_account=user)


def fake_batch(
    batch_id,
    *,
    status,
    manufacture_date,
    expire_date,
    quantity=Decimal("1.00"),
    received_at=None,
    shelf_life_days=20,
    category="drink",
    location="A-01",
):
    return SimpleNamespace(
        id=batch_id,
        product_id=1,
        batch_code=f"BATCH-{batch_id:03d}",
        quantity=quantity,
        received_at=received_at,
        status=status,
        remarks=None,
        manufacture_date=manufacture_date,
        expire_date=expire_date,
        product=SimpleNamespace(
            id=1,
            barcode="123456",
            product_name="Milk",
            unit="box",
            manufacturer="Factory",
            shelf_life_days=shelf_life_days,
            category=category,
            location=location,
        ),
    )


def fake_operation(operation_type, quantity, created_at, *, category="drink"):
    return SimpleNamespace(
        operation_type=operation_type,
        quantity=quantity,
        created_at=created_at,
        batch=SimpleNamespace(product=SimpleNamespace(category=category)),
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
