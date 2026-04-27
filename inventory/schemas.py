from rest_framework import serializers

from inventory.models import Batch, Product


class ProductListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


class CategoryQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True)


class ProductCreateSerializer(serializers.Serializer):
    barcode = serializers.CharField()
    product_name = serializers.CharField()
    shelf_life_days = serializers.IntegerField(min_value=0)
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    category = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    unit = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    manufacturer = serializers.CharField()


class ProductUpdateSerializer(serializers.Serializer):
    product_name = serializers.CharField(required=False)
    shelf_life_days = serializers.IntegerField(required=False, min_value=0)
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    category = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    unit = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    manufacturer = serializers.CharField(required=False)


class ProductBatchListQuerySerializer(serializers.Serializer):
    status = serializers.CharField(required=False, allow_blank=False)
    expired_only = serializers.BooleanField(required=False, default=False)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


class ProductOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "barcode",
            "product_name",
            "shelf_life_days",
            "location",
            "category",
            "unit",
            "manufacturer",
            "created_at",
            "updated_at",
        ]


class BatchListQuerySerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=False, min_value=1)
    status = serializers.CharField(required=False, allow_blank=False)
    expired_only = serializers.BooleanField(required=False, default=False)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


class BatchCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    batch_code = serializers.CharField(required=False, allow_blank=False)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2)
    manufacture_date = serializers.DateField()
    expire_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_blank=False, default="unopened")
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class BatchUpdateSerializer(serializers.Serializer):
    batch_code = serializers.CharField(required=False, allow_blank=False)
    quantity = serializers.DecimalField(required=False, max_digits=12, decimal_places=2)
    manufacture_date = serializers.DateField(required=False)
    expire_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_blank=False)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class BatchStatusUpdateSerializer(serializers.Serializer):
    status = serializers.CharField()


class ProductSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "barcode", "product_name", "unit", "manufacturer"]


class BatchOutputSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product = ProductSummarySerializer(read_only=True)

    class Meta:
        model = Batch
        fields = [
            "id",
            "product_id",
            "batch_code",
            "quantity",
            "received_at",
            "manufacture_date",
            "expire_date",
            "status",
            "remarks",
            "product",
        ]
