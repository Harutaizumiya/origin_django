# API 文档

本文档定义当前项目的目标 API 契约。后端实现必须与本文档保持同步；如实现与文档不一致，以本文档为准并同步修正代码。

## 基础信息

- Base URL：`<BASE_URL>/api`
- 本地开发示例：`http://127.0.0.1:8000/api`
- Content-Type：`application/json`

## 认证说明

- 当前除首页 `/` 和认证接口外，业务 API 均要求登录。
- 统一使用请求头：`Authorization: Bearer <token>`。
- token 为不含业务含义的 opaque 字符串；客户端不得解析 token 内容。
- 登录 token 默认 8 小时过期，`expires_in = 28800`；登录请求传 `remember_me = true` 时延长为 3 天，`expires_in = 259200`。暂不提供 refresh token。
- `POST /auth/logout` 只吊销当前请求携带的 token；多设备登录允许多个未过期 token 并存。
- 商品、批次、库存操作和扫码审计会记录当前登录用户；当前响应体暂不返回操作者字段。
- 业务 API 使用组件级权限控制；`is_superuser=true` 自动拥有全部权限。
- 超级管理员可通过 `/auth/permissions`、`/auth/roles`、`/auth/users` 配置角色、权限和用户授权。

## 统一响应结构

### 成功响应

- HTTP 状态码：`200` / `201`
- 响应体：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 列表响应

