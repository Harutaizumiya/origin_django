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
        self.assertEqual(response.json(), {"data": [], "meta": {"page": 1, "size": 20, "total": 0}})

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
        self.assertEqual(response.json(), {"error": {"code": "conflict", "message": "Barcode already exists"}})

    @patch("inventory.views.ProductService.update_product")
    def test_patch_product_returns_not_found_shape(self, mock_update_product):
        mock_update_product.side_effect = NotFoundApiError("Product 99 not found")

        response = self.client.patch("/api/products/99", {"product_name": "New"}, format="json")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": {"code": "not_found", "message": "Product 99 not found"}})

    @patch("inventory.views.ProductService.delete_product")
    def test_delete_product_returns_success_payload(self, mock_delete_product):
        mock_delete_product.return_value = {"id": 7}

        response = self.client.delete("/api/products/7")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": {"id": 7}})

    @patch("inventory.views.ProductService.list_categories")
    def test_list_categories_returns_data_array(self, mock_list_categories):
        mock_list_categories.return_value = ["drink", "snack"]

        response = self.client.get("/api/products/categories")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": ["drink", "snack"]})

    @patch("inventory.views.BatchService.list_batches")
    def test_list_batches_returns_standard_shape(self, mock_list_batches):
        mock_list_batches.return_value = ([], 0)

        response = self.client.get("/api/batches", {"page": 1, "size": 20})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": [], "meta": {"page": 1, "size": 20, "total": 0}})

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
        self.assertEqual(response.json(), {"error": {"code": "not_found", "message": "Product 404 not found"}})
