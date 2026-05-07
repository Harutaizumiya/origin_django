from common.responses import success_response
from common.views import ServiceAPIView
from inventory.schemas import (
    BatchCreateSerializer,
    ExpiryAlertQuerySerializer,
    BatchListQuerySerializer,
    BatchOperationCreateSerializer,
    BatchOperationListQuerySerializer,
    BatchOperationOutputSerializer,
    BatchOperationRevertSerializer,
    BatchOutputSerializer,
    BatchQuantitySummarySerializer,
    BatchStatusUpdateSerializer,
    BatchUpdateSerializer,
    CategoryQuerySerializer,
    ProductCreateSerializer,
    ProductBatchListQuerySerializer,
    ProductListQuerySerializer,
    ProductOutputSerializer,
    ProductUpdateSerializer,
)
from inventory.services import BatchOperationService, BatchService, ProductService


def paginated_payload(*, items, page: int, size: int, total: int):
    return {
        "items": items,
        "pagination": {
            "page": page,
            "size": size,
            "total": total,
        },
    }


class ProductCollectionView(ServiceAPIView):
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
        product = ProductService.create_product(serializer.validated_data)
        return success_response(ProductOutputSerializer(product).data, status_code=201)


class ProductDetailView(ServiceAPIView):
    def get(self, request, product_id: int):
        product = ProductService.get_product(product_id)
        return success_response(ProductOutputSerializer(product).data)

    def patch(self, request, product_id: int):
        serializer = ProductUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = ProductService.update_product(product_id, serializer.validated_data)
        return success_response(ProductOutputSerializer(product).data)

    def delete(self, request, product_id: int):
        result = ProductService.delete_product(product_id)
        return success_response(result)


class ProductBarcodeDetailView(ServiceAPIView):
    def get(self, request, barcode: str):
        product = ProductService.get_product_by_barcode(barcode)
        return success_response(ProductOutputSerializer(product).data)


class ProductCategoriesView(ServiceAPIView):
    def get(self, request):
        query = CategoryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        categories = ProductService.list_categories(query.validated_data.get("search"))
        return success_response({"items": categories, "pagination": None})


class ProductBatchCollectionView(ServiceAPIView):
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
        batch = BatchService.create_batch(serializer.validated_data)
        return success_response(BatchOutputSerializer(batch).data, status_code=201)


class BatchExpiryAlertsView(ServiceAPIView):
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


class BatchOperationCollectionView(ServiceAPIView):
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
        operation, batch = BatchOperationService.create_operation(batch_id, serializer.validated_data)
        return success_response(
            {
                "operation": BatchOperationOutputSerializer(operation).data,
                "batch": BatchQuantitySummarySerializer(batch).data,
            },
            status_code=201,
        )


class BatchOperationRevertView(ServiceAPIView):
    def post(self, request, batch_id: int, operation_id: int):
        serializer = BatchOperationRevertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        operation, batch = BatchOperationService.revert_operation(
            batch_id=batch_id,
            operation_id=operation_id,
            data=serializer.validated_data,
        )
        return success_response(
            {
                "operation": BatchOperationOutputSerializer(operation).data,
                "batch": BatchQuantitySummarySerializer(batch).data,
            },
            status_code=201,
        )


class BatchDetailView(ServiceAPIView):
    def get(self, request, batch_id: int):
        batch = BatchService.get_batch(batch_id)
        return success_response(BatchOutputSerializer(batch).data)

    def patch(self, request, batch_id: int):
        serializer = BatchUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = BatchService.update_batch(batch_id, serializer.validated_data)
        return success_response(BatchOutputSerializer(batch).data)

    def delete(self, request, batch_id: int):
        result = BatchService.delete_batch(batch_id)
        return success_response(result)


class BatchStatusView(ServiceAPIView):
    def patch(self, request, batch_id: int):
        serializer = BatchStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = BatchService.update_batch_status(batch_id, serializer.validated_data["status"])
        return success_response(BatchOutputSerializer(batch).data)
