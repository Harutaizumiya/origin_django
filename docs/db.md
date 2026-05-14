# 数据库结构文档

本文档按当前 Django model 映射整理数据库结构。库存业务模型均设置为
`managed = False`，说明 Django 当前不会通过 migration 创建或变更这些业务表；
实际数据库结构需要与本文档保持一致。Django auth、session 以及 `accounts_auth_tokens`
由 Django migrations 管理。

## 基础信息

- 数据库类型：PostgreSQL
- 连接配置：通过项目根目录 `.env` 中的 `DATABASE_URL` 读取
- Django 配置入口：`config/settings.py`
- 测试环境：执行测试时使用 SQLite 文件 `test.sqlite3`
- 时区：`Asia/Shanghai`
- 认证 token pepper：通过 `AUTH_TOKEN_PEPPER` 配置读取，未配置时回退到 `SECRET_KEY`

## 表关系

```mermaid
erDiagram
    product ||--o{ batches : "has"
    batches ||--o{ batch_operations : "records"
    batches ||--o{ batch_qr_credentials : "issues"
    batches ||--o{ qr_scan_audit_logs : "audits"
    auth_user ||--o{ accounts_auth_tokens : "owns"

    product {
        bigint id PK
        varchar(255) barcode UK
        varchar(255) product_name
        integer shelf_life_days
        varchar(255) location
        varchar(255) category
        varchar(255) unit
        text manufacturer
        timestamptz created_at
        timestamptz updated_at
    }

    batches {
        integer id PK
        bigint product_id FK
        varchar(255) batch_code
        numeric(12,2) quantity
        timestamptz received_at
        date manufacture_date
        date expire_date
        varchar(255) status
        varchar(255) remarks
    }

    batch_operations {
        bigint id PK
        integer batch_id FK
        bigint reversed_operation_id FK
        varchar(20) operation_type
        numeric(12,2) quantity
        numeric(12,2) quantity_after
        varchar(255) remarks
        timestamptz created_at
    }

    batch_qr_credentials {
        bigint id PK
        integer batch_id FK
        varchar(255) batch_code
        varchar(64) token_hash UK
        timestamptz issued_at
        timestamptz revoked_at
        varchar(255) created_by
    }

    qr_scan_audit_logs {
        varchar(40) id PK
        text raw_qr
        integer batch_id FK
        varchar(255) batch_code
        varchar(50) source
        varchar(255) device_id
        varchar(255) client_scan_id
        varchar(255) scanner_user
        timestamptz scanned_at_client
        timestamptz scanned_at_server
        inet ip_address
        text user_agent
        varchar(20) result_status
        text result_message
        varchar(255) failure_reason
    }

    accounts_auth_tokens {
        bigint id PK
        integer user_id FK
        varchar(64) token_hash UK
        timestamptz issued_at
        timestamptz expires_at
        timestamptz revoked_at
    }
```

## Django 管理的认证表

Django 内置的 `auth_*`、`django_session` 表由 `django.contrib.auth` 和
`django.contrib.sessions` 的 migrations 创建和维护。当前项目不自定义用户表，登录用户来自
Django 默认用户模型。

## 表：accounts_auth_tokens

API Bearer token 表，由 `accounts` app migration 管理。明文 token 只在登录响应返回；
数据库只保存 `sha256(token + AUTH_TOKEN_PEPPER)`。

| 字段 | 数据库类型 | 空值 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | 否 | 自增 | 主键 | token 记录 ID |
| `user_id` | `integer` | 否 | 无 | 外键/索引 | 关联 Django 用户 ID |
| `token_hash` | `varchar(64)` | 否 | 无 | 唯一 | 登录 token 的 SHA-256 哈希 |
| `issued_at` | `timestamp with time zone` | 否 | 应用层当前时间 | - | 签发时间 |
| `expires_at` | `timestamp with time zone` | 否 | 无 | 索引 | 到期时间，固定为签发后 8 小时 |
| `revoked_at` | `timestamp with time zone` | 是 | 无 | 索引 | 吊销时间，`null` 表示未吊销 |

### 业务约定

- token 格式为 `Authorization: Bearer <token>`。
- token 为 opaque 字符串，不包含可解析业务声明。
- 每个 token 固定 8 小时过期，不提供 refresh token。
- 登出只吊销当前 token；同一用户可并存多个未过期 token。

## 表：product

商品主数据表。