- `data.items`：列表数据
- `data.pagination`：分页信息
- 非分页列表接口返回 `pagination: null`

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "size": 20,
      "total": 0
    }
  }
}
```

### 错误响应

- HTTP 状态码：`400` / `401` / `403` / `404` / `409`
- `code`：业务整数码
- `message`：稳定英文标识
- `data`：固定为 `null`

```json
{
  "code": 4001,
  "message": "validation_error",
  "data": null
}
```

### 错误码定义

| HTTP 状态码 | 业务码 | message |
| --- | ---: | --- |
| `400` | `4001` | `validation_error` |
| `401` | `4011` | `unauthenticated` |
| `403` | `4031` | `forbidden` |
| `404` | `4041` | `not_found` |
| `409` | `4091` | `conflict` |

## 公共字段约定

- `created_at` / `updated_at` / `received_at`：ISO 8601 时间点
- `manufacture_date` / `expire_date`：`YYYY-MM-DD`
- `quantity`：响应统一为字符串；数据库类型为 `numeric(12,2)`；示例 `"8.50"`
- `status`：当前仅定义以下枚举值：
  - `unopened`
  - `opened`
  - `used_up`

## 复用 Schema

### AuthUser

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 用户 ID |
| `username` | string | 登录用户名 |
| `email` | string | 邮箱，可为空字符串 |
| `first_name` | string | 名，可为空字符串 |
| `last_name` | string | 姓，可为空字符串 |
| `is_staff` | boolean | 是否 staff 用户 |
| `is_superuser` | boolean | 是否超级用户 |
| `permissions` | string[] | 当前用户有效业务权限码；超级管理员返回全部权限码 |

### AuthAdminUser

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 用户 ID |
| `username` | string | 登录用户名 |
| `email` | string | 邮箱，可为空字符串 |
| `first_name` | string | 名，可为空字符串 |
| `last_name` | string | 姓，可为空字符串 |
| `is_active` | boolean | 是否启用 |
| `is_staff` | boolean | 是否 staff 用户 |
| `is_superuser` | boolean | 是否超级用户；不能通过用户管理 API 设置 |
| `groups` | AuthRole[] | 已分配角色 |
| `direct_permissions` | string[] | 直接分配给用户的权限码 |
| `effective_permissions` | string[] | 角色权限和直接权限合并后的有效权限码 |

### AuthRole

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | Django Group ID |
| `name` | string | 角色名称 |
| `permissions` | string[] | 角色拥有的权限码 |

### AuthLoginResult

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `token` | string | Bearer token 明文，只在登录响应返回 |
| `token_type` | string | 固定为 `Bearer` |
| `expires_in` | integer | token 有效秒数；默认 `28800`，`remember_me=true` 时为 `259200` |
| `expires_at` | string | token 到期时间，ISO 8601 时间点 |
| `user` | AuthUser | 当前登录用户 |

### Product

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 商品 ID |
| `barcode` | string | 商品条码 |
| `product_name` | string | 商品名称 |
| `shelf_life_days` | integer | 保质期天数 |
| `location` | string \| null | 存放位置 |
| `category` | string \| null | 分类 |
| `unit` | string \| null | 单位 |
| `manufacturer` | string | 厂商 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### ProductSummary

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 商品 ID |
| `barcode` | string | 商品条码 |
| `product_name` | string | 商品名称 |
| `unit` | string \| null | 单位 |
| `manufacturer` | string | 厂商 |

### Batch

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 批次 ID |
| `product_id` | integer | 关联商品 ID |
| `batch_code` | string | 批次号 |
| `quantity` | string | 数量，定点十进制字符串 |
| `received_at` | string | 入库时间 |
| `manufacture_date` | string \| null | 生产日期 |
| `expire_date` | string \| null | 到期日期 |
| `status` | string \| null | 批次状态 |
| `remarks` | string \| null | 备注 |
| `product` | ProductSummary | 商品摘要 |

### BatchOperation

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 操作记录 ID |
| `batch_id` | integer | 关联批次 ID |
| `operation_type` | string | 操作类型：`add`、`loss`、`deduct` |
| `quantity` | string | 本次操作数量，始终为正数 |
| `quantity_after` | string | 操作完成后的批次数量快照 |
| `remarks` | string \| null | 备注 |
| `created_at` | string | 操作时间 |
| `reversed_operation_id` | integer \| null | 被撤销的原操作 ID；普通操作为 `null` |
| `is_reverted` | boolean | 当前操作是否已经被撤销 |

### DashboardOverview

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `current_inventory_quantity` | string | 当前在库总数量，只统计 `quantity > 0` 且 `status != used_up` 的批次 |
| `near_expiry_batch_count` | integer | 7 天内临期批次数，按 `0 <= days_until_expiry <= 7` 统计 |
| `expired_batch_count` | integer | 已过期批次数，按 `days_until_expiry < 0` 或 `expiry_status = expired` 统计 |
| `batch_health_rate` | number | 批次健康率，健康批次数 / 当前在库批次数，保留 4 位小数；无在库批次时为 `1.0` |
| `expiry_trend_30d` | ExpiryTrendPoint[] | 未来 30 天到期趋势，含今日和第 30 天 |
| `category_inventory_distribution` | CategoryInventoryDistribution[] | 品类在库分布 |
| `top_near_expiry_batches` | Batch[] | Top 5 临期批次，按剩余天数升序排序 |

### ExpiryTrendPoint

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | string | 日期，`YYYY-MM-DD` |
| `batch_count` | integer | 当天到期批次数 |
| `quantity` | string | 当天到期批次当前在库数量 |

### CategoryInventoryDistribution

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `category` | string | 商品分类；空分类统一返回 `未分类` |
| `batch_count` | integer | 当前在库批次数 |
| `quantity` | string | 当前在库数量 |
| `ratio` | number | 该品类数量占当前在库总数量比例，保留 4 位小数 |

### AnalyticsSummary

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `range` | string | 汇总范围，当前支持 `1m`、`3m`、`6m`、`12m` |
| `period` | object | 统计周期，`start` 为起始月份 1 日，`end` 为服务端当前日期 |
| `inventory_change_count` | integer | 库存变动次数，按有效 `batch_operations` 统计 |
| `current_month_loss_quantity` | string | 当月报损数量，按有效 `loss` 操作数量汇总 |
| `average_stock_age_days` | number \| null | 当前在库批次平均库龄，按 `received_at` 到当前日期的批次平均计算 |
| `monthly_inventory_loss_trend` | MonthlyInventoryLossTrend[] | 月度在库数量/报损数量趋势 |
| `category_operation_summary` | CategoryOperationSummary[] | 品类入库与出库/报损操作量 |
| `high_risk_inventory_ranking` | Batch[] | 高风险库存排行，最多 10 条 |

### MonthlyInventoryLossTrend

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `month` | string | 月份，`YYYY-MM` |
| `inventory_quantity` | string | 当前在库批次按 `received_at` 所属月份汇总的数量 |
| `loss_quantity` | string | 当月有效报损数量 |

### CategoryOperationSummary

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `category` | string | 商品分类；空分类统一返回 `未分类` |
| `inbound_quantity` | string | 有效 `add` 操作数量 |
| `outbound_loss_quantity` | string | 有效 `deduct + loss` 操作数量 |
| `operation_count` | integer | 该品类有效操作次数 |

### BatchQuantitySummary

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 批次 ID |
| `quantity` | string | 当前批次数量 |
| `status` | string \| null | 当前批次状态 |

### BatchLabelPayload

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `batchCode` | string | 批次号 |
| `productName` | string | 商品名称 |
| `barcode` | string | 商品条码 |
| `quantity` | string \| null | 批次数量 |
| `location` | string \| null | 商品存放位置 |
| `expireDate` | string \| null | 到期日期，`YYYY-MM-DD` |
| `qrCode` | string | 可打印二维码内容，格式为 `OB1\|{batchCode}\|{token}` |

### QrScanRequest

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `qr` | string | 原始二维码内容 |
| `source` | string | 扫码来源：`web_camera`、`mobile_camera`、`handheld` |
| `deviceId` | string \| null | 设备标识，可选 |
| `clientScanId` | string \| null | 客户端扫码 ID，用于去重 |
| `scannedAt` | string \| null | 客户端扫码时间 |

### QrScanResult

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `auditId` | string | 审计记录 ID |
| `batchCode` | string \| null | 批次号 |
| `productName` | string \| null | 商品名称 |
| `status` | string | `valid`、`near_expiry`、`expired`、`invalid`、`revoked`、`not_found` |
| `message` | string | 前端展示消息 |
| `expireDate` | string \| null | 到期日期 |
| `remainingDays` | integer \| null | 剩余天数，过期为负数 |
| `clientScanId` | string \| null | 批量扫码时回传客户端扫码 ID；无值时省略 |

### QrScanBulkRequest

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `items` | QrScanRequest[] | 扫码项列表，不能为空 |

### QrScanBulkResult

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `items` | QrScanResult[] | 每个二维码的独立扫码结果 |

### Pagination

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `page` | integer | 当前页码 |
| `size` | integer | 每页数量 |
| `total` | integer | 总条数 |

### IdOnlyResult

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 被删除资源的 ID |

## 组件权限码

| 权限码 | 组件 | 动作 | 说明 |
| --- | --- | --- | --- |
| `products_read` | products | read | 商品列表、详情、条码查询、分类查询 |
| `products_create` | products | create | 创建商品 |
| `products_update` | products | update | 更新商品 |
| `products_delete` | products | delete | 删除商品 |
| `batches_read` | batches | read | 批次列表、商品批次、批次详情、效期预警 |
| `batches_create` | batches | create | 创建批次 |
| `batches_update` | batches | update | 更新批次、更新批次状态 |
| `batches_delete` | batches | delete | 删除批次 |
| `batch_operations_read` | batch_operations | read | 查看批次库存操作记录 |
| `batch_operations_add` | batch_operations | add | 创建 `operation_type=add` 入库操作 |
| `batch_operations_deduct` | batch_operations | deduct | 创建 `operation_type=deduct` 出库操作 |
| `batch_operations_loss` | batch_operations | loss | 创建 `operation_type=loss` 报损操作 |
| `batch_operations_revert` | batch_operations | revert | 撤销库存操作 |
| `label_payload_issue` | label_payload | issue | 签发可打印二维码凭证 |
| `qr_scans_create` | qr_scans | create | 单条扫码和批量扫码 |
| `dashboard_read` | dashboard | read | 库存看板概览 |
| `analytics_read` | analytics | read | 分析汇总 |

### 接口权限映射

- `GET /dashboard/overview`：`dashboard_read`
- `GET /analytics/summary`：`analytics_read`
- 商品读接口：`products_read`；`POST /products`：`products_create`；`PATCH /products/{id}`：`products_update`；`DELETE /products/{id}`：`products_delete`
- 批次读接口：`batches_read`；`POST /batches`：`batches_create`；`PATCH /batches/{id}` 和 `PATCH /batches/{id}/status`：`batches_update`；`DELETE /batches/{id}`：`batches_delete`
- `GET /batches/{id}/operations`：`batch_operations_read`
- `POST /batches/{id}/operations`：按 `operation_type` 分别要求 `batch_operations_add`、`batch_operations_deduct`、`batch_operations_loss`
- `POST /batches/{id}/operations/{operation_id}/revert`：`batch_operations_revert`
- `GET /batches/{id}/label-payload`：`label_payload_issue`
- `POST /qr-scans` 和 `POST /qr-scans/bulk`：`qr_scans_create`

## 认证接口

### POST `/auth/login`

使用 Django 用户名和密码登录，签发 Bearer token。默认有效期 8 小时；勾选“记住我”时有效期为 3 天。

请求体：

```json
{
  "username": "operator",
  "password": "password",
  "remember_me": true
}
```

字段说明：
- `remember_me`：可选，默认 `false`；为 `true` 时本次 token 延长到 3 天。

成功响应：
- `data`：`AuthLoginResult`

常见错误：
- `400 / 4001 / validation_error`
- `401 / 4011 / unauthenticated`
- `409 / 4091 / conflict`

### POST `/auth/logout`

吊销当前请求携带的 Bearer token。

认证：
- 必须携带 `Authorization: Bearer <token>`

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "revoked": true
  }
}
```

