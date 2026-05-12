from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from common.exceptions import ConflictApiError, NotFoundApiError
from inventory.expiry import ALERT_EXPIRY_STATUSES, calc_days_until_expiry, calc_expiry_progress, calc_expiry_status
from inventory.models import Batch, BatchOperation, BatchQrCredential, Product, QrScanAuditLog


QR_CODE_PREFIX = "OB1"
QR_SCAN_SOURCES = ("web_camera", "mobile_camera", "handheld")

QR_SCAN_STATUS_VALID = "valid"
QR_SCAN_STATUS_NEAR_EXPIRY = "near_expiry"
QR_SCAN_STATUS_EXPIRED = "expired"
QR_SCAN_STATUS_INVALID = "invalid"
QR_SCAN_STATUS_REVOKED = "revoked"
QR_SCAN_STATUS_NOT_FOUND = "not_found"

QR_SCAN_STATUSES = (
    QR_SCAN_STATUS_VALID,
    QR_SCAN_STATUS_NEAR_EXPIRY,
    QR_SCAN_STATUS_EXPIRED,
    QR_SCAN_STATUS_INVALID,
    QR_SCAN_STATUS_REVOKED,
    QR_SCAN_STATUS_NOT_FOUND,
)


def _raise_conflict(detail: str, exc: Exception) -> None:
    raise ConflictApiError(detail) from exc


