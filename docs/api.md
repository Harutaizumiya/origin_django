# API 文档

本文档定义当前项目的目标 API 契约。后端实现必须与本文档保持同步；如实现与文档不一致，以本文档为准并同步修正代码。

## 基础信息

- Base URL：`<BASE_URL>/api`
- 本地开发示例：`http://127.0.0.1:8000/api`
- Content-Type：`application/json`

## 认证说明

- 当前接口暂不要求认证。
- 未来如启用认证，统一使用请求头：`Authorization: Bearer <token>`。
- 当前文档先保留该约定，具体 token 签发与校验规则后续单独补充。

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

- HTTP 状态码：`400` / `404` / `409`
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

成功响应：
- `data`：`Batch`

常见错误：
- `400 / 4001 / validation_error`
- `404 / 4041 / not_found`
- `409 / 4091 / conflict`

### POST `/batches/{batch_id}/operations`

创建一条批次操作记录，并同步更新对应批次的 `quantity`。该接口不读取、不判断、不修改
批次 `status`。

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
      "quantity": "6.50"
    }
  }
}
```

返回字段结构：
- `data.operation`：`BatchOperation`
- `data.batch`：批次数量摘要

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
`quantity`。

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
- 每条原操作最多只能撤销一次；重复撤销返回 `409 / 4091 / conflict`。
- 撤销操作本身不能再次撤销；尝试撤销返回 `409 / 4091 / conflict`。
- 撤销 `add` 时如果当前批次数量不足以扣回，返回 `409 / 4091 / conflict`。
- 撤销不读取、不判断、不修改批次 `status`。

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
      "quantity": "8.50"
    }
  }
}
```

返回字段结构：
- `data.operation`：新创建的反向 `BatchOperation`
- `data.batch`：批次数量摘要

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
- `status`：可选，默认 `unopened`
- `category`：可选，按商品分类精确过滤
- `location`：可选，按商品位置精确过滤
- `expiry_status`：可选，枚举值为 `expired`、`critical`、`warning`、`normal`
- `days_lte`：可选，默认 `30`，绝对剩余天数运营窗口
- `include_expired`：可选，默认 `true`
- `page`：可选，默认 `1`
- `size`：可选，默认 `20`，最大 `100`

默认行为：

- 只返回 `status = unopened` 的批次。
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