常见错误：
- `401 / 4011 / unauthenticated`

### GET `/auth/me`

查询当前登录用户。

认证：
- 必须携带 `Authorization: Bearer <token>`

成功响应：
- `data`：`AuthUser`

常见错误：
- `401 / 4011 / unauthenticated`

## 权限管理接口

以下接口仅允许 `is_superuser=true` 的用户访问。非超级管理员返回
`403 / 4031 / forbidden`。

### GET `/auth/permissions`

返回全部业务权限目录，按组件分组。

成功响应：
- `data.items[]`：`{ component, permissions[] }`
- `data.items[].permissions[]`：包含 `code,name,component,action,description`
- `data.pagination`：`null`

### GET `/auth/roles`

返回角色列表。角色底层使用 Django `Group`。

成功响应：
- `data.items[]`：`AuthRole`
- `data.pagination`：`null`

### POST `/auth/roles`

创建角色并配置权限。

请求体：

```json
{
  "name": "warehouse_operator",
  "permission_codes": ["products_read", "batch_operations_add"]
}
```

成功响应：
- `201`
- `data`：`AuthRole`

常见错误：
- `400 / 4001 / validation_error`
- `403 / 4031 / forbidden`
- `409 / 4091 / conflict`

### GET `/auth/roles/{id}`

