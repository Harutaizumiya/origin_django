from django.db import models


class Product(models.Model):
    id = models.BigAutoField(primary_key=True)
    barcode = models.CharField(max_length=255, unique=True)
    product_name = models.CharField(max_length=255)
    shelf_life_days = models.IntegerField()
    location = models.CharField(max_length=255, blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)
    unit = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    manufacturer = models.TextField()

    class Meta:
        managed = False
        db_table = "product"


class Batch(models.Model):
    id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.DO_NOTHING, related_name="batches", db_column="product_id")
    batch_code = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    received_date = models.DateTimeField(blank=True, null=True)
    manufacture_date = models.DateField(blank=True, null=True)
    expire_date = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=255, blank=True, null=True)
    remarks = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "batches"
