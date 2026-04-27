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
- `quantity`
- `manufacture_date`
- `expire_date`
- `status`
- `remarks`

成功响应：
- `data`：`Batch`

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