查询角色详情。

成功响应：
- `data`：`AuthRole`

### PATCH `/auth/roles/{id}`

更新角色名称和权限。`permission_codes` 存在时会整体替换角色权限。

请求体：

```json
{
  "name": "warehouse_manager",
  "permission_codes": ["products_read", "products_create"]
}
```

成功响应：
- `data`：`AuthRole`

### DELETE `/auth/roles/{id}`

删除角色。角色已分配给用户时返回 `409 / 4091 / conflict`。

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1
  }
}
```

### GET `/auth/users`

返回用户列表。

成功响应：
- `data.items[]`：`AuthAdminUser`
- `data.pagination`：`null`

### POST `/auth/users`

创建普通用户或 staff 用户；不支持通过该接口创建超级管理员。

请求体：

```json
{
  "username": "operator",
  "password": "password",
  "email": "operator@example.com",
  "first_name": "Origin",
  "last_name": "User",
  "is_active": true,
  "is_staff": false,
  "group_ids": [1],
  "permission_codes": ["qr_scans_create"]
}
```

成功响应：
- `201`
- `data`：`AuthAdminUser`

### GET `/auth/users/{id}`

查询用户详情。

成功响应：
- `data`：`AuthAdminUser`

### PATCH `/auth/users/{id}`

更新用户资料、启用状态、staff 状态、角色和直接权限。`group_ids` 和
`permission_codes` 存在时会整体替换对应授权。

请求体：

```json
{
  "email": "operator@example.com",
  "first_name": "Origin",
  "last_name": "User",
  "is_active": true,
  "is_staff": false,
  "group_ids": [1],
  "permission_codes": ["products_read"]
}
```

成功响应：
- `data`：`AuthAdminUser`

### POST `/auth/users/{id}/password`

重置用户密码。

请求体：

```json
{
  "password": "new-password"
}
```

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 2,
    "password_reset": true
  }
}
```

## 看板接口

### GET `/dashboard/overview`

查询库存看板总览。

聚合口径：
- 只统计 `quantity > 0` 且 `status != used_up` 的批次。
- 临期：`0 <= days_until_expiry <= 7`。
- 已过期：`days_until_expiry < 0` 或 `expiry_status = expired`。
- 批次健康率：既非临期也非已过期的当前在库批次数 / 当前在库批次数。
- 未来 30 天到期趋势包含服务端当前日期和第 30 天，共 31 个日期桶。

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "current_inventory_quantity": "42.50",
    "near_expiry_batch_count": 3,
    "expired_batch_count": 1,
    "batch_health_rate": 0.875,
    "expiry_trend_30d": [
      {
        "date": "2026-05-13",
        "batch_count": 1,
        "quantity": "8.50"
      }
    ],
    "category_inventory_distribution": [
      {
        "category": "饮料",
        "batch_count": 4,
        "quantity": "28.50",
        "ratio": 0.6706
      }
    ],
    "top_near_expiry_batches": []
  }
}
```

返回字段结构：
- `data`：`DashboardOverview`

常见错误：
- `409 / 4091 / conflict`

## 分析接口

### GET `/analytics/summary`

查询库存分析汇总。

请求参数：
- `range`：可选，默认 `6m`；当前支持 `1m`、`3m`、`6m`、`12m`

聚合口径：
- 当前在库类指标只统计 `quantity > 0` 且 `status != used_up` 的批次。
- 有效操作会排除撤销操作本身，以及已经被撤销的原操作。
- 报损数量：有效 `batch_operations.operation_type = loss` 的数量。
- 出库/报损量：有效 `deduct + loss` 操作数量。
- 平均库龄：按当前在库批次的 `received_at` 到服务端当前日期计算批次平均，暂不做数量加权。
- 月度在库数量：按当前在库批次的 `received_at` 所属月份汇总当前数量；该值不是历史库存快照。

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "range": "6m",
    "period": {
      "start": "2025-12-01",
      "end": "2026-05-13"
    },
    "inventory_change_count": 12,
    "current_month_loss_quantity": "3.00",
    "average_stock_age_days": 18.5,
    "monthly_inventory_loss_trend": [
      {
        "month": "2026-05",
        "inventory_quantity": "42.50",
        "loss_quantity": "3.00"
      }
    ],
    "category_operation_summary": [
      {
        "category": "饮料",
        "inbound_quantity": "12.00",
        "outbound_loss_quantity": "5.00",
        "operation_count": 6
      }
    ],
    "high_risk_inventory_ranking": []
  }
}
```

返回字段结构：
- `data`：`AnalyticsSummary`

常见错误：
- `400 / 4001 / validation_error`
- `409 / 4091 / conflict`

## 商品接口

### GET `/products`