def _format_date(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _format_decimal(value) -> str | None:
    if value is None:
        return None
    return f"{Decimal(value):.2f}"


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
                QrCredentialService.issue_for_batch(batch)
        except IntegrityError as exc:
            if cls._is_stale_primary_key_sequence_error(exc):
                try:
                    with transaction.atomic():
                        cls._sync_batch_id_sequence()
                        batch = Batch.objects.create(**payload)
                        QrCredentialService.issue_for_batch(batch)
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


class QrCredentialService:
    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(24)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(f"{token}{settings.QR_TOKEN_PEPPER}".encode("utf-8")).hexdigest()

    @staticmethod
    def format_qr_code(batch_code: str, token: str) -> str:
        return f"{QR_CODE_PREFIX}|{batch_code}|{token}"

    @classmethod
    def issue_for_batch(cls, batch: Batch, *, created_by: str | None = None):
        token = cls.generate_token()
        credential = BatchQrCredential.objects.create(
            batch=batch,
            batch_code=batch.batch_code,
            token_hash=cls.hash_token(token),
            created_by=created_by,
        )
        return credential, cls.format_qr_code(batch.batch_code, token)

    @classmethod
    def build_label_payload(cls, batch_id: int) -> dict:
        try:
            batch = Batch.objects.select_related("product").get(pk=batch_id)
            _credential, qr_code = cls.issue_for_batch(batch)
        except Batch.DoesNotExist as exc:
            raise NotFoundApiError(f"Batch {batch_id} not found") from exc
        except DatabaseError as exc:
            _raise_conflict("Unable to build batch label payload", exc)

        return {
            "batchCode": batch.batch_code,
            "productName": batch.product.product_name,
            "barcode": batch.product.barcode,
            "quantity": _format_decimal(batch.quantity),
            "location": batch.product.location,
            "expireDate": _format_date(batch.expire_date),
            "qrCode": qr_code,
        }

    @classmethod
    def backfill_missing_credentials(cls, *, created_by: str | None = "backfill") -> int:
        try:
            active_batch_ids = BatchQrCredential.objects.filter(revoked_at__isnull=True).values_list(
                "batch_id",
                flat=True,
            )
            batches = Batch.objects.exclude(id__in=active_batch_ids)
            count = 0
            with transaction.atomic():
                for batch in batches:
                    cls.issue_for_batch(batch, created_by=created_by)
                    count += 1
            return count
        except DatabaseError as exc:
            _raise_conflict("Unable to backfill batch QR credentials", exc)


class QrScanService:
    pending_message = "pending"

    @classmethod
    def scan_qr(cls, data: dict, context: dict | None = None) -> dict:
        context = context or {}
        try:
            duplicate = cls._find_duplicate(data)
            if duplicate is not None:
                return cls._result_from_audit(duplicate, client_scan_id=data.get("client_scan_id"))

            with transaction.atomic():
                audit = cls._create_audit(data, context)
                result = cls._resolve_scan_result(data["qr"])
                cls._apply_audit_result(audit, result)
        except DatabaseError as exc:
            _raise_conflict("Unable to record QR scan", exc)
        return cls._public_result(result, audit.id, client_scan_id=data.get("client_scan_id"))

    @classmethod
    def scan_bulk(cls, items: list[dict], context: dict | None = None) -> dict:
        return {"items": [cls.scan_qr(item, context) for item in items]}

    @staticmethod
    def _generate_audit_id() -> str:
        return f"scan_{uuid4().hex}"

    @classmethod
    def _find_duplicate(cls, data: dict):
        client_scan_id = data.get("client_scan_id")
        if not client_scan_id:
            return None
        return (
            QrScanAuditLog.objects.filter(
                source=data["source"],
                device_id=data.get("device_id"),
                client_scan_id=client_scan_id,
            )
            .order_by("scanned_at_server", "id")
            .first()
        )

    @classmethod
    def _create_audit(cls, data: dict, context: dict):
        return QrScanAuditLog.objects.create(
            id=cls._generate_audit_id(),
            raw_qr=data["qr"],
            source=data["source"],
            device_id=data.get("device_id"),
            client_scan_id=data.get("client_scan_id"),
            scanner_user=context.get("scanner_user"),
            scanned_at_client=data.get("scanned_at"),
            scanned_at_server=timezone.now(),
            ip_address=context.get("ip_address"),
            user_agent=context.get("user_agent"),
            result_status=QR_SCAN_STATUS_INVALID,
            result_message=cls.pending_message,
        )

    @classmethod
    def _resolve_scan_result(cls, qr: str) -> dict:
        parsed = cls._parse_qr(qr)
        if parsed is None:
            return cls._result(
                status=QR_SCAN_STATUS_INVALID,
                message="二维码格式错误",
                failure_reason="invalid_format",
            )

        batch_code, token = parsed
        token_hash = QrCredentialService.hash_token(token)
        credential = (
            BatchQrCredential.objects.filter(batch_code=batch_code, token_hash=token_hash)
            .order_by("-issued_at", "-id")
            .first()
        )
        if credential is None:
            return cls._result(
                status=QR_SCAN_STATUS_INVALID,
                message="二维码无效",
                batch_code=batch_code,
                failure_reason="token_mismatch",
            )

        if credential.revoked_at is not None:
            return cls._result(
                status=QR_SCAN_STATUS_REVOKED,
                message="二维码已吊销",
                batch_code=credential.batch_code,
                batch_id=credential.batch_id,
                failure_reason="credential_revoked",
            )

        try:
            batch = Batch.objects.select_related("product").get(pk=credential.batch_id)
        except Batch.DoesNotExist:
            return cls._result(
                status=QR_SCAN_STATUS_NOT_FOUND,
                message="批次不存在",
                batch_code=credential.batch_code,
                batch_id=credential.batch_id,
                failure_reason="batch_not_found",
            )

        return cls._result_for_batch(batch)

    @staticmethod
    def _parse_qr(qr: str) -> tuple[str, str] | None:
        parts = qr.split("|")
        if len(parts) != 3:
            return None
        prefix, batch_code, token = parts
        if prefix != QR_CODE_PREFIX or not batch_code or not token:
            return None
        return batch_code, token

    @classmethod
    def _result_for_batch(cls, batch: Batch) -> dict:
        remaining_days = calc_days_until_expiry(batch.expire_date)
        if remaining_days is None:
            status = QR_SCAN_STATUS_VALID
            message = "该批次未设置到期日"
        elif remaining_days < 0:
            status = QR_SCAN_STATUS_EXPIRED
            message = "该批次已过期"
        elif remaining_days <= settings.QR_SCAN_NEAR_EXPIRY_DAYS:
            status = QR_SCAN_STATUS_NEAR_EXPIRY
            message = "该批次临近到期"
        else:
            status = QR_SCAN_STATUS_VALID
            message = "该批次仍在效期内"

        return cls._result(
            status=status,
            message=message,
            batch_code=batch.batch_code,
            batch_id=batch.id,
            product_name=batch.product.product_name,
            expire_date=batch.expire_date,
            remaining_days=remaining_days,
        )

    @staticmethod
    def _result(
        *,
        status: str,
        message: str,
        batch_code: str | None = None,
        batch_id: int | None = None,
        product_name: str | None = None,
        expire_date=None,
        remaining_days: int | None = None,
        failure_reason: str | None = None,
    ) -> dict:
        return {
            "batchCode": batch_code,
            "productName": product_name,
            "status": status,
            "message": message,
            "expireDate": _format_date(expire_date),
            "remainingDays": remaining_days,
            "_batch_id": batch_id,
            "_failure_reason": failure_reason,
        }

    @staticmethod
    def _public_result(result: dict, audit_id: str, *, client_scan_id: str | None = None) -> dict:
        payload = {
            "auditId": audit_id,
            "batchCode": result.get("batchCode"),
            "productName": result.get("productName"),
            "status": result["status"],
            "message": result["message"],
            "expireDate": result.get("expireDate"),
            "remainingDays": result.get("remainingDays"),
        }
        if client_scan_id:
            payload["clientScanId"] = client_scan_id
        return payload

    @classmethod
    def _apply_audit_result(cls, audit, result: dict) -> None:
        audit.batch_id = result.get("_batch_id")
        audit.batch_code = result.get("batchCode")
        audit.result_status = result["status"]
        audit.result_message = result["message"]
        audit.failure_reason = result.get("_failure_reason")
        audit.save(
            update_fields=[
                "batch_id",
                "batch_code",
                "result_status",
                "result_message",
                "failure_reason",
            ]
        )

    @classmethod
    def _result_from_audit(cls, audit, *, client_scan_id: str | None = None) -> dict:
        product_name = None
        expire_date = None
        remaining_days = None
        if audit.batch_id is not None:
            try:
                batch = Batch.objects.select_related("product").get(pk=audit.batch_id)
            except Batch.DoesNotExist:
                batch = None
            if batch is not None:
                product_name = batch.product.product_name
                expire_date = _format_date(batch.expire_date)
                remaining_days = calc_days_until_expiry(batch.expire_date)

        result = {
            "batchCode": audit.batch_code,
            "productName": product_name,
            "status": audit.result_status,
            "message": audit.result_message,
            "expireDate": expire_date,
            "remainingDays": remaining_days,
        }
        return cls._public_result(result, audit.id, client_scan_id=client_scan_id)


class BatchOperationService:
    decrease_operation_types = {"loss", "deduct"}
    reverse_operation_types = {
        "add": "deduct",
        "loss": "add",
        "deduct": "add",
    }

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

                update_fields = cls._apply_batch_quantity_state(batch, quantity_after)
                batch.quantity = quantity_after
                batch.save(update_fields=update_fields)
                operation = BatchOperation.objects.create(
                    batch=batch,
                    reversed_operation=data.get("reversed_operation"),
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
    def revert_operation(cls, *, batch_id: int, operation_id: int, data: dict):
        try:
            with transaction.atomic():
                original_operation = BatchOperation.objects.select_for_update().get(pk=operation_id, batch_id=batch_id)
                if original_operation.reversed_operation_id is not None:
                    raise ConflictApiError("Reversal operation cannot be reverted")
                if BatchOperation.objects.filter(reversed_operation_id=original_operation.id).exists():
                    raise ConflictApiError("Batch operation has already been reverted")

                batch = Batch.objects.select_for_update().get(pk=batch_id)
                if batch.quantity is None:
                    raise ConflictApiError("Batch quantity is unavailable")

                operation_type = cls.reverse_operation_types[original_operation.operation_type]
                quantity_after = cls._apply_quantity(
                    current_quantity=batch.quantity,
                    operation_type=operation_type,
                    quantity=original_operation.quantity,
                )
                if quantity_after < Decimal("0"):
                    raise ConflictApiError("Insufficient batch quantity")

                update_fields = cls._apply_batch_quantity_state(batch, quantity_after)
                batch.quantity = quantity_after
                batch.save(update_fields=update_fields)
                reversal_operation = BatchOperation.objects.create(
                    batch=batch,
                    reversed_operation=original_operation,
                    operation_type=operation_type,
                    quantity=original_operation.quantity,
                    quantity_after=quantity_after,
                    remarks=data.get("remarks"),
                )
        except BatchOperation.DoesNotExist as exc:
            raise NotFoundApiError(f"Batch operation {operation_id} not found") from exc
        except IntegrityError as exc:
            raise ConflictApiError("Batch operation has already been reverted") from exc
        except DatabaseError as exc:
            _raise_conflict("Unable to revert batch operation", exc)

        reversal_operation.refresh_from_db(fields=["created_at"])
        return reversal_operation, batch

    @classmethod
    def _apply_quantity(cls, *, current_quantity: Decimal, operation_type: str, quantity: Decimal) -> Decimal:
        if operation_type == "add":
            return current_quantity + quantity
        if operation_type in cls.decrease_operation_types:
            return current_quantity - quantity
        raise ConflictApiError("Unsupported batch operation")

    @staticmethod
    def _apply_batch_quantity_state(batch: Batch, quantity_after: Decimal) -> list[str]:
        update_fields = ["quantity"]
        if quantity_after == Decimal("0"):
            if batch.status != "used_up":
                batch.status = "used_up"
                update_fields.append("status")
        elif batch.status == "used_up":
            batch.status = None
            update_fields.append("status")
        return update_fields

    @staticmethod
    def list_operations(*, batch_id: int, operation_type: str | None, page: int, size: int):
        try:
            Batch.objects.only("id").get(pk=batch_id)
            reversal_queryset = BatchOperation.objects.filter(reversed_operation_id=OuterRef("pk"))
            queryset = (
                BatchOperation.objects.filter(batch_id=batch_id)
                .annotate(is_reverted=Exists(reversal_queryset))
                .order_by("-created_at", "-id")
            )
            if operation_type:
                queryset = queryset.filter(operation_type=operation_type)

            total = queryset.count()
            offset = (page - 1) * size
            return list(queryset[offset : offset + size]), total
        except Batch.DoesNotExist as exc:
            raise NotFoundApiError(f"Batch {batch_id} not found") from exc
        except DatabaseError as exc:
            _raise_conflict("Unable to list batch operations", exc)
