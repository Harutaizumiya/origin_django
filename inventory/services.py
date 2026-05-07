from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import Q
from django.utils import timezone

from common.exceptions import ConflictApiError, NotFoundApiError
from inventory.expiry import ALERT_EXPIRY_STATUSES, calc_days_until_expiry, calc_expiry_progress, calc_expiry_status
from inventory.models import Batch, BatchOperation, Product


def _raise_conflict(detail: str, exc: Exception) -> None:
    raise ConflictApiError(detail) from exc


class ProductService:
    searchable_fields = ("barcode", "product_name", "category", "location", "unit", "manufacturer")

    @classmethod
    def list_products(cls, *, search: str | None, page: int, size: int):
        try:
            queryset = Product.objects.all().order_by("id")
            if search:
                query = Q()
                for field in cls.searchable_fields:
                    query |= Q(**{f"{field}__icontains": search})
                queryset = queryset.filter(query)

            total = queryset.count()
            offset = (page - 1) * size
            return list(queryset[offset : offset + size]), total
        except DatabaseError as exc:
            _raise_conflict("Unable to list products", exc)

    @staticmethod
    def get_product(product_id: int):
        try:
            return Product.objects.get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise NotFoundApiError(f"Product {product_id} not found") from exc
        except DatabaseError as exc:
            _raise_conflict("Unable to load product", exc)

    @staticmethod
    def get_product_by_barcode(barcode: str):
        try:
            return Product.objects.get(barcode=barcode)
        except Product.DoesNotExist as exc:
            raise NotFoundApiError(f"Product with barcode {barcode} not found") from exc
        except DatabaseError as exc:
            _raise_conflict("Unable to load product", exc)

    @staticmethod
    def create_product(data: dict):
        try:
            with transaction.atomic():
                product = Product.objects.create(**data)
        except IntegrityError as exc:
            raise ConflictApiError("Barcode already exists") from exc
        except DatabaseError as exc:
            _raise_conflict("Unable to create product", exc)
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
            with transaction.atomic():
                product.save(update_fields=list(data.keys()))
        except IntegrityError as exc:
            raise ConflictApiError("Barcode already exists") from exc
        except DatabaseError as exc:
            _raise_conflict("Unable to update product", exc)

        product.refresh_from_db(fields=["updated_at"])
        return product

    @staticmethod
    def delete_product(product_id: int):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise NotFoundApiError(f"Product {product_id} not found") from exc

        deleted_id = product.id
        try:
            with transaction.atomic():
                product.delete()
        except IntegrityError as exc:
            _raise_conflict("Unable to delete product", exc)
        except DatabaseError as exc:
            _raise_conflict("Unable to delete product", exc)
        return {"id": deleted_id}

    @staticmethod
    def list_categories(search: str | None):
        try:
            queryset = Product.objects.exclude(category__isnull=True).exclude(category__exact="")
            if search:
                queryset = queryset.filter(category__icontains=search)
            return list(queryset.order_by("category").values_list("category", flat=True).distinct())
        except DatabaseError as exc:
            _raise_conflict("Unable to list categories", exc)


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
        except DatabaseError as exc:
            _raise_conflict("Unable to load product", exc)

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
            with transaction.atomic():
                batch = Batch.objects.create(**payload)
        except IntegrityError as exc:
            if cls._is_stale_primary_key_sequence_error(exc):
                try:
                    with transaction.atomic():
                        cls._sync_batch_id_sequence()
                        batch = Batch.objects.create(**payload)
                except IntegrityError as retry_exc:
                    raise ConflictApiError("Unable to create batch") from retry_exc
                except DatabaseError as retry_exc:
                    _raise_conflict("Unable to create batch", retry_exc)
            else:
                raise ConflictApiError("Unable to create batch") from exc
        except DatabaseError as exc:
            _raise_conflict("Unable to create batch", exc)
        batch.refresh_from_db(fields=["received_at"])
        return batch

    @staticmethod
    def get_batch(batch_id: int):
        try:
            return Batch.objects.select_related("product").get(pk=batch_id)
        except Batch.DoesNotExist as exc:
            raise NotFoundApiError(f"Batch {batch_id} not found") from exc
        except DatabaseError as exc:
            _raise_conflict("Unable to load batch", exc)

    @classmethod
    def update_batch(cls, batch_id: int, data: dict):
        batch = cls.get_batch(batch_id)
        update_data = dict(data)

        for field, value in update_data.items():
            setattr(batch, field, value)

        try:
            with transaction.atomic():
                batch.save(update_fields=list(update_data.keys()))
        except IntegrityError as exc:
            raise ConflictApiError("Unable to update batch") from exc
        except DatabaseError as exc:
            _raise_conflict("Unable to update batch", exc)
        return batch

    @classmethod
    def update_batch_status(cls, batch_id: int, status: str):
        return cls.update_batch(batch_id, {"status": status})

    @classmethod
    def delete_batch(cls, batch_id: int):
        batch = cls.get_batch(batch_id)
        deleted_id = batch.id
        try:
            with transaction.atomic():
                batch.delete()
        except IntegrityError as exc:
            _raise_conflict("Unable to delete batch", exc)
        except DatabaseError as exc:
            _raise_conflict("Unable to delete batch", exc)
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
        try:
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
        except DatabaseError as exc:
            _raise_conflict("Unable to list batches", exc)

    @staticmethod
    def list_expiry_alerts(
        *,
        product_id: int | None,
        status: str | None,
        category: str | None,
        location: str | None,
        expiry_status: str | None,
        days_lte: int,
        include_expired: bool,
        page: int,
        size: int,
    ):
        try:
            today = timezone.localdate()
            latest_expire_date = today + timedelta(days=days_lte)
            queryset = Batch.objects.select_related("product").exclude(expire_date__isnull=True)

            if product_id:
                queryset = queryset.filter(product_id=product_id)
            if status:
                queryset = queryset.filter(status=status)
            if category:
                queryset = queryset.filter(product__category=category)
            if location:
                queryset = queryset.filter(product__location=location)

            if include_expired:
                queryset = queryset.filter(expire_date__lte=latest_expire_date)
            else:
                queryset = queryset.filter(expire_date__gte=today, expire_date__lte=latest_expire_date)

            batches = list(queryset)
            allowed_statuses = (expiry_status,) if expiry_status else ALERT_EXPIRY_STATUSES
            filtered_batches = [
                batch
                for batch in batches
                if calc_expiry_status(batch.manufacture_date, batch.product.shelf_life_days, today) in allowed_statuses
            ]

            filtered_batches.sort(
                key=lambda batch: (
                    calc_days_until_expiry(batch.expire_date, today) is None,
                    calc_days_until_expiry(batch.expire_date, today) or 0,
                    -(calc_expiry_progress(batch.manufacture_date, batch.product.shelf_life_days, today) or 0),
                    -batch.id,
                )
            )

            total = len(filtered_batches)
            offset = (page - 1) * size
            return filtered_batches[offset : offset + size], total
        except DatabaseError as exc:
            _raise_conflict("Unable to list expiry alerts", exc)


