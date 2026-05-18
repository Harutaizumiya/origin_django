from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from common.exceptions import ConflictApiError, NotFoundApiError


class InventoryApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User(id=123, username="api-test")
        self.client.force_authenticate(user=self.user)

    def test_homepage_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Origin Django")

    @patch("inventory.views.DashboardService.get_overview")
    def test_dashboard_overview_returns_standard_shape(self, mock_get_overview):
        mock_get_overview.return_value = {
            "current_inventory_quantity": Decimal("18.50"),
            "near_expiry_batch_count": 1,
            "expired_batch_count": 0,
            "batch_health_rate": 0.5,
            "expiry_trend_30d": [{"date": "2026-05-13", "batch_count": 1, "quantity": Decimal("8.50")}],
            "category_inventory_distribution": [
                {"category": "drink", "batch_count": 2, "quantity": Decimal("18.50"), "ratio": 1.0}
            ],
            "top_near_expiry_batches": [],
        }

        response = self.client.get("/api/dashboard/overview")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["current_inventory_quantity"], "18.50")
        self.assertEqual(response.json()["data"]["near_expiry_batch_count"], 1)
        self.assertEqual(response.json()["data"]["expiry_trend_30d"][0]["quantity"], "8.50")
        mock_get_overview.assert_called_once_with()

    @patch("inventory.views.AnalyticsService.get_summary")
    def test_analytics_summary_returns_standard_shape(self, mock_get_summary):
        mock_get_summary.return_value = {
            "range": "6m",
            "period": {"start": "2025-12-01", "end": "2026-05-13"},
            "inventory_change_count": 3,
            "current_month_loss_quantity": Decimal("2.00"),
            "average_stock_age_days": 12.5,
            "monthly_inventory_loss_trend": [
                {
                    "month": "2026-05",
                    "inventory_quantity": Decimal("18.50"),
                    "loss_quantity": Decimal("2.00"),
                }
            ],
            "category_operation_summary": [
                {
                    "category": "drink",
                    "inbound_quantity": Decimal("5.00"),
                    "outbound_loss_quantity": Decimal("2.00"),
                    "operation_count": 3,
                }
            ],
            "high_risk_inventory_ranking": [],
        }

        response = self.client.get("/api/analytics/summary", {"range": "6m"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["inventory_change_count"], 3)
        self.assertEqual(response.json()["data"]["current_month_loss_quantity"], "2.00")
        mock_get_summary.assert_called_once_with(range_value="6m")

    def test_analytics_summary_rejects_invalid_range(self):
        response = self.client.get("/api/analytics/summary", {"range": "2y"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"code": 4001, "message": "validation_error", "data": None})

    @patch("inventory.views.ProductService.list_products")
    def test_list_products_returns_standard_shape(self, mock_list_products):
        mock_list_products.return_value = ([], 0)

        response = self.client.get("/api/products", {"page": 1, "size": 20})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "code": 0,
                "message": "success",
                "data": {
                    "items": [],
                    "pagination": {"page": 1, "size": 20, "total": 0},
                },
            },
        )

    @patch("inventory.views.ProductService.get_product")
    def test_get_product_detail_returns_standard_shape(self, mock_get_product):
        mock_get_product.return_value = {
            "id": 1,
            "barcode": "123456",
            "product_name": "Milk",
            "shelf_life_days": 12,
            "location": "A-01",
            "category": "drink",
            "unit": "box",
            "manufacturer": "Factory",
            "created_at": None,
            "updated_at": None,
        }

        response = self.client.get("/api/products/1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": 1,
                    "barcode": "123456",
                    "product_name": "Milk",
                    "shelf_life_days": 12,
                    "location": "A-01",
                    "category": "drink",
                    "unit": "box",
                    "manufacturer": "Factory",
                    "created_at": None,
                    "updated_at": None,
                },
            },
        )

    @patch("inventory.views.ProductService.get_product_by_barcode")
    def test_get_product_by_barcode_returns_standard_shape(self, mock_get_product_by_barcode):
        mock_get_product_by_barcode.return_value = {
            "id": 1,
            "barcode": "123456",
            "product_name": "Milk",
            "shelf_life_days": 12,
            "location": "A-01",
            "category": "drink",
            "unit": "box",
            "manufacturer": "Factory",
            "created_at": None,
            "updated_at": None,
        }

        response = self.client.get("/api/products/barcode/123456")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": 1,
                    "barcode": "123456",
                    "product_name": "Milk",
                    "shelf_life_days": 12,
                    "location": "A-01",
                    "category": "drink",
                    "unit": "box",
                    "manufacturer": "Factory",
                    "created_at": None,
                    "updated_at": None,
                },
            },
        )

    @patch("inventory.views.ProductService.create_product")
    def test_create_product_translates_conflict_error(self, mock_create_product):
        mock_create_product.side_effect = ConflictApiError("Barcode already exists")

        response = self.client.post(
            "/api/products",
            {
                "barcode": "123456",
                "product_name": "Milk",
                "shelf_life_days": 12,
                "manufacturer": "Factory",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"code": 4091, "message": "conflict", "data": None})
        mock_create_product.assert_called_once()
        self.assertIs(mock_create_product.call_args.kwargs["actor"], self.user)

    @patch("inventory.views.ProductService.update_product")
    def test_patch_product_returns_not_found_shape(self, mock_update_product):
        mock_update_product.side_effect = NotFoundApiError("Product 99 not found")

        response = self.client.patch("/api/products/99", {"product_name": "New"}, format="json")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"code": 4041, "message": "not_found", "data": None})
        mock_update_product.assert_called_once_with(99, {"product_name": "New"}, actor=self.user)

    @patch("inventory.views.ProductService.delete_product")
    def test_delete_product_returns_success_payload(self, mock_delete_product):
        mock_delete_product.return_value = {"id": 7}

        response = self.client.delete("/api/products/7")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"code": 0, "message": "success", "data": {"id": 7}})
        mock_delete_product.assert_called_once_with(7, actor=self.user)

    @patch("inventory.views.ProductService.list_categories")
    def test_list_categories_returns_data_array(self, mock_list_categories):
        mock_list_categories.return_value = ["drink", "snack"]

        response = self.client.get("/api/products/categories")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "code": 0,
                "message": "success",
                "data": {
                    "items": ["drink", "snack"],
                    "pagination": None,
                },
            },
        )

    @patch("inventory.views.BatchService.list_batches")
    def test_list_batches_returns_standard_shape(self, mock_list_batches):
        mock_list_batches.return_value = ([], 0)

        response = self.client.get("/api/batches", {"page": 1, "size": 20})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "code": 0,
                "message": "success",
                "data": {
                    "items": [],
                    "pagination": {"page": 1, "size": 20, "total": 0},
                },
            },
        )

    @patch("inventory.expiry.timezone.localdate")
    @patch("inventory.views.BatchService.list_batches")
    def test_list_batches_includes_expiry_fields(self, mock_list_batches, mock_localdate):
        mock_localdate.return_value = date(2026, 4, 27)
        mock_list_batches.return_value = (
            [
                SimpleNamespace(
                    id=3,
                    product=SimpleNamespace(
                        id=1,
                        barcode="123456",
                        product_name="Milk",
                        unit="box",
                        manufacturer="Factory",
                        shelf_life_days=20,
                    ),
                    batch_code="BATCH-001",
                    quantity="8.50",
                    received_at=None,
                    manufacture_date=date(2026, 4, 11),
                    expire_date=date(2026, 5, 1),
                    status="unopened",
                    remarks="qa batch",
                )
            ],
            1,
        )

        response = self.client.get("/api/batches", {"page": 1, "size": 20})

        self.assertEqual(response.status_code, 200)
        item = response.json()["data"]["items"][0]
        self.assertEqual(item["days_until_expiry"], 4)
        self.assertEqual(item["expiry_progress"], 0.8)
        self.assertEqual(item["expiry_status"], "warning")

    @patch("inventory.views.BatchService.list_batches")
    def test_get_product_batches_returns_standard_shape(self, mock_list_batches):
        mock_list_batches.return_value = ([], 0)

        response = self.client.get("/api/products/1/batches", {"page": 1, "size": 20})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "code": 0,
                "message": "success",
                "data": {
                    "items": [],
                    "pagination": {"page": 1, "size": 20, "total": 0},
                },
            },
        )
        mock_list_batches.assert_called_once_with(product_id=1, status=None, expired_only=False, page=1, size=20)

    @patch("inventory.expiry.timezone.localdate")
    @patch("inventory.views.BatchService.get_batch")
    def test_get_batch_detail_returns_standard_shape(self, mock_get_batch, mock_localdate):
        mock_localdate.return_value = date(2026, 4, 27)
        mock_get_batch.return_value = {
            "id": 3,
            "product_id": 1,
            "batch_code": "BATCH-001",
            "quantity": "8.50",
            "received_at": None,
            "manufacture_date": "2026-04-21",
            "expire_date": "2026-05-06",
            "status": "unopened",
            "remarks": "qa batch",
            "product": {
                "id": 1,
                "barcode": "123456",
                "product_name": "Milk",
                "unit": "box",
                "manufacturer": "Factory",
                "shelf_life_days": 15,
            },
        }

        response = self.client.get("/api/batches/3")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": 3,
                    "product_id": 1,
                    "batch_code": "BATCH-001",
                    "quantity": "8.50",
                    "received_at": None,
                    "manufacture_date": "2026-04-21",
                    "expire_date": "2026-05-06",
                    "status": "unopened",
                    "remarks": "qa batch",
                    "days_until_expiry": 9,
                    "expiry_progress": 0.4,
                    "expiry_status": "normal",
                    "product": {
                        "id": 1,
                        "barcode": "123456",
                        "product_name": "Milk",
                        "unit": "box",
                        "manufacturer": "Factory",
                    },
                },
            },
        )

    @patch("inventory.views.BatchService.update_batch")
    def test_patch_batch_returns_standard_shape(self, mock_update_batch):
        mock_update_batch.return_value = {
            "id": 3,
            "product_id": 1,
            "batch_code": "BATCH-001",
            "quantity": "9.50",
            "received_at": None,
            "manufacture_date": "2026-04-21",
            "expire_date": "2026-05-06",
            "status": "opened",
            "remarks": "updated",
            "product": {
                "id": 1,
                "barcode": "123456",
                "product_name": "Milk",
                "unit": "box",
                "manufacturer": "Factory",
            },
        }

        response = self.client.patch("/api/batches/3", {"remarks": "updated"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], 0)
        self.assertEqual(response.json()["data"]["remarks"], "updated")
        mock_update_batch.assert_called_once()
        self.assertIs(mock_update_batch.call_args.kwargs["actor"], self.user)

    def test_patch_batch_rejects_direct_quantity_update(self):
        response = self.client.patch("/api/batches/3", {"quantity": "9.50"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"code": 4001, "message": "validation_error", "data": None})

    @patch("inventory.views.BatchService.update_batch_status")
    def test_patch_batch_status_returns_standard_shape(self, mock_update_batch_status):
        mock_update_batch_status.return_value = {
            "id": 3,
            "product_id": 1,
            "batch_code": "BATCH-001",
            "quantity": "8.50",
            "received_at": None,
            "manufacture_date": "2026-04-21",
            "expire_date": "2026-05-06",
            "status": "used_up",
            "remarks": "qa batch",
            "product": {
                "id": 1,
                "barcode": "123456",
                "product_name": "Milk",
                "unit": "box",
                "manufacturer": "Factory",
            },
        }

        response = self.client.patch("/api/batches/3/status", {"status": "used_up"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], 0)
        self.assertEqual(response.json()["data"]["status"], "used_up")
        mock_update_batch_status.assert_called_once_with(3, "used_up", actor=self.user)

    @patch("inventory.views.BatchService.delete_batch")
    def test_delete_batch_returns_success_payload(self, mock_delete_batch):
        mock_delete_batch.return_value = {"id": 3}

        response = self.client.delete("/api/batches/3")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"code": 0, "message": "success", "data": {"id": 3}})
        mock_delete_batch.assert_called_once_with(3, actor=self.user)

    @patch("inventory.views.BatchService.list_expiry_alerts")
    def test_expiry_alerts_default_query_returns_standard_shape(self, mock_list_expiry_alerts):
        mock_list_expiry_alerts.return_value = ([], 0)

        response = self.client.get("/api/batches/expiry-alerts")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "code": 0,
                "message": "success",
                "data": {
                    "items": [],
                    "pagination": {"page": 1, "size": 20, "total": 0},
                },
            },
        )
        mock_list_expiry_alerts.assert_called_once_with(
            product_id=None,
            status=None,
            category=None,
            location=None,
            expiry_status=None,
            days_lte=30,
            include_expired=True,
            page=1,
            size=20,
        )

    @patch("inventory.views.BatchService.list_expiry_alerts")
    def test_expiry_alerts_passes_query_filters(self, mock_list_expiry_alerts):
        mock_list_expiry_alerts.return_value = ([], 0)

        response = self.client.get(
            "/api/batches/expiry-alerts",
            {
                "product_id": 1,
                "status": "opened",
                "category": "drink",
                "location": "A-01",
                "expiry_status": "normal",
                "days_lte": 3,
                "include_expired": "false",
                "page": 2,
                "size": 5,
            },
        )

        self.assertEqual(response.status_code, 200)
        mock_list_expiry_alerts.assert_called_once_with(
            product_id=1,
            status="opened",
            category="drink",
            location="A-01",
            expiry_status="normal",
            days_lte=3,
            include_expired=False,
            page=2,
            size=5,
        )

    def test_expiry_alerts_rejects_invalid_status(self):
        response = self.client.get("/api/batches/expiry-alerts", {"expiry_status": "unknown"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"code": 4001, "message": "validation_error", "data": None})

    @patch("inventory.views.QrCredentialService.build_label_payload")
    def test_batch_label_payload_returns_printable_qr_code(self, mock_build_label_payload):
        mock_build_label_payload.return_value = {
            "batchCode": "BATCH-001",
            "productName": "Milk",
            "barcode": "123456",
            "quantity": "8.50",
            "location": "A-01",
            "expireDate": "2026-05-06",
            "qrCode": "OB1|BATCH-001|token",
        }

        response = self.client.get("/api/batches/3/label-payload")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["qrCode"], "OB1|BATCH-001|token")
        mock_build_label_payload.assert_called_once_with(3, created_by="api-test")

    @patch("inventory.views.QrCredentialService.build_label_payload")
    def test_batch_label_payload_requires_authentication(self, mock_build_label_payload):
        client = APIClient()

        response = client.get("/api/batches/3/label-payload")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"code": 4011, "message": "unauthenticated", "data": None})
        mock_build_label_payload.assert_not_called()

    @patch("inventory.views.QrScanService.scan_qr")
    def test_qr_scan_returns_standard_scan_result(self, mock_scan_qr):
        mock_scan_qr.return_value = {
            "auditId": "scan_abc",
            "batchCode": "BATCH-001",
            "productName": "Milk",
            "status": "valid",
            "message": "该批次仍在效期内",
            "expireDate": "2026-05-06",
            "remainingDays": 9,
            "clientScanId": "client-1",
        }

        response = self.client.post(
            "/api/qr-scans",
            {
                "qr": "OB1|BATCH-001|token",
                "source": "mobile_camera",
                "deviceId": "device-001",
                "clientScanId": "client-1",
                "scannedAt": "2026-05-12T10:30:00+08:00",
            },
            format="json",
            REMOTE_ADDR="127.0.0.1",
            HTTP_USER_AGENT="api-test",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["auditId"], "scan_abc")
        self.assertEqual(response.json()["data"]["clientScanId"], "client-1")
        mock_scan_qr.assert_called_once()
        scan_payload = mock_scan_qr.call_args.args[0]
        self.assertEqual(scan_payload["qr"], "OB1|BATCH-001|token")
        self.assertEqual(scan_payload["source"], "mobile_camera")
        self.assertEqual(scan_payload["device_id"], "device-001")
        self.assertEqual(scan_payload["client_scan_id"], "client-1")
        self.assertIsNotNone(scan_payload["scanned_at"])
        self.assertEqual(mock_scan_qr.call_args.args[1]["ip_address"], "127.0.0.1")
        self.assertEqual(mock_scan_qr.call_args.args[1]["user_agent"], "api-test")
        self.assertEqual(mock_scan_qr.call_args.args[1]["scanner_user_id"], 123)

    def test_qr_scan_rejects_invalid_source(self):
        response = self.client.post(
            "/api/qr-scans",
            {
                "qr": "OB1|BATCH-001|token",
                "source": "unknown",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"code": 4001, "message": "validation_error", "data": None})

    @patch("inventory.views.QrScanService.scan_bulk")
    def test_bulk_qr_scan_returns_item_results(self, mock_scan_bulk):
        mock_scan_bulk.return_value = {
            "items": [
                {
                    "auditId": "scan_1",
                    "batchCode": "BATCH-001",
                    "productName": "Milk",
                    "status": "valid",
                    "message": "该批次仍在效期内",
                    "expireDate": "2026-05-06",
                    "remainingDays": 9,
                    "clientScanId": "client-1",
                },
                {
                    "auditId": "scan_2",
                    "batchCode": None,
                    "productName": None,
                    "status": "invalid",
                    "message": "二维码格式错误",
                    "expireDate": None,
                    "remainingDays": None,
                    "clientScanId": "client-2",
                },
            ]
        }

        response = self.client.post(
            "/api/qr-scans/bulk",
            {
                "items": [
                    {"qr": "OB1|BATCH-001|token", "source": "mobile_camera", "clientScanId": "client-1"},
                    {"qr": "bad", "source": "mobile_camera", "clientScanId": "client-2"},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["items"][1]["status"], "invalid")
        mock_scan_bulk.assert_called_once()
        self.assertEqual(mock_scan_bulk.call_args.args[1]["scanner_user_id"], 123)

    @patch("inventory.views.BatchService.create_batch")
    def test_create_batch_translates_product_not_found(self, mock_create_batch):
        mock_create_batch.side_effect = NotFoundApiError("Product 404 not found")

        response = self.client.post(
            "/api/batches",
            {
                "product_id": 404,
                "quantity": "10.00",
                "manufacture_date": "2026-04-21",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"code": 4041, "message": "not_found", "data": None})
        mock_create_batch.assert_called_once()
        self.assertIs(mock_create_batch.call_args.kwargs["actor"], self.user)

    @patch("inventory.views.BatchOperationService.create_operation")
    def test_create_batch_operation_returns_operation_and_batch_summary(self, mock_create_operation):
        mock_create_operation.return_value = (
            SimpleNamespace(
                id=7,
                batch_id=3,
                operation_type="loss",
                quantity=Decimal("2.00"),
                quantity_after=Decimal("6.50"),
                remarks="broken package",
                created_at=None,
                reversed_operation_id=None,
                is_reverted=False,
            ),
            SimpleNamespace(id=3, quantity=Decimal("6.50"), status=None),
        )

        response = self.client.post(
            "/api/batches/3/operations",
            {
                "operation_type": "loss",
                "quantity": "2.00",
                "remarks": "broken package",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {
                "code": 0,
                "message": "success",
                "data": {
                    "operation": {
                        "id": 7,
                        "batch_id": 3,
                        "operation_type": "loss",
                        "quantity": "2.00",
                        "quantity_after": "6.50",
                        "remarks": "broken package",
                        "created_at": None,
                        "reversed_operation_id": None,
                        "is_reverted": False,
                    },
                    "batch": {
                        "id": 3,
                        "quantity": "6.50",
                        "status": None,
                    },
                },
            },
        )
        mock_create_operation.assert_called_once()
        self.assertEqual(mock_create_operation.call_args.args[0], 3)
        self.assertEqual(mock_create_operation.call_args.args[1]["quantity"], Decimal("2.00"))
        self.assertIs(mock_create_operation.call_args.kwargs["actor"], self.user)

    @patch("inventory.views.BatchOperationService.list_operations")
    def test_list_batch_operations_returns_paginated_history(self, mock_list_operations):
        mock_list_operations.return_value = (
            [
                SimpleNamespace(
                    id=7,
                    batch_id=3,
                    operation_type="loss",
                    quantity=Decimal("2.00"),
                    quantity_after=Decimal("6.50"),
                    remarks="broken package",
                    created_at=None,
                    reversed_operation_id=None,
                    is_reverted=True,
                )
            ],
            1,
        )

        response = self.client.get(
            "/api/batches/3/operations",
            {
                "operation_type": "loss",
                "page": 2,
                "size": 5,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["pagination"], {"page": 2, "size": 5, "total": 1})
        self.assertEqual(response.json()["data"]["items"][0]["quantity_after"], "6.50")
        self.assertIs(response.json()["data"]["items"][0]["is_reverted"], True)
        mock_list_operations.assert_called_once_with(batch_id=3, operation_type="loss", page=2, size=5)

    @patch("inventory.views.BatchOperationService.revert_operation")
    def test_revert_batch_operation_returns_reversal_and_batch_summary(self, mock_revert_operation):
        mock_revert_operation.return_value = (
            SimpleNamespace(
                id=8,
                batch_id=3,
                operation_type="add",
                quantity=Decimal("2.00"),
                quantity_after=Decimal("8.50"),
                remarks="undo loss",
                created_at=None,
                reversed_operation_id=7,
                is_reverted=False,
            ),
            SimpleNamespace(id=3, quantity=Decimal("8.50"), status=None),
        )

        response = self.client.post(
            "/api/batches/3/operations/7/revert",
            {"remarks": "undo loss"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {
                "code": 0,
                "message": "success",
                "data": {
                    "operation": {
                        "id": 8,
                        "batch_id": 3,
                        "operation_type": "add",
                        "quantity": "2.00",
                        "quantity_after": "8.50",
                        "remarks": "undo loss",
                        "created_at": None,
                        "reversed_operation_id": 7,
                        "is_reverted": False,
                    },
                    "batch": {
                        "id": 3,
                        "quantity": "8.50",
                        "status": None,
                    },
                },
            },
        )
        mock_revert_operation.assert_called_once_with(
            batch_id=3,
            operation_id=7,
            data={"remarks": "undo loss"},
            actor=self.user,
        )

    @patch("inventory.views.BatchOperationService.revert_operation")
    def test_revert_batch_operation_translates_conflict(self, mock_revert_operation):
        mock_revert_operation.side_effect = ConflictApiError("Batch operation has already been reverted")

        response = self.client.post("/api/batches/3/operations/7/revert", {}, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"code": 4091, "message": "conflict", "data": None})
        mock_revert_operation.assert_called_once_with(batch_id=3, operation_id=7, data={}, actor=self.user)

    def test_create_batch_operation_rejects_invalid_operation_type(self):
        response = self.client.post(
            "/api/batches/3/operations",
            {
                "operation_type": "unknown",
                "quantity": "2.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"code": 4001, "message": "validation_error", "data": None})

    def test_create_batch_operation_rejects_non_positive_quantity(self):
        response = self.client.post(
            "/api/batches/3/operations",
            {
                "operation_type": "add",
                "quantity": "0",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"code": 4001, "message": "validation_error", "data": None})

    @patch("inventory.views.BatchOperationService.create_operation")
    def test_create_batch_operation_translates_conflict(self, mock_create_operation):
        mock_create_operation.side_effect = ConflictApiError("Insufficient batch quantity")

        response = self.client.post(
            "/api/batches/3/operations",
            {
                "operation_type": "deduct",
                "quantity": 99,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"code": 4091, "message": "conflict", "data": None})
        mock_create_operation.assert_called_once()
        self.assertIs(mock_create_operation.call_args.kwargs["actor"], self.user)

    def test_validation_error_returns_business_code_and_stable_message(self):
        response = self.client.post(
            "/api/products",
            {
                "barcode": "123456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"code": 4001, "message": "validation_error", "data": None})