查询商品列表。

请求参数：
- `search`：可选，按 `barcode`、`product_name`、`category`、`location`、`unit`、`manufacturer` 模糊查询
- `page`：可选，默认 `1`
- `size`：可选，默认 `20`，最大 `100`

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "barcode": "6901234567890",
        "product_name": "示例商品",
        "shelf_life_days": 30,
        "location": "A-01",
        "category": "饮料",
        "unit": "瓶",
        "manufacturer": "示例厂商",
        "created_at": "2026-04-21T11:43:00+08:00",
        "updated_at": "2026-04-21T11:43:00+08:00"
      }
    ],
    "pagination": {
      "page": 1,
      "size": 20,
      "total": 1
    }
  }
}
```

返回字段结构：
- `data.items[]`：`Product`
- `data.pagination`：`Pagination`

常见错误：
- `400 / 4001 / validation_error`

### POST `/products`

创建商品。

请求体：

```json
{
  "barcode": "6901234567890",
  "product_name": "示例商品",
  "shelf_life_days": 30,
  "location": "A-01",
  "category": "饮料",
  "unit": "瓶",
  "manufacturer": "示例厂商"
}
```

请求字段：
- `barcode`：必填
- `product_name`：必填
- `shelf_life_days`：必填，整数，最小 `0`
- `location`：可选，可为 `null` 或空字符串
- `category`：可选，可为 `null` 或空字符串
- `unit`：可选，可为 `null` 或空字符串
- `manufacturer`：必填

说明：
- 后端会记录当前登录用户为本次商品创建操作的执行人。

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "barcode": "6901234567890",
    "product_name": "示例商品",
    "shelf_life_days": 30,
    "location": "A-01",
    "category": "饮料",
    "unit": "瓶",
    "manufacturer": "示例厂商",
    "created_at": "2026-04-21T11:43:00+08:00",
    "updated_at": "2026-04-21T11:43:00+08:00"
  }
}
```

返回字段结构：
- `data`：`Product`

常见错误：
- `400 / 4001 / validation_error`
- `409 / 4091 / conflict`

### GET `/products/{product_id}`

查询单个商品。

路径参数：
- `product_id`：商品 ID

成功响应：
- `data`：`Product`

常见错误：
- `404 / 4041 / not_found`

### PATCH `/products/{product_id}`

更新商品。只更新请求体中出现的字段。

路径参数：
- `product_id`：商品 ID

请求体示例：

```json
{
  "product_name": "更新后的商品名称",
  "location": "B-02"
}
```

可更新字段：
- `product_name`
- `shelf_life_days`
- `location`
- `category`
- `unit`
- `manufacturer`

说明：
- 后端会记录当前登录用户为本次商品更新操作的执行人。

成功响应：
- `data`：`Product`

常见错误：
- `400 / 4001 / validation_error`
- `404 / 4041 / not_found`
- `409 / 4091 / conflict`

### DELETE `/products/{product_id}`

删除商品。

路径参数：
- `product_id`：商品 ID

说明：
- 后端会在删除前记录当前登录用户和商品快照。

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1
  }
}
```

返回字段结构：
- `data`：`IdOnlyResult`

常见错误：
- `404 / 4041 / not_found`

### GET `/products/barcode/{barcode}`

按条码精确查询商品。

路径参数：
- `barcode`：商品条码

成功响应：
- `data`：`Product`

常见错误：
- `404 / 4041 / not_found`

### GET `/products/categories`

查询商品分类列表。

请求参数：
- `search`：可选，按分类名模糊查询

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": ["饮料", "香烟"],
    "pagination": null
  }
}
```

返回字段结构：
- `data.items[]`：`string`
- `data.pagination`：固定为 `null`

常见错误：
- `400 / 4001 / validation_error`

### GET `/products/{product_id}/batches`

查询某个商品下的批次列表。

路径参数：
- `product_id`：商品 ID

请求参数：
- `status`：可选，按状态过滤
- `expired_only`：可选，布尔值，默认 `false`
- `page`：可选，默认 `1`
- `size`：可选，默认 `20`，最大 `100`

成功响应：
- `data.items[]`：`Batch`
- `data.pagination`：`Pagination`

常见错误：
- `400 / 4001 / validation_error`

## 批次接口

### GET `/batches`

查询批次列表。

请求参数：
- `product_id`：可选，按商品 ID 过滤
- `status`：可选，按状态过滤
- `expired_only`：可选，布尔值，默认 `false`
- `page`：可选，默认 `1`
- `size`：可选，默认 `20`，最大 `100`

排序规则：
- 按 `received_at` 倒序
- 同一时间下按 `id` 倒序

成功响应：
- `data.items[]`：`Batch`
- `data.pagination`：`Pagination`

常见错误：
- `400 / 4001 / validation_error`

### POST `/batches`

创建批次。

请求体：

```json
{
  "product_id": 14,
  "quantity": "8.50",
  "manufacture_date": "2026-04-21",
  "expire_date": "2026-05-06",
  "status": "unopened",
  "remarks": "示例批次"
}
```

