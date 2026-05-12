from decimal import Decimal

from rest_framework import serializers

from inventory.expiry import VALID_EXPIRY_STATUSES, calc_days_until_expiry, calc_expiry_progress, calc_expiry_status
from inventory.models import Batch, BatchOperation, Product
from inventory.services import QR_SCAN_SOURCES, QR_SCAN_STATUSES


VALID_BATCH_OPERATION_TYPES = ("add", "loss", "deduct")


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


class ExpiryAlertQuerySerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=False, min_value=1)
    status = serializers.CharField(required=False, allow_blank=False)
    category = serializers.CharField(required=False, allow_blank=False)
    location = serializers.CharField(required=False, allow_blank=False)
    expiry_status = serializers.ChoiceField(required=False, choices=VALID_EXPIRY_STATUSES)
    days_lte = serializers.IntegerField(required=False, default=30, min_value=0)
    include_expired = serializers.BooleanField(required=False, default=True)
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
    manufacture_date = serializers.DateField(required=False)
    expire_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_blank=False)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        if "quantity" in self.initial_data:
            raise serializers.ValidationError({"quantity": "Use batch operations to change quantity."})
        return attrs


class BatchStatusUpdateSerializer(serializers.Serializer):
    status = serializers.CharField()


class BatchOperationCreateSerializer(serializers.Serializer):
    operation_type = serializers.ChoiceField(choices=VALID_BATCH_OPERATION_TYPES)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class BatchOperationRevertSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class BatchOperationListQuerySerializer(serializers.Serializer):
    operation_type = serializers.ChoiceField(required=False, choices=VALID_BATCH_OPERATION_TYPES)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


class QrScanRequestSerializer(serializers.Serializer):
    qr = serializers.CharField()
    source = serializers.ChoiceField(choices=QR_SCAN_SOURCES)
    deviceId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    clientScanId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    scannedAt = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        for field in ("deviceId", "clientScanId"):
            if attrs.get(field) == "":
                attrs[field] = None
        return attrs


class QrScanBulkRequestSerializer(serializers.Serializer):
    items = QrScanRequestSerializer(many=True, allow_empty=False)


class BatchLabelPayloadSerializer(serializers.Serializer):
    batchCode = serializers.CharField()
    productName = serializers.CharField()
    barcode = serializers.CharField()
    quantity = serializers.CharField(allow_null=True)
    location = serializers.CharField(allow_null=True)
    expireDate = serializers.CharField(allow_null=True)
    qrCode = serializers.CharField()


class QrScanResultSerializer(serializers.Serializer):
    auditId = serializers.CharField()
    batchCode = serializers.CharField(allow_null=True)
    productName = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=QR_SCAN_STATUSES)
    message = serializers.CharField()
    expireDate = serializers.CharField(allow_null=True)
    remainingDays = serializers.IntegerField(allow_null=True)
    clientScanId = serializers.CharField(required=False, allow_null=True)


class QrScanBulkResultSerializer(serializers.Serializer):
    items = QrScanResultSerializer(many=True)


class ProductSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "barcode", "product_name", "unit", "manufacturer"]


class BatchOutputSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product = ProductSummarySerializer(read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    expiry_progress = serializers.SerializerMethodField()
    expiry_status = serializers.SerializerMethodField()

    def get_days_until_expiry(self, obj):
        return calc_days_until_expiry(self._value(obj, "expire_date"))

    def get_expiry_progress(self, obj):
        return calc_expiry_progress(
            self._value(obj, "manufacture_date"),
            self._product_value(obj, "shelf_life_days"),
        )

    def get_expiry_status(self, obj):
        return calc_expiry_status(
            self._value(obj, "manufacture_date"),
            self._product_value(obj, "shelf_life_days"),
        )

    @staticmethod
    def _value(obj, field):
        if isinstance(obj, dict):
            return obj.get(field)
        return getattr(obj, field, None)

    @classmethod
    def _product_value(cls, obj, field):
        product = cls._value(obj, "product")
        if isinstance(product, dict):
            return product.get(field)
        return getattr(product, field, None)

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
            "days_until_expiry",
            "expiry_progress",
            "expiry_status",
            "product",
        ]


class BatchQuantitySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = ["id", "quantity", "status"]


class BatchOperationOutputSerializer(serializers.ModelSerializer):
    is_reverted = serializers.SerializerMethodField()

    def get_is_reverted(self, obj):
        if isinstance(obj, dict):
            return bool(obj.get("is_reverted"))
        if hasattr(obj, "is_reverted"):
            return bool(obj.is_reverted)
        if not hasattr(obj, "reversal_operations"):
            return False
        return obj.reversal_operations.exists()

    class Meta:
        model = BatchOperation
        fields = [
            "id",
            "batch_id",
            "operation_type",
            "quantity",
            "quantity_after",
            "remarks",
            "created_at",
            "reversed_operation_id",
            "is_reverted",
        ]
