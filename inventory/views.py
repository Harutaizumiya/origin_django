from common.responses import success_response
from common.views import ServiceAPIView
from inventory.schemas import (
    AnalyticsSummaryQuerySerializer,
    AnalyticsSummarySerializer,
    BatchCreateSerializer,
    ExpiryAlertQuerySerializer,
    BatchListQuerySerializer,
    BatchOperationCreateSerializer,
    BatchOperationListQuerySerializer,
    BatchOperationOutputSerializer,
    BatchOperationRevertSerializer,
    BatchOutputSerializer,
    BatchLabelPayloadSerializer,
    BatchQuantitySummarySerializer,
    BatchStatusUpdateSerializer,
    BatchUpdateSerializer,
    CategoryQuerySerializer,
    DashboardOverviewSerializer,
    ProductCreateSerializer,
    ProductBatchListQuerySerializer,
    ProductListQuerySerializer,
    ProductOutputSerializer,
    ProductUpdateSerializer,
    QrScanBulkRequestSerializer,
    QrScanBulkResultSerializer,
    QrScanRequestSerializer,
    QrScanResultSerializer,
)
from inventory.services import (
    AnalyticsService,
    BatchOperationService,
    BatchService,
    DashboardService,
    ProductService,
    QrCredentialService,
    QrScanService,
)


def paginated_payload(*, items, page: int, size: int, total: int):
    return {
        "items": items,
        "pagination": {
            "page": page,
            "size": size,
            "total": total,
        },
    }


def qr_scan_payload(validated_data: dict) -> dict:
    return {
        "qr": validated_data["qr"],
        "source": validated_data["source"],
        "device_id": validated_data.get("deviceId"),
        "client_scan_id": validated_data.get("clientScanId"),
        "scanned_at": validated_data.get("scannedAt"),
    }


def scan_request_context(request) -> dict:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip_address = forwarded_for.split(",", 1)[0].strip() if forwarded_for else request.META.get("REMOTE_ADDR")
    user = getattr(request, "user", None)
    scanner_user = None
    scanner_user_id = None
    if user is not None and getattr(user, "is_authenticated", False):
        scanner_user = str(user)
        scanner_user_id = getattr(user, "id", None)
    return {
        "ip_address": ip_address,
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "scanner_user": scanner_user,
        "scanner_user_id": scanner_user_id,
    }


class DashboardOverviewView(ServiceAPIView):
    permission_map = {"GET": "dashboard_read"}

    def get(self, request):
        overview = DashboardService.get_overview()
        serializer = DashboardOverviewSerializer(overview)
        return success_response(serializer.data)


class AnalyticsSummaryView(ServiceAPIView):
    permission_map = {"GET": "analytics_read"}

    def get(self, request):
        query = AnalyticsSummaryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        summary = AnalyticsService.get_summary(range_value=query.validated_data["range"])
        serializer = AnalyticsSummarySerializer(summary)
        return success_response(serializer.data)


class ProductCollectionView(ServiceAPIView):
    permission_map = {"GET": "products_read", "POST": "products_create"}

    def get(self, request):
        query = ProductListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        products, total = ProductService.list_products(
            search=query.validated_data.get("search"),
            page=query.validated_data["page"],
            size=query.validated_data["size"],
        )
        serializer = ProductOutputSerializer(products, many=True)
        return success_response(
            paginated_payload(
                items=serializer.data,
                page=query.validated_data["page"],
                size=query.validated_data["size"],
                total=total,
            ),
        )

    def post(self, request):
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = ProductService.create_product(serializer.validated_data, actor=request.user)
        return success_response(ProductOutputSerializer(product).data, status_code=201)


class ProductDetailView(ServiceAPIView):
    permission_map = {"GET": "products_read", "PATCH": "products_update", "DELETE": "products_delete"}

    def get(self, request, product_id: int):
        product = ProductService.get_product(product_id)
        return success_response(ProductOutputSerializer(product).data)

    def patch(self, request, product_id: int):
        serializer = ProductUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = ProductService.update_product(product_id, serializer.validated_data, actor=request.user)
        return success_response(ProductOutputSerializer(product).data)

    def delete(self, request, product_id: int):
        result = ProductService.delete_product(product_id, actor=request.user)
        return success_response(result)


class ProductBarcodeDetailView(ServiceAPIView):
    permission_map = {"GET": "products_read"}

    def get(self, request, barcode: str):
        product = ProductService.get_product_by_barcode(barcode)
        return success_response(ProductOutputSerializer(product).data)


class ProductCategoriesView(ServiceAPIView):
    permission_map = {"GET": "products_read"}

    def get(self, request):
        query = CategoryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        categories = ProductService.list_categories(query.validated_data.get("search"))
        return success_response({"items": categories, "pagination": None})


class ProductBatchCollectionView(ServiceAPIView):
    permission_map = {"GET": "batches_read"}

    def get(self, request, product_id: int):
        query = ProductBatchListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        batches, total = BatchService.list_batches(
            product_id=product_id,
            status=query.validated_data.get("status"),
            expired_only=query.validated_data["expired_only"],
            page=query.validated_data["page"],
            size=query.validated_data["size"],
        )
        serializer = BatchOutputSerializer(batches, many=True)
        return success_response(
            paginated_payload(
                items=serializer.data,
                page=query.validated_data["page"],
                size=query.validated_data["size"],
                total=total,
            ),
        )