请求字段：
- `product_id`：必填
- `batch_code`：可选，不传时自动生成
- `quantity`：必填，可传数字或字符串，响应始终为字符串
- `manufacture_date`：必填，格式 `YYYY-MM-DD`
- `expire_date`：可选，格式 `YYYY-MM-DD`；不传时按 `manufacture_date + product.shelf_life_days` 自动计算
- `status`：可选，默认 `unopened`
- `remarks`：可选，可为 `null` 或空字符串

说明：
- 创建批次时后端会自动签发一条二维码凭证，但本接口不返回二维码 token。
- 标签打印应调用 `GET /batches/{batch_id}/label-payload` 获取专用打印载荷。
- 后端会记录当前登录用户为本次批次创建操作的执行人。

成功响应：
- `data`：`Batch`

常见错误：
- `400 / 4001 / validation_error`
- `404 / 4041 / not_found`
- `409 / 4091 / conflict`

### GET `/batches/{batch_id}`

查询单个批次。

路径参数：
- `batch_id`：批次 ID

成功响应：
- `data`：`Batch`

常见错误：
- `404 / 4041 / not_found`

### GET `/batches/{batch_id}/label-payload`

查询批次标签打印载荷，并签发一条新的可打印二维码凭证。普通批次列表和详情接口不会返回二维码 token。

路径参数：
- `batch_id`：批次 ID

说明：
- 本接口必须登录；当前阶段只要求登录，不做细粒度标签打印权限。
- 二维码内容只包含凭证：`OB1|{batchCode}|{token}`，不包含效期判断结果。
- token 明文只在本次响应中返回；数据库只保存 `sha256(token + QR_TOKEN_PEPPER)`。
- 读取标签载荷会签发一条新凭证；已有未吊销二维码继续有效。

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batchCode": "B202605120001",
    "productName": "鲜奶",
    "barcode": "692xxxx",
    "quantity": "12.00",
    "location": "A-01",
    "expireDate": "2026-08-11",
    "qrCode": "OB1|B202605120001|N7K3Q9X2P4A8M6D2"
  }
}
```

返回字段结构：
- `data`：`BatchLabelPayload`

常见错误：
- `401 / 4011 / unauthenticated`
- `404 / 4041 / not_found`
- `409 / 4091 / conflict`

### PATCH `/batches/{batch_id}`

更新批次。只更新请求体中出现的字段。

路径参数：
- `batch_id`：批次 ID

请求体示例：

```json
{
  "quantity": "9.50",
  "remarks": "updated"
}
```

可更新字段：
- `batch_code`
- `manufacture_date`
- `expire_date`
- `status`
- `remarks`

说明：
- 批次数量不能通过该接口直接更新；数量变更必须使用
  `POST /batches/{batch_id}/operations`。
- 后端会记录当前登录用户为本次批次更新操作的执行人。

成功响应：
- `data`：`Batch`

常见错误：
- `400 / 4001 / validation_error`
- `404 / 4041 / not_found`
- `409 / 4091 / conflict`

### POST `/batches/{batch_id}/operations`

创建一条批次操作记录，并同步更新对应批次的 `quantity` 和 `status`。

路径参数：
- `batch_id`：批次 ID

请求体：

```json
{
  "operation_type": "loss",
  "quantity": "2.00",
  "remarks": "包装破损"
}
```

请求字段：
- `operation_type`：必填，枚举值为 `add`、`loss`、`deduct`
- `quantity`：必填，可传数字或字符串，必须大于 `0`
- `remarks`：可选，可为 `null` 或空字符串

业务规则：
- `add`：`batch.quantity += quantity`
- `loss` / `deduct`：`batch.quantity -= quantity`
- 后端会记录当前登录用户为本次库存增减或报损操作的执行人。
- 当 `quantity_after = 0` 时，系统自动将批次 `status` 更新为 `used_up`
- 当批次当前 `status = used_up` 且本次操作后 `quantity_after > 0` 时，系统自动将批次 `status` 重置为 `null`
- 扣减后小于 `0` 时拒绝，返回 `409 / 4091 / conflict`
- 历史数据中 `batch.quantity` 为 `null` 时拒绝，返回 `409 / 4091 / conflict`

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "operation": {
      "id": 1,
      "batch_id": 10,
      "operation_type": "loss",
        "quantity": "2.00",
        "quantity_after": "6.50",
        "remarks": "包装破损",
        "created_at": "2026-05-07T14:30:00+08:00",
        "reversed_operation_id": null,
        "is_reverted": false
      },
    "batch": {
      "id": 10,
      "quantity": "6.50",
      "status": null
    }
  }
}
```

返回字段结构：
- `data.operation`：`BatchOperation`
- `data.batch`：`BatchQuantitySummary`

常见错误：
- `400 / 4001 / validation_error`
- `404 / 4041 / not_found`
- `409 / 4091 / conflict`

