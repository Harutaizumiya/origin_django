from common.responses import success_response
from common.views import ServiceAPIView
from inventory.schemas import (
    BatchCreateSerializer,
    BatchListQuerySerializer,
    BatchOutputSerializer,
    CategoryQuerySerializer,
    ProductCreateSerializer,
    ProductListQuerySerializer,
    ProductOutputSerializer,
    ProductUpdateSerializer,
)
from inventory.services import BatchService, ProductService


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
            serializer.data,
            meta={
                "page": query.validated_data["page"],
                "size": query.validated_data["size"],
                "total": total,
            },
        )

    def post(self, request):
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = ProductService.create_product(serializer.validated_data)
        return success_response(ProductOutputSerializer(product).data, status_code=201)


class ProductDetailView(ServiceAPIView):
    def patch(self, request, product_id: int):
        serializer = ProductUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = ProductService.update_product(product_id, serializer.validated_data)
        return success_response(ProductOutputSerializer(product).data)

    def delete(self, request, product_id: int):
        result = ProductService.delete_product(product_id)
        return success_response(result)


class ProductCategoriesView(ServiceAPIView):
    def get(self, request):
        query = CategoryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        categories = ProductService.list_categories(query.validated_data.get("search"))
        return success_response(categories)


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
            serializer.data,
            meta={
                "page": query.validated_data["page"],
                "size": query.validated_data["size"],
                "total": total,
            },
        )

    def post(self, request):
        serializer = BatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = BatchService.create_batch(serializer.validated_data)
        return success_response(BatchOutputSerializer(batch).data, status_code=201)