class BatchCollectionView(ServiceAPIView):
    permission_map = {"GET": "batches_read", "POST": "batches_create"}

    def get(self, request):
        query = BatchListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        batches, total = BatchService.list_batches(
            product_id=query.validated_data.get("product_id"),
            status=query.validated_data.get("status"),
            expired_only=query.validated_data["expired_only"],
            page=query.validated_data["page"],
            size=query.validated_data["size"],
        )
        serializer = BatchOutputSerializer(batches, many=True)
        return success_response(
            paginated_payload(
                items=serializer.data,
                page=query.validated_data["page"],
                size=query.validated_data["size"],
                total=total,
            ),
        )

    def post(self, request):
        serializer = BatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = BatchService.create_batch(serializer.validated_data, actor=request.user)
        return success_response(BatchOutputSerializer(batch).data, status_code=201)


class BatchExpiryAlertsView(ServiceAPIView):
    permission_map = {"GET": "batches_read"}

    def get(self, request):
        query = ExpiryAlertQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        batches, total = BatchService.list_expiry_alerts(
            product_id=query.validated_data.get("product_id"),
            status=query.validated_data.get("status"),
            category=query.validated_data.get("category"),
            location=query.validated_data.get("location"),
            expiry_status=query.validated_data.get("expiry_status"),
            days_lte=query.validated_data["days_lte"],
            include_expired=query.validated_data["include_expired"],
            page=query.validated_data["page"],
            size=query.validated_data["size"],
        )
        serializer = BatchOutputSerializer(batches, many=True)
        return success_response(
            paginated_payload(
                items=serializer.data,
                page=query.validated_data["page"],
                size=query.validated_data["size"],
                total=total,
            ),
        )


class BatchLabelPayloadView(ServiceAPIView):
    permission_map = {"GET": "label_payload_issue"}

    def get(self, request, batch_id: int):
        payload = QrCredentialService.build_label_payload(batch_id, created_by=str(request.user))
        serializer = BatchLabelPayloadSerializer(payload)
        return success_response(serializer.data)


class QrScanCollectionView(ServiceAPIView):
    permission_map = {"POST": "qr_scans_create"}

    def post(self, request):
        serializer = QrScanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = QrScanService.scan_qr(
            qr_scan_payload(serializer.validated_data),
            scan_request_context(request),
        )
        output = QrScanResultSerializer(result)
        return success_response(output.data)


class QrScanBulkView(ServiceAPIView):
    permission_map = {"POST": "qr_scans_create"}

    def post(self, request):
        serializer = QrScanBulkRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = QrScanService.scan_bulk(
            [qr_scan_payload(item) for item in serializer.validated_data["items"]],
            scan_request_context(request),
        )
        output = QrScanBulkResultSerializer(result)
        return success_response(output.data)


class BatchOperationCollectionView(ServiceAPIView):
    permission_map = {"GET": "batch_operations_read"}

    def get_required_permission(self, request):
        if request.method != "POST":
            return self.permission_map.get(request.method)
        return {
            "add": "batch_operations_add",
            "deduct": "batch_operations_deduct",
            "loss": "batch_operations_loss",
        }.get(request.data.get("operation_type"))

    def get(self, request, batch_id: int):
        query = BatchOperationListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        operations, total = BatchOperationService.list_operations(
            batch_id=batch_id,
            operation_type=query.validated_data.get("operation_type"),
            page=query.validated_data["page"],
            size=query.validated_data["size"],
        )
        serializer = BatchOperationOutputSerializer(operations, many=True)
        return success_response(
            paginated_payload(
                items=serializer.data,
                page=query.validated_data["page"],
                size=query.validated_data["size"],
                total=total,
            ),
        )

    def post(self, request, batch_id: int):
        serializer = BatchOperationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        operation, batch = BatchOperationService.create_operation(batch_id, serializer.validated_data, actor=request.user)
        return success_response(
            {
                "operation": BatchOperationOutputSerializer(operation).data,
                "batch": BatchQuantitySummarySerializer(batch).data,
            },
            status_code=201,
        )


class BatchOperationRevertView(ServiceAPIView):
    permission_map = {"POST": "batch_operations_revert"}

    def post(self, request, batch_id: int, operation_id: int):
        serializer = BatchOperationRevertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        operation, batch = BatchOperationService.revert_operation(
            batch_id=batch_id,
            operation_id=operation_id,
            data=serializer.validated_data,
            actor=request.user,
        )
        return success_response(
            {
                "operation": BatchOperationOutputSerializer(operation).data,
                "batch": BatchQuantitySummarySerializer(batch).data,
            },
            status_code=201,
        )


class BatchDetailView(ServiceAPIView):
    permission_map = {"GET": "batches_read", "PATCH": "batches_update", "DELETE": "batches_delete"}

    def get(self, request, batch_id: int):
        batch = BatchService.get_batch(batch_id)
        return success_response(BatchOutputSerializer(batch).data)

    def patch(self, request, batch_id: int):
        serializer = BatchUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = BatchService.update_batch(batch_id, serializer.validated_data, actor=request.user)
        return success_response(BatchOutputSerializer(batch).data)

    def delete(self, request, batch_id: int):
        result = BatchService.delete_batch(batch_id, actor=request.user)
        return success_response(result)


class BatchStatusView(ServiceAPIView):
    permission_map = {"PATCH": "batches_update"}

    def patch(self, request, batch_id: int):
        serializer = BatchStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = BatchService.update_batch_status(batch_id, serializer.validated_data["status"], actor=request.user)
        return success_response(BatchOutputSerializer(batch).data)