### GET `/batches/{batch_id}/operations`

查询某个批次的操作历史。

路径参数：
- `batch_id`：批次 ID

请求参数：
- `operation_type`：可选，枚举值为 `add`、`loss`、`deduct`
- `page`：可选，默认 `1`
- `size`：可选，默认 `20`，最大 `100`

排序规则：
- 按 `created_at` 倒序
- 同一时间下按 `id` 倒序

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "batch_id": 10,
        "operation_type": "loss",
        "quantity": "2.00",
        "quantity_after": "6.50",
        "remarks": "包装破损",
        "created_at": "2026-05-07T14:30:00+08:00",
        "reversed_operation_id": null,
        "is_reverted": false
      }
    ],
    "pagination": {
      "page": 1,
      "size": 20,
      "total": 1
    }
  }
}
```

返回字段结构：
- `data.items[]`：`BatchOperation`
- `data.pagination`：`Pagination`

常见错误：
- `400 / 4001 / validation_error`
- `404 / 4041 / not_found`

### POST `/batches/{batch_id}/operations/{operation_id}/revert`

撤销一条批次操作。撤销不会删除原记录，而是创建一条反向操作记录，并更新批次
`quantity` 和 `status`。

路径参数：
- `batch_id`：批次 ID
- `operation_id`：要撤销的操作记录 ID

请求体：

```json
{
  "remarks": "撤销误操作"
}
```

请求字段：
- `remarks`：可选，可为 `null` 或空字符串

业务规则：
- 撤销 `add` 会创建一条 `deduct` 操作。
- 撤销 `loss` / `deduct` 会创建一条 `add` 操作。
- 后端会记录当前登录用户为本次撤销操作的执行人。
- 当撤销后的 `quantity_after = 0` 时，系统自动将批次 `status` 更新为 `used_up`
- 当批次当前 `status = used_up` 且撤销后 `quantity_after > 0` 时，系统自动将批次 `status` 重置为 `null`
- 每条原操作最多只能撤销一次；重复撤销返回 `409 / 4091 / conflict`。
- 撤销操作本身不能再次撤销；尝试撤销返回 `409 / 4091 / conflict`。
- 撤销 `add` 时如果当前批次数量不足以扣回，返回 `409 / 4091 / conflict`。

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "operation": {
      "id": 2,
      "batch_id": 10,
      "operation_type": "add",
      "quantity": "2.00",
      "quantity_after": "8.50",
      "remarks": "撤销误操作",
      "created_at": "2026-05-07T14:40:00+08:00",
      "reversed_operation_id": 1,
      "is_reverted": false
    },
    "batch": {
      "id": 10,
      "quantity": "8.50",
      "status": null
    }
  }
}
```

返回字段结构：
- `data.operation`：新创建的反向 `BatchOperation`
- `data.batch`：`BatchQuantitySummary`

常见错误：
- `400 / 4001 / validation_error`
- `404 / 4041 / not_found`
- `409 / 4091 / conflict`

### PATCH `/batches/{batch_id}/status`

只更新批次状态。

路径参数：
- `batch_id`：批次 ID

请求体：

```json
{
  "status": "used_up"
}
```

成功响应：
- `data`：`Batch`

常见错误：
- `400 / 4001 / validation_error`
- `404 / 4041 / not_found`
- `409 / 4091 / conflict`

### DELETE `/batches/{batch_id}`

删除批次。

路径参数：
- `batch_id`：批次 ID

说明：
- 后端会在删除前记录当前登录用户和批次快照。

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 3
  }
}
```

返回字段结构：
- `data`：`IdOnlyResult`

常见错误：
- `404 / 4041 / not_found`

## 二维码扫码接口

### POST `/qr-scans`

提交一次二维码扫码结果。所有扫码请求都会写入审计，包括格式错误和无效 token。

请求体：

```json
{
  "qr": "OB1|B202605120001|N7K3Q9X2P4A8M6D2",
  "source": "mobile_camera",
  "deviceId": "device-001",
  "clientScanId": "uuid-from-client",
  "scannedAt": "2026-05-12T10:30:00+08:00"
}
```

请求字段：
- `qr`：必填，原始二维码内容
- `source`：必填，枚举值为 `web_camera`、`mobile_camera`、`handheld`
- `deviceId`：可选，可为 `null` 或空字符串
- `clientScanId`：可选，可为 `null` 或空字符串；非空时按 `source + deviceId + clientScanId` 去重
- `scannedAt`：可选，客户端扫码时间

处理规则：
- 先创建审计草稿，再解析二维码、匹配凭证、检查吊销和批次存在性、计算效期，最后更新审计结果。
- `clientScanId` 去重命中时不新增审计，直接返回首次审计结果。
- 审计日志会记录当前登录用户。
- 前端可以解析二维码格式用于“正在识别”的体验，但不能自行判断效期。

状态规则：

| status | 说明 |
| --- | --- |
| `valid` | 未过期且剩余天数大于临期阈值 |
| `near_expiry` | 未过期且 `remainingDays <= QR_SCAN_NEAR_EXPIRY_DAYS` |
| `expired` | `expire_date < today` |
| `invalid` | 格式错误或 token 错误 |
| `revoked` | 二维码凭证已吊销 |
| `not_found` | 凭证匹配到批次号，但批次记录不存在 |

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "auditId": "scan_01J...",
    "batchCode": "B202605120001",
    "productName": "鲜奶",
    "status": "valid",
    "message": "该批次仍在效期内",
    "expireDate": "2026-08-11",
    "remainingDays": 91,
    "clientScanId": "uuid-from-client"
  }
}
```