| 字段 | 数据库类型 | 空值 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | 否 | 自增 | 主键 | 商品 ID |
| `barcode` | `varchar(255)` | 否 | 无 | 唯一 | 商品条码 |
| `product_name` | `varchar(255)` | 否 | 无 | - | 商品名称 |
| `shelf_life_days` | `integer` | 否 | 无 | - | 保质期天数，接口层要求不小于 `0` |
| `location` | `varchar(255)` | 是 | 无 | - | 存放位置 |
| `category` | `varchar(255)` | 是 | 无 | - | 商品分类 |
| `unit` | `varchar(255)` | 是 | 无 | - | 单位 |
| `manufacturer` | `text` | 否 | 无 | - | 厂商 |
| `created_at` | `timestamp with time zone` | 否 | `NOW()` | - | 创建时间 |
| `updated_at` | `timestamp with time zone` | 否 | `NOW()` | - | 更新时间 |

### 业务约定

- `barcode` 用于按条码精确查询，必须唯一。
- 商品列表支持按 `barcode`、`product_name`、`category`、`location`、`unit`、
  `manufacturer` 模糊查询。
- 删除商品时，当前 Django model 对关联批次使用 `DO_NOTHING`；如果数据库存在外键，
  需要由数据库约束决定是否允许删除已有批次的商品。

## 表：batches

商品入库批次表。

| 字段 | 数据库类型 | 空值 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | `integer` | 否 | 自增 | 主键 | 批次 ID |
| `product_id` | `bigint` | 否 | 无 | 外键 | 关联 `product.id` |
| `batch_code` | `varchar(255)` | 否 | 应用层生成 | - | 批次号 |
| `quantity` | `numeric(12,2)` | 是 | 无 | - | 数量 |
| `received_at` | `timestamp with time zone` | 否 | `NOW()` | - | 入库时间 |
| `manufacture_date` | `date` | 是 | 无 | - | 生产日期，创建接口要求必填 |
| `expire_date` | `date` | 是 | 应用层计算 | - | 到期日期 |
| `status` | `varchar(255)` | 是 | 应用层默认为 `unopened` | - | 批次状态 |
| `remarks` | `varchar(255)` | 是 | 无 | - | 备注 |

### 业务约定

- `batch_code` 未传入时由应用层生成，格式为
  `BATCH-YYYYMMDD-<8位随机十六进制>`。
- `expire_date` 未传入时由应用层按
  `manufacture_date + product.shelf_life_days` 计算。
- 当前 API 文档定义的状态值为：
  - `unopened`
  - `opened`
  - `used_up`
- 批次列表默认按 `received_at` 倒序，再按 `id` 倒序排序。
- 批次查询支持按 `product_id`、`status`、是否过期过滤。
- 批次数量变更应通过 `batch_operations` 记录；业务接口不再允许直接 PATCH
  `batches.quantity`。

## 表：batch_operations

批次操作历史表，用于记录每次批次数量变更。此表与 `product`、`batches` 一样由生产库
DDL 维护，Django model 设置为 `managed = False`。

| 字段 | 数据库类型 | 空值 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | 否 | 自增 | 主键 | 操作记录 ID |
| `batch_id` | `integer` | 否 | 无 | 外键 | 关联 `batches.id` |
| `reversed_operation_id` | `bigint` | 是 | 无 | 外键/唯一 | 被撤销的原操作 ID，普通操作为 `null` |
| `operation_type` | `varchar(20)` | 否 | 无 | 检查约束/索引 | 操作类型：`add`、`loss`、`deduct` |
| `quantity` | `numeric(12,2)` | 否 | 无 | 检查约束 | 本次操作数量，始终为正数 |
| `quantity_after` | `numeric(12,2)` | 否 | 无 | 检查约束 | 操作完成后的批次数量快照 |
| `remarks` | `varchar(255)` | 是 | 无 | - | 备注 |
| `created_at` | `timestamp with time zone` | 否 | `NOW()` | 索引 | 操作时间 |

### 业务约定

- `quantity` 始终为正数，增减方向由 `operation_type` 决定。
- `add` 增加对应批次 `quantity`；`loss` 与 `deduct` 扣减对应批次 `quantity`。
- 扣减后数量不能小于 `0`，否则应用层返回 `409 / conflict`。
- 写入操作记录与更新 `batches.quantity` 必须在同一事务内完成。
- v1 不根据操作结果修改批次 `status`。
- 撤销操作通过创建一条反向操作记录实现，不删除原操作。
- `reversed_operation_id` 对原操作唯一，保证每条操作最多只能被撤销一次。
- 撤销操作本身不能再次撤销，避免形成撤销链。

## 表：batch_qr_credentials

批次二维码凭证表。二维码内容为 `OB1|{batch_code}|{token}`；数据库只保存
`sha256(token + QR_TOKEN_PEPPER)`，不保存明文 token。

