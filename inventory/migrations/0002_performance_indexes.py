from django.db import migrations


INDEX_STATEMENTS = {
    "product": [
        "CREATE INDEX IF NOT EXISTS product_category_idx ON product(category)",
    ],
    "batches": [
        "CREATE INDEX IF NOT EXISTS batches_product_id_idx ON batches(product_id)",
        "CREATE INDEX IF NOT EXISTS batches_status_idx ON batches(status)",
        "CREATE INDEX IF NOT EXISTS batches_expire_date_idx ON batches(expire_date)",
        "CREATE INDEX IF NOT EXISTS batches_received_at_id_idx ON batches(received_at DESC, id DESC)",
    ],
    "batch_operations": [
        "CREATE INDEX IF NOT EXISTS batch_ops_batch_created_idx ON batch_operations(batch_id, created_at DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS batch_operations_type_idx ON batch_operations(operation_type)",
    ],
    "batch_qr_credentials": [
        "CREATE INDEX IF NOT EXISTS batch_qr_batch_rev_idx ON batch_qr_credentials(batch_id, revoked_at)",
        "CREATE INDEX IF NOT EXISTS batch_qr_credentials_code_idx ON batch_qr_credentials(batch_code)",
    ],
    "qr_scan_audit_logs": [
        "CREATE INDEX IF NOT EXISTS qr_audit_batch_scan_idx ON qr_scan_audit_logs(batch_id, scanned_at_server DESC)",
        "CREATE INDEX IF NOT EXISTS qr_audit_client_scan_idx ON qr_scan_audit_logs(source, device_id, client_scan_id)",
        "CREATE INDEX IF NOT EXISTS qr_scan_audit_logs_status_idx ON qr_scan_audit_logs(result_status)",
    ],
}

DROP_STATEMENTS = [
    "DROP INDEX IF EXISTS qr_scan_audit_logs_status_idx",
    "DROP INDEX IF EXISTS qr_audit_client_scan_idx",
    "DROP INDEX IF EXISTS qr_audit_batch_scan_idx",
    "DROP INDEX IF EXISTS batch_qr_credentials_code_idx",
    "DROP INDEX IF EXISTS batch_qr_batch_rev_idx",
    "DROP INDEX IF EXISTS batch_operations_type_idx",
    "DROP INDEX IF EXISTS batch_ops_batch_created_idx",
    "DROP INDEX IF EXISTS batches_received_at_id_idx",
    "DROP INDEX IF EXISTS batches_expire_date_idx",
    "DROP INDEX IF EXISTS batches_status_idx",
    "DROP INDEX IF EXISTS batches_product_id_idx",
    "DROP INDEX IF EXISTS product_category_idx",
]


def add_performance_indexes(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())
    with schema_editor.connection.cursor() as cursor:
        for table, statements in INDEX_STATEMENTS.items():
            if table not in existing_tables:
                continue
            for statement in statements:
                cursor.execute(statement)


def remove_performance_indexes(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for statement in DROP_STATEMENTS:
            cursor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_actor_audit"),
    ]

    operations = [
        migrations.RunPython(add_performance_indexes, reverse_code=remove_performance_indexes),
    ]
