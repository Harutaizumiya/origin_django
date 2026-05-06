from django.urls import path

from inventory.views import (
    BatchCollectionView,
    BatchDetailView,
    BatchExpiryAlertsView,
    BatchStatusView,
    ProductBarcodeDetailView,
    ProductBatchCollectionView,
    ProductCategoriesView,
    ProductCollectionView,
    ProductDetailView,
)

urlpatterns = [
    path("products", ProductCollectionView.as_view(), name="product-collection"),
    path("products/barcode/<str:barcode>", ProductBarcodeDetailView.as_view(), name="product-by-barcode"),
    path("products/categories", ProductCategoriesView.as_view(), name="product-categories"),
    path("products/<int:product_id>/batches", ProductBatchCollectionView.as_view(), name="product-batches"),
    path("products/<int:product_id>", ProductDetailView.as_view(), name="product-detail"),
    path("batches", BatchCollectionView.as_view(), name="batch-collection"),
    path("batches/expiry-alerts", BatchExpiryAlertsView.as_view(), name="batch-expiry-alerts"),
    path("batches/<int:batch_id>/status", BatchStatusView.as_view(), name="batch-status"),
    path("batches/<int:batch_id>", BatchDetailView.as_view(), name="batch-detail"),
]
