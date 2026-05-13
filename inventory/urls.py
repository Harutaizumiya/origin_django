from django.urls import path

from inventory.views import (
    AnalyticsSummaryView,
    BatchCollectionView,
    BatchDetailView,
    BatchExpiryAlertsView,
    BatchLabelPayloadView,
    BatchOperationCollectionView,
    BatchOperationRevertView,
    BatchStatusView,
    DashboardOverviewView,
    ProductBarcodeDetailView,
    ProductBatchCollectionView,
    ProductCategoriesView,
    ProductCollectionView,
    ProductDetailView,
    QrScanBulkView,
    QrScanCollectionView,
)

urlpatterns = [
    path("dashboard/overview", DashboardOverviewView.as_view(), name="dashboard-overview"),
    path("analytics/summary", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("products", ProductCollectionView.as_view(), name="product-collection"),
    path("products/barcode/<str:barcode>", ProductBarcodeDetailView.as_view(), name="product-by-barcode"),
    path("products/categories", ProductCategoriesView.as_view(), name="product-categories"),
    path("products/<int:product_id>/batches", ProductBatchCollectionView.as_view(), name="product-batches"),
    path("products/<int:product_id>", ProductDetailView.as_view(), name="product-detail"),
    path("batches", BatchCollectionView.as_view(), name="batch-collection"),
    path("batches/expiry-alerts", BatchExpiryAlertsView.as_view(), name="batch-expiry-alerts"),
    path("batches/<int:batch_id>/label-payload", BatchLabelPayloadView.as_view(), name="batch-label-payload"),
    path("batches/<int:batch_id>/operations", BatchOperationCollectionView.as_view(), name="batch-operations"),
    path(
        "batches/<int:batch_id>/operations/<int:operation_id>/revert",
        BatchOperationRevertView.as_view(),
        name="batch-operation-revert",
    ),
    path("batches/<int:batch_id>/status", BatchStatusView.as_view(), name="batch-status"),
    path("batches/<int:batch_id>", BatchDetailView.as_view(), name="batch-detail"),
    path("qr-scans", QrScanCollectionView.as_view(), name="qr-scan-collection"),
    path("qr-scans/bulk", QrScanBulkView.as_view(), name="qr-scan-bulk"),
]
