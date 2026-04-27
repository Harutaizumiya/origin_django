from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from common.exceptions import ConflictApiError, NotFoundApiError


class InventoryApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_homepage_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Origin Django")

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

    @patch("inventory.views.ProductService.update_product")
    def test_patch_product_returns_not_found_shape(self, mock_update_product):
        mock_update_product.side_effect = NotFoundApiError("Product 99 not found")

        response = self.client.patch("/api/products/99", {"product_name": "New"}, format="json")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"code": 4041, "message": "not_found", "data": None})

    @patch("inventory.views.ProductService.delete_product")
    def test_delete_product_returns_success_payload(self, mock_delete_product):
        mock_delete_product.return_value = {"id": 7}

        response = self.client.delete("/api/products/7")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"code": 0, "message": "success", "data": {"id": 7}})

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

    @patch("inventory.views.BatchService.get_batch")
    def test_get_batch_detail_returns_standard_shape(self, mock_get_batch):
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

        response = self.client.patch("/api/batches/3", {"quantity": "9.50", "remarks": "updated"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], 0)
        self.assertEqual(response.json()["data"]["remarks"], "updated")

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

    @patch("inventory.views.BatchService.delete_batch")
    def test_delete_batch_returns_success_payload(self, mock_delete_batch):
        mock_delete_batch.return_value = {"id": 3}

        response = self.client.delete("/api/batches/3")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"code": 0, "message": "success", "data": {"id": 3}})

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
