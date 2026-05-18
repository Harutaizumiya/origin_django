from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.db.models.functions.datetime
import django.utils.timezone


def add_actor_columns(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())
    statements = []
    if "batch_operations" in existing_tables:
        statements.extend(
            [
                "ALTER TABLE batch_operations ADD COLUMN IF NOT EXISTS operator_id integer REFERENCES auth_user(id)",
                "CREATE INDEX IF NOT EXISTS batch_ops_operator_idx ON batch_operations(operator_id)",
            ]
        )
    if "qr_scan_audit_logs" in existing_tables:
        statements.extend(
            [
                "ALTER TABLE qr_scan_audit_logs ADD COLUMN IF NOT EXISTS scanner_user_id integer REFERENCES auth_user(id)",
                "CREATE INDEX IF NOT EXISTS qr_audit_scanner_idx ON qr_scan_audit_logs(scanner_user_id)",
            ]
        )
    if not statements:
        return
    with schema_editor.connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def remove_actor_columns(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())
    statements = []
    if "qr_scan_audit_logs" in existing_tables:
        statements.extend(
            [
                "DROP INDEX IF EXISTS qr_audit_scanner_idx",
                "ALTER TABLE qr_scan_audit_logs DROP COLUMN IF EXISTS scanner_user_id",
            ]
        )
    if "batch_operations" in existing_tables:
        statements.extend(
            [
                "DROP INDEX IF EXISTS batch_ops_operator_idx",
                "ALTER TABLE batch_operations DROP COLUMN IF EXISTS operator_id",
            ]
        )
    if not statements:
        return
    with schema_editor.connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("barcode", models.CharField(max_length=255, unique=True)),
                ("product_name", models.CharField(max_length=255)),
                ("shelf_life_days", models.IntegerField()),
                ("location", models.CharField(blank=True, max_length=255, null=True)),
                ("category", models.CharField(blank=True, max_length=255, null=True)),
                ("unit", models.CharField(blank=True, max_length=255, null=True)),
                ("created_at", models.DateTimeField(blank=True, db_default=django.db.models.functions.datetime.Now())),
                ("updated_at", models.DateTimeField(blank=True, db_default=django.db.models.functions.datetime.Now())),
                ("manufacturer", models.TextField()),
            ],
            options={
                "db_table": "product",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="Batch",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("batch_code", models.CharField(max_length=255)),
                ("quantity", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("received_at", models.DateTimeField(blank=True, db_default=django.db.models.functions.datetime.Now())),
                ("manufacture_date", models.DateField(blank=True, null=True)),
                ("expire_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(blank=True, max_length=255, null=True)),
                ("remarks", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "product",
                    models.ForeignKey(
                        db_column="product_id",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="batches",
                        to="inventory.product",
                    ),
                ),
            ],
            options={
                "db_table": "batches",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="BatchOperation",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("operation_type", models.CharField(max_length=20)),
                ("quantity", models.DecimalField(decimal_places=2, max_digits=12)),
                ("quantity_after", models.DecimalField(decimal_places=2, max_digits=12)),
                ("remarks", models.CharField(blank=True, max_length=255, null=True)),
                ("created_at", models.DateTimeField(blank=True, db_default=django.db.models.functions.datetime.Now())),
                (
                    "batch",
                    models.ForeignKey(
                        db_column="batch_id",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="operations",
                        to="inventory.batch",
                    ),
                ),
                (
                    "operator",
                    models.ForeignKey(
                        blank=True,
                        db_column="operator_id",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="batch_operations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reversed_operation",
                    models.ForeignKey(
                        blank=True,
                        db_column="reversed_operation_id",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="reversal_operations",
                        to="inventory.batchoperation",
                    ),
                ),
            ],
            options={
                "db_table": "batch_operations",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="BatchQrCredential",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("batch_code", models.CharField(max_length=255)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("issued_at", models.DateTimeField(blank=True, db_default=django.db.models.functions.datetime.Now())),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "batch",
                    models.ForeignKey(
                        db_column="batch_id",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="qr_credentials",
                        to="inventory.batch",
                    ),
                ),
            ],
            options={
                "db_table": "batch_qr_credentials",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="QrScanAuditLog",
            fields=[
                ("id", models.CharField(max_length=40, primary_key=True, serialize=False)),
                ("raw_qr", models.TextField()),
                ("batch_code", models.CharField(blank=True, max_length=255, null=True)),
                ("source", models.CharField(max_length=50)),
                ("device_id", models.CharField(blank=True, max_length=255, null=True)),
                ("client_scan_id", models.CharField(blank=True, max_length=255, null=True)),
                ("scanner_user", models.CharField(blank=True, max_length=255, null=True)),
                ("scanned_at_client", models.DateTimeField(blank=True, null=True)),
                ("scanned_at_server", models.DateTimeField(blank=True, db_default=django.db.models.functions.datetime.Now())),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, null=True)),
                ("result_status", models.CharField(max_length=20)),
                ("result_message", models.TextField()),
                ("failure_reason", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "batch",
                    models.ForeignKey(
                        blank=True,
                        db_column="batch_id",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="qr_scan_audit_logs",
                        to="inventory.batch",
                    ),
                ),
                (
                    "scanner_user_account",
                    models.ForeignKey(
                        blank=True,
                        db_column="scanner_user_id",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="qr_scan_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "qr_scan_audit_logs",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="InventoryAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("resource_type", models.CharField(max_length=50)),
                ("resource_id", models.CharField(max_length=64)),
                ("action", models.CharField(max_length=50)),
                ("snapshot", models.JSONField()),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="inventory_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "inventory_audit_logs",
            },
        ),
        migrations.AddIndex(
            model_name="inventoryauditlog",
            index=models.Index(fields=["resource_type", "resource_id", "-created_at"], name="inv_audit_resource_idx"),
        ),
        migrations.AddIndex(
            model_name="inventoryauditlog",
            index=models.Index(fields=["actor", "-created_at"], name="inv_audit_actor_idx"),
        ),
        migrations.AddIndex(
            model_name="inventoryauditlog",
            index=models.Index(fields=["action"], name="inv_audit_action_idx"),
        ),
        migrations.RunPython(add_actor_columns, reverse_code=remove_actor_columns),
    ]
