from django.db import models
from django.db.models.functions import Now


class Product(models.Model):
    id = models.BigAutoField(primary_key=True)
    barcode = models.CharField(max_length=255, unique=True)
    product_name = models.CharField(max_length=255)
    shelf_life_days = models.IntegerField()
    location = models.CharField(max_length=255, blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)
    unit = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, db_default=Now())
    updated_at = models.DateTimeField(blank=True, db_default=Now())
    manufacturer = models.TextField()

    class Meta:
        managed = False
        db_table = "product"


class Batch(models.Model):
    id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.DO_NOTHING, related_name="batches", db_column="product_id")
    batch_code = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    received_at = models.DateTimeField(blank=True, db_default=Now())
    manufacture_date = models.DateField(blank=True, null=True)
    expire_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=255, blank=True, null=True)
    remarks = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "batches"


class BatchOperation(models.Model):
    id = models.BigAutoField(primary_key=True)
    batch = models.ForeignKey(Batch, on_delete=models.DO_NOTHING, related_name="operations", db_column="batch_id")
    reversed_operation = models.ForeignKey(
        "self",
        on_delete=models.DO_NOTHING,
        related_name="reversal_operations",
        db_column="reversed_operation_id",
        blank=True,
        null=True,
    )
    operation_type = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=2)
    remarks = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, db_default=Now())

    class Meta:
        managed = False
        db_table = "batch_operations"
        indexes = [
            models.Index(fields=["batch", "-created_at", "-id"], name="batch_ops_batch_created_idx"),
            models.Index(fields=["operation_type"], name="batch_operations_type_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["reversed_operation"], name="batch_operations_reversed_operation_uniq"),
        ]


class BatchQrCredential(models.Model):
    id = models.BigAutoField(primary_key=True)
    batch = models.ForeignKey(Batch, on_delete=models.DO_NOTHING, related_name="qr_credentials", db_column="batch_id")
    batch_code = models.CharField(max_length=255)
    token_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField(blank=True, db_default=Now())
    revoked_at = models.DateTimeField(blank=True, null=True)
    created_by = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "batch_qr_credentials"
        indexes = [
            models.Index(fields=["batch", "revoked_at"], name="batch_qr_batch_rev_idx"),
            models.Index(fields=["batch_code"], name="batch_qr_credentials_code_idx"),
        ]


class QrScanAuditLog(models.Model):
    id = models.CharField(max_length=40, primary_key=True)
    raw_qr = models.TextField()
    batch = models.ForeignKey(
        Batch,
        on_delete=models.DO_NOTHING,
        related_name="qr_scan_audit_logs",
        db_column="batch_id",
        blank=True,
        null=True,
    )
    batch_code = models.CharField(max_length=255, blank=True, null=True)
    source = models.CharField(max_length=50)
    device_id = models.CharField(max_length=255, blank=True, null=True)
    client_scan_id = models.CharField(max_length=255, blank=True, null=True)
    scanner_user = models.CharField(max_length=255, blank=True, null=True)
    scanned_at_client = models.DateTimeField(blank=True, null=True)
    scanned_at_server = models.DateTimeField(blank=True, db_default=Now())
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    result_status = models.CharField(max_length=20)
    result_message = models.TextField()
    failure_reason = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "qr_scan_audit_logs"
        indexes = [
            models.Index(fields=["batch", "-scanned_at_server"], name="qr_audit_batch_scan_idx"),
            models.Index(fields=["source", "device_id", "client_scan_id"], name="qr_audit_client_scan_idx"),
            models.Index(fields=["result_status"], name="qr_scan_audit_logs_status_idx"),
        ]
