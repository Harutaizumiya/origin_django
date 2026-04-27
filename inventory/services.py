from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

from django.db import IntegrityError, connection
from django.db.models import Q
from django.utils import timezone

from common.exceptions import ConflictApiError, NotFoundApiError
from inventory.models import Batch, Product


class ProductService:
    searchable_fields = ("barcode", "product_name", "category", "location", "unit", "manufacturer")

    @classmethod
    def list_products(cls, *, search: str | None, page: int, size: int):
        queryset = Product.objects.all().order_by("id")
        if search:
            query = Q()
            for field in cls.searchable_fields:
                query |= Q(**{f"{field}__icontains": search})
            queryset = queryset.filter(query)

        total = queryset.count()
        offset = (page - 1) * size
        return list(queryset[offset : offset + size]), total

    @staticmethod
    def get_product(product_id: int):
        try:
            return Product.objects.get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise NotFoundApiError(f"Product {product_id} not found") from exc

    @staticmethod
    def get_product_by_barcode(barcode: str):
        try:
            return Product.objects.get(barcode=barcode)
        except Product.DoesNotExist as exc:
            raise NotFoundApiError(f"Product with barcode {barcode} not found") from exc

    @staticmethod
    def create_product(data: dict):
        try:
            product = Product.objects.create(**data)
        except IntegrityError as exc:
            raise ConflictApiError("Barcode already exists") from exc
        product.refresh_from_db(fields=["created_at", "updated_at"])
        return product

    @staticmethod
    def update_product(product_id: int, data: dict):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise NotFoundApiError(f"Product {product_id} not found") from exc

        for field, value in data.items():
            setattr(product, field, value)

        try:
            product.save(update_fields=list(data.keys()))
        except IntegrityError as exc:
            raise ConflictApiError("Barcode already exists") from exc

        product.refresh_from_db(fields=["updated_at"])
        return product

    @staticmethod
    def delete_product(product_id: int):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise NotFoundApiError(f"Product {product_id} not found") from exc

        deleted_id = product.id
        product.delete()
        return {"id": deleted_id}

    @staticmethod
    def list_categories(search: str | None):
        queryset = Product.objects.exclude(category__isnull=True).exclude(category__exact="")
        if search:
            queryset = queryset.filter(category__icontains=search)
        return list(queryset.order_by("category").values_list("category", flat=True).distinct())


class BatchService:
    @staticmethod
    def _generate_batch_code() -> str:
        return f"BATCH-{datetime.now().strftime('%Y%m%d')}-{uuid4().hex[:8]}"

    @classmethod
    def create_batch(cls, data: dict):
        try:
            product = Product.objects.get(pk=data["product_id"])
        except Product.DoesNotExist as exc:
            raise NotFoundApiError(f"Product {data['product_id']} not found") from exc

        expire_date = data.get("expire_date")
        if expire_date is None:
            expire_date = data["manufacture_date"] + timedelta(days=product.shelf_life_days)

        payload = {
            "product": product,
            "batch_code": data.get("batch_code") or cls._generate_batch_code(),
            "quantity": data["quantity"],
            "manufacture_date": data["manufacture_date"],
            "expire_date": expire_date,
            "status": data.get("status", "unopened"),
            "remarks": data.get("remarks"),
        }
        try:
            batch = Batch.objects.create(**payload)
        except IntegrityError as exc:
            if cls._is_stale_primary_key_sequence_error(exc):
                cls._sync_batch_id_sequence()
                try:
                    batch = Batch.objects.create(**payload)
                except IntegrityError as retry_exc:
                    raise ConflictApiError("Unable to create batch") from retry_exc
            else:
                raise ConflictApiError("Unable to create batch") from exc
        batch.refresh_from_db(fields=["received_at"])
        return batch

    @staticmethod
    def get_batch(batch_id: int):
        try:
            return Batch.objects.select_related("product").get(pk=batch_id)
        except Batch.DoesNotExist as exc:
            raise NotFoundApiError(f"Batch {batch_id} not found") from exc

    @classmethod
    def update_batch(cls, batch_id: int, data: dict):
        batch = cls.get_batch(batch_id)
        update_data = dict(data)

        for field, value in update_data.items():
            setattr(batch, field, value)

        try:
            batch.save(update_fields=list(update_data.keys()))
        except IntegrityError as exc:
            raise ConflictApiError("Unable to update batch") from exc
        return batch

    @classmethod
    def update_batch_status(cls, batch_id: int, status: str):
        return cls.update_batch(batch_id, {"status": status})

    @classmethod
    def delete_batch(cls, batch_id: int):
        batch = cls.get_batch(batch_id)
        deleted_id = batch.id
        batch.delete()
        return {"id": deleted_id}

    @staticmethod
    def _is_stale_primary_key_sequence_error(exc: IntegrityError) -> bool:
        message = str(exc)
        return 'duplicate key value violates unique constraint "batches_pkey"' in message

    @staticmethod
    def _sync_batch_id_sequence() -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT setval(
                    pg_get_serial_sequence('public.batches', 'id'),
                    COALESCE((SELECT MAX(id) FROM public.batches), 0),
                    true
                )
                """
            )

    @staticmethod
    def list_batches(*, product_id: int | None, status: str | None, expired_only: bool, page: int, size: int):
        queryset = Batch.objects.select_related("product").all().order_by("-received_at", "-id")
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if status:
            queryset = queryset.filter(status=status)
        if expired_only:
            queryset = queryset.filter(expire_date__lt=timezone.localdate())

        total = queryset.count()
        offset = (page - 1) * size
        return list(queryset[offset : offset + size]), total
