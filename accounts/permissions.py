from __future__ import annotations

from dataclasses import dataclass

from rest_framework.permissions import BasePermission


@dataclass(frozen=True)
class ComponentPermissionItem:
    code: str
    name: str
    component: str
    action: str
    description: str


COMPONENT_PERMISSIONS: tuple[ComponentPermissionItem, ...] = (
    ComponentPermissionItem("products_read", "查看商品", "products", "read", "查看商品列表、详情、条码查询和分类"),
    ComponentPermissionItem("products_create", "创建商品", "products", "create", "创建商品主数据"),
    ComponentPermissionItem("products_update", "更新商品", "products", "update", "更新商品主数据"),
    ComponentPermissionItem("products_delete", "删除商品", "products", "delete", "删除商品主数据"),
    ComponentPermissionItem("batches_read", "查看批次", "batches", "read", "查看批次列表、详情和效期预警"),
    ComponentPermissionItem("batches_create", "创建批次", "batches", "create", "创建批次"),
    ComponentPermissionItem("batches_update", "更新批次", "batches", "update", "更新批次资料和状态"),
    ComponentPermissionItem("batches_delete", "删除批次", "batches", "delete", "删除批次"),
    ComponentPermissionItem(
        "batch_operations_read",
        "查看库存操作",
        "batch_operations",
        "read",
        "查看批次库存操作记录",
    ),
    ComponentPermissionItem("batch_operations_add", "库存入库", "batch_operations", "add", "创建入库操作"),
    ComponentPermissionItem("batch_operations_deduct", "库存出库", "batch_operations", "deduct", "创建出库操作"),
    ComponentPermissionItem("batch_operations_loss", "库存报损", "batch_operations", "loss", "创建报损操作"),
    ComponentPermissionItem(
        "batch_operations_revert",
        "撤销库存操作",
        "batch_operations",
        "revert",
        "撤销库存操作并创建反向记录",
    ),
    ComponentPermissionItem(
        "label_payload_issue",
        "签发二维码凭证",
        "label_payload",
        "issue",
        "签发可打印二维码凭证",
    ),
    ComponentPermissionItem("qr_scans_create", "扫码审计", "qr_scans", "create", "提交单条或批量扫码审计"),
    ComponentPermissionItem("dashboard_read", "查看看板", "dashboard", "read", "查看库存看板概览"),
    ComponentPermissionItem("analytics_read", "查看分析", "analytics", "read", "查看库存分析汇总"),
)

COMPONENT_PERMISSION_CODES = frozenset(item.code for item in COMPONENT_PERMISSIONS)
PERMISSION_APP_LABEL = "accounts"
PERMISSION_CONTENT_TYPE_MODEL = "componentpermission"


def catalog_as_dicts() -> list[dict]:
    return [
        {
            "code": item.code,
            "name": item.name,
            "component": item.component,
            "action": item.action,
            "description": item.description,
        }
        for item in COMPONENT_PERMISSIONS
    ]


class ComponentPermission(BasePermission):
    message = "forbidden"

    def has_permission(self, request, view) -> bool:
        required_permission = self._required_permission(request, view)
        if required_permission is None:
            return True

        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False):
            return True

        from accounts.services import PermissionService

        return PermissionService.user_has_permission(user, required_permission)

    @staticmethod
    def _required_permission(request, view) -> str | None:
        resolver = getattr(view, "get_required_permission", None)
        if callable(resolver):
            return resolver(request)

        permission_map = getattr(view, "permission_map", {})
        value = permission_map.get(request.method)
        if isinstance(value, str) or value is None:
            return value
        if callable(value):
            return value(request)
        return None


class SuperAdminPermission(BasePermission):
    message = "forbidden"

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user is not None and getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False))