class BatchOperationService:
    decrease_operation_types = {"loss", "deduct"}

    @classmethod
    def create_operation(cls, batch_id: int, data: dict):
        try:
            with transaction.atomic():
                batch = Batch.objects.select_for_update().get(pk=batch_id)
                if batch.quantity is None:
                    raise ConflictApiError("Batch quantity is unavailable")

                quantity = data["quantity"]
                quantity_after = cls._apply_quantity(
                    current_quantity=batch.quantity,
                    operation_type=data["operation_type"],
                    quantity=quantity,
                )
                if quantity_after < Decimal("0"):
                    raise ConflictApiError("Insufficient batch quantity")

                batch.quantity = quantity_after
                batch.save(update_fields=["quantity"])
                operation = BatchOperation.objects.create(
                    batch=batch,
                    operation_type=data["operation_type"],
                    quantity=quantity,
                    quantity_after=quantity_after,
                    remarks=data.get("remarks"),
                )
        except Batch.DoesNotExist as exc:
            raise NotFoundApiError(f"Batch {batch_id} not found") from exc
        except IntegrityError as exc:
            raise ConflictApiError("Unable to create batch operation") from exc
        except DatabaseError as exc:
            _raise_conflict("Unable to create batch operation", exc)

        operation.refresh_from_db(fields=["created_at"])
        return operation, batch

    @classmethod
    def _apply_quantity(cls, *, current_quantity: Decimal, operation_type: str, quantity: Decimal) -> Decimal:
        if operation_type == "add":
            return current_quantity + quantity
        if operation_type in cls.decrease_operation_types:
            return current_quantity - quantity
        raise ConflictApiError("Unsupported batch operation")

    @staticmethod
    def list_operations(*, batch_id: int, operation_type: str | None, page: int, size: int):
        try:
            Batch.objects.only("id").get(pk=batch_id)
            queryset = BatchOperation.objects.filter(batch_id=batch_id).order_by("-created_at", "-id")
            if operation_type:
                queryset = queryset.filter(operation_type=operation_type)

            total = queryset.count()
            offset = (page - 1) * size
            return list(queryset[offset : offset + size]), total
        except Batch.DoesNotExist as exc:
            raise NotFoundApiError(f"Batch {batch_id} not found") from exc
        except DatabaseError as exc:
            _raise_conflict("Unable to list batch operations", exc)