| 字段 | 数据库类型 | 空值 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | 否 | 自增 | 主键 | 凭证 ID |
| `batch_id` | `integer` | 否 | 无 | 外键/索引 | 关联 `batches.id` |
| `batch_code` | `varchar(255)` | 否 | 无 | 索引 | 签发时的批次号快照 |
| `token_hash` | `varchar(64)` | 否 | 无 | 唯一 | token 的 SHA-256 哈希 |
| `issued_at` | `timestamp with time zone` | 否 | `NOW()` | - | 签发时间 |
| `revoked_at` | `timestamp with time zone` | 是 | 无 | 索引 | 吊销时间，`null` 表示未吊销 |
| `created_by` | `varchar(255)` | 是 | 无 | - | 签发来源或用户标识 |

### 业务约定

- 批次创建时自动签发一条凭证。
- 标签打印接口读取标签载荷时会签发一条新的可打印凭证并返回明文二维码；`created_by` 记录当前登录用户；旧的未吊销凭证继续有效。
- 历史补发命令只补齐凭证记录，不输出明文 token；历史批次如需打印标签，应调用标签接口生成可打印二维码。
- 吊销凭证后，使用对应二维码扫码会返回 `revoked`。

## 表：qr_scan_audit_logs

二维码扫码审计表。所有扫码请求都应落审计，包括格式错误、token 错误、吊销和批次不存在。

| 字段 | 数据库类型 | 空值 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(40)` | 否 | 应用层生成 | 主键 | 审计 ID，格式为 `scan_<uuid>` |
| `raw_qr` | `text` | 否 | 无 | - | 原始二维码内容 |
| `batch_id` | `integer` | 是 | 无 | 外键/索引 | 匹配到的批次 ID |
| `batch_code` | `varchar(255)` | 是 | 无 | - | 解析或匹配到的批次号 |
| `source` | `varchar(50)` | 否 | 无 | 索引 | `web_camera`、`mobile_camera`、`handheld` |
| `device_id` | `varchar(255)` | 是 | 无 | 索引 | 扫码设备标识 |
| `client_scan_id` | `varchar(255)` | 是 | 无 | 索引 | 客户端扫码 ID，用于去重 |
| `scanner_user` | `varchar(255)` | 是 | 无 | - | 扫码用户标识，登录请求记录当前用户 |
| `scanned_at_client` | `timestamp with time zone` | 是 | 无 | - | 客户端扫码时间 |
| `scanned_at_server` | `timestamp with time zone` | 否 | `NOW()` | 索引 | 服务端接收时间 |
| `ip_address` | `inet` | 是 | 无 | - | 请求 IP |
| `user_agent` | `text` | 是 | 无 | - | 请求 UA |
| `result_status` | `varchar(20)` | 否 | 无 | 索引 | 扫码结果状态 |
| `result_message` | `text` | 否 | 无 | - | 展示给前端的结果信息 |
| `failure_reason` | `varchar(255)` | 是 | 无 | - | 失败原因，成功时为空 |

### 业务约定

- `client_scan_id` 非空时，应用层按 `source + device_id + client_scan_id` 查重，命中则返回首次审计结果，不新增审计记录。
- 效期状态由服务端当前日期和 `batches.expire_date` 计算，不信任二维码内容。
- 临期阈值由 `QR_SCAN_NEAR_EXPIRY_DAYS` 配置控制，当前默认 `7` 天。

## PostgreSQL DDL 参考

以下 DDL 用于表达当前 model 期望的结构。生产库如已存在表结构，应先对比差异后再执行变更。

```sql
CREATE TABLE accounts_auth_tokens (
    id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id integer NOT NULL REFERENCES auth_user(id),
    token_hash varchar(64) NOT NULL UNIQUE,
    issued_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone
);

CREATE TABLE product (
    id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    barcode varchar(255) NOT NULL UNIQUE,
    product_name varchar(255) NOT NULL,
    shelf_life_days integer NOT NULL,
    location varchar(255),
    category varchar(255),
    unit varchar(255),
    created_at timestamp with time zone NOT NULL DEFAULT NOW(),
    updated_at timestamp with time zone NOT NULL DEFAULT NOW(),
    manufacturer text NOT NULL
);

CREATE TABLE batches (
    id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    product_id bigint NOT NULL REFERENCES product(id),
    batch_code varchar(255) NOT NULL,
    quantity numeric(12, 2),
    received_at timestamp with time zone NOT NULL DEFAULT NOW(),
    manufacture_date date,
    expire_date date,
    status varchar(255),
    remarks varchar(255)
);