返回字段结构：
- `data`：`QrScanResult`

常见错误：
- `400 / 4001 / validation_error`
- `409 / 4091 / conflict`

### POST `/qr-scans/bulk`

批量提交多个二维码扫码结果。每个二维码都会独立处理和落审计。

请求体：

```json
{
  "items": [
    {
      "qr": "OB1|B202605120001|N7K3Q9X2P4A8M6D2",
      "source": "mobile_camera",
      "deviceId": "device-001",
      "clientScanId": "scan-001",
      "scannedAt": "2026-05-12T10:30:00+08:00"
    },
    {
      "qr": "bad-qr",
      "source": "mobile_camera",
      "deviceId": "device-001",
      "clientScanId": "scan-002",
      "scannedAt": "2026-05-12T10:30:01+08:00"
    }
  ]
}
```

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "auditId": "scan_01J...",
        "batchCode": "B202605120001",
        "productName": "鲜奶",
        "status": "valid",
        "message": "该批次仍在效期内",
        "expireDate": "2026-08-11",
        "remainingDays": 91,
        "clientScanId": "scan-001"
      },
      {
        "auditId": "scan_01K...",
        "batchCode": null,
        "productName": null,
        "status": "invalid",
        "message": "二维码格式错误",
        "expireDate": null,
        "remainingDays": null,
        "clientScanId": "scan-002"
      }
    ]
  }
}
```

返回字段结构：
- `data`：`QrScanBulkResult`

常见错误：
- `400 / 4001 / validation_error`
- `409 / 4091 / conflict`

## 其他

- 首页：`GET /`
- 当前没有 `users` 相关 API

## 效期预警补充

### Batch 新增计算字段

批次响应新增以下只读计算字段，不写入数据库：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `days_until_expiry` | integer \| null | 距离 `expire_date` 的剩余天数，过期为负数，无到期日为 `null` |
| `expiry_progress` | number \| null | 生命周期相对进度，计算公式为 `(today - manufacture_date) / product.shelf_life_days` |
| `expiry_status` | string | 效期风险状态 |

`expiry_status` 使用相对进度判定：

| 状态 | 条件 | 说明 |
| --- | --- | --- |
| `expired` | `expiry_progress > 1.0` | 已过期 |
| `critical` | `expiry_progress > 0.9` | 生命周期超过 90% |
| `warning` | `expiry_progress > 0.75` | 生命周期 75% 到 90% |
| `normal` | `expiry_progress <= 0.75` | 生命周期未超过 75% |

`shelf_life_days = 0` 时视为已过期。`manufacture_date` 是业务必填字段；若历史数据缺失导致无法计算，相应计算字段会防御性返回 `null` / `unknown`，避免接口 500。

### GET `/batches/expiry-alerts`

查询临期/过期批次列表。

请求参数：

- `product_id`：可选，按商品 ID 过滤
- `status`：可选
- `category`：可选，按商品分类精确过滤
- `location`：可选，按商品位置精确过滤
- `expiry_status`：可选，枚举值为 `expired`、`critical`、`warning`、`normal`
- `days_lte`：可选，默认 `30`，绝对剩余天数运营窗口
- `include_expired`：可选，默认 `true`
- `page`：可选，默认 `1`
- `size`：可选，默认 `20`，最大 `100`

默认行为：

- 只返回生命周期后段状态：`expired`、`critical`、`warning`。
- 默认运营窗口为 `days_until_expiry <= 30`。
- `include_expired=false` 时排除已过期批次。
- 排序优先级：`days_until_expiry ASC`、`expiry_progress DESC`、`id DESC`。

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "product_id": 14,
        "batch_code": "BATCH-20260427-12345678",
        "quantity": "8.50",
        "received_at": "2026-04-21T11:43:00+08:00",
        "manufacture_date": "2026-04-01",
        "expire_date": "2026-04-30",
        "status": "unopened",
        "remarks": "示例批次",
        "days_until_expiry": 3,
        "expiry_progress": 0.87,
        "expiry_status": "warning",
        "product": {
          "id": 14,
          "barcode": "6901234567890",
          "product_name": "示例商品",
          "unit": "盒",
          "manufacturer": "示例厂商"
        }
      }
    ],
    "pagination": {
      "page": 1,
      "size": 20,
      "total": 1
    }
  }
}
```