CREATE TABLE batch_operations (
    id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    batch_id integer NOT NULL REFERENCES batches(id),
    reversed_operation_id bigint UNIQUE REFERENCES batch_operations(id),
    operation_type varchar(20) NOT NULL,
    quantity numeric(12, 2) NOT NULL,
    quantity_after numeric(12, 2) NOT NULL,
    remarks varchar(255),
    created_at timestamp with time zone NOT NULL DEFAULT NOW(),
    CONSTRAINT batch_operations_operation_type_check
        CHECK (operation_type IN ('add', 'loss', 'deduct')),
    CONSTRAINT batch_operations_quantity_positive_check CHECK (quantity > 0),
    CONSTRAINT batch_operations_quantity_after_non_negative_check CHECK (quantity_after >= 0)
);

CREATE TABLE batch_qr_credentials (
    id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    batch_id integer NOT NULL REFERENCES batches(id),
    batch_code varchar(255) NOT NULL,
    token_hash varchar(64) NOT NULL UNIQUE,
    issued_at timestamp with time zone NOT NULL DEFAULT NOW(),
    revoked_at timestamp with time zone,
    created_by varchar(255)
);

CREATE TABLE qr_scan_audit_logs (
    id varchar(40) PRIMARY KEY,
    raw_qr text NOT NULL,
    batch_id integer REFERENCES batches(id),
    batch_code varchar(255),
    source varchar(50) NOT NULL,
    device_id varchar(255),
    client_scan_id varchar(255),
    scanner_user varchar(255),
    scanned_at_client timestamp with time zone,
    scanned_at_server timestamp with time zone NOT NULL DEFAULT NOW(),
    ip_address inet,
    user_agent text,
    result_status varchar(20) NOT NULL,
    result_message text NOT NULL,
    failure_reason varchar(255),
    CONSTRAINT qr_scan_audit_logs_source_check
        CHECK (source IN ('web_camera', 'mobile_camera', 'handheld')),
    CONSTRAINT qr_scan_audit_logs_result_status_check
        CHECK (result_status IN ('valid', 'near_expiry', 'expired', 'invalid', 'revoked', 'not_found'))
);
```

## 建议索引

当前 Django model 仅声明了 `product.barcode` 唯一约束和主外键关系。结合现有查询模式，
建议数据库至少具备以下索引：

```sql
CREATE INDEX IF NOT EXISTS acct_auth_user_exp_idx
    ON accounts_auth_tokens(user_id, expires_at);
CREATE INDEX IF NOT EXISTS acct_auth_revoked_idx
    ON accounts_auth_tokens(revoked_at);
CREATE INDEX IF NOT EXISTS batches_product_id_idx ON batches(product_id);
CREATE INDEX IF NOT EXISTS batches_status_idx ON batches(status);
CREATE INDEX IF NOT EXISTS batches_expire_date_idx ON batches(expire_date);
CREATE INDEX IF NOT EXISTS batches_received_at_id_idx ON batches(received_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS product_category_idx ON product(category);
CREATE INDEX IF NOT EXISTS batch_ops_batch_created_idx
    ON batch_operations(batch_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS batch_operations_type_idx ON batch_operations(operation_type);
CREATE INDEX IF NOT EXISTS batch_qr_batch_rev_idx
    ON batch_qr_credentials(batch_id, revoked_at);
CREATE INDEX IF NOT EXISTS batch_qr_credentials_code_idx
    ON batch_qr_credentials(batch_code);
CREATE INDEX IF NOT EXISTS qr_audit_batch_scan_idx
    ON qr_scan_audit_logs(batch_id, scanned_at_server DESC);
CREATE INDEX IF NOT EXISTS qr_audit_client_scan_idx
    ON qr_scan_audit_logs(source, device_id, client_scan_id);
CREATE INDEX IF NOT EXISTS qr_scan_audit_logs_status_idx
    ON qr_scan_audit_logs(result_status);
```

如需优化商品模糊搜索，可考虑为常用搜索字段增加 PostgreSQL trigram 索引；这属于性能优化，
不属于当前 model 的硬性结构要求。

## 效期预警索引说明

临期预警接口会按批次状态、到期日、商品 ID 过滤，并按到期日参与排序。由于 `Product` 与 `Batch` 当前均为 `managed = False`，以下索引需要通过数据库维护流程执行，不能依赖 Django migration 自动维护业务表结构。

```sql
CREATE INDEX IF NOT EXISTS batches_expire_date_idx ON batches(expire_date);
CREATE INDEX IF NOT EXISTS batches_status_idx ON batches(status);
CREATE INDEX IF NOT EXISTS batches_product_id_idx ON batches(product_id);
```
