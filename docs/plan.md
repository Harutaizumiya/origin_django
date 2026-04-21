# origin_backend（supabase_dev）-> Django 迁移计划

## 1. 计划基线
本计划以 `origin_backend` 的 `supabase_dev` 分支为唯一事实来源，并按你最新要求调整目标：

- Django 作为新的后端框架
- 业务数据库后端统一迁移到 Supabase
- `users` 模块只保留基础结构，不接入实际业务

这意味着迁移目标已经不再是“把一个混合数据源的 FastAPI 项目迁移为 Django，并保留 Supabase 演进方向”，而是：

- 把当前 FastAPI 项目迁移为 Django
- 把当前分散在 MySQL / Supabase 的业务数据统一收敛到 Supabase
- 在第一阶段只实现 `product` 和 `batches` 的真实业务迁移
- `users` 只搭骨架，不接实际数据库业务流、不挂正式业务职责

## 2. 当前分支现状梳理

### 2.1 框架与入口
当前项目仍是 FastAPI：

- `origin_backend.py` 负责应用创建、路由挂载和首页 HTML 返回
- `middleware/cors.py` 处理跨域
- `routers/` 下拆分 `product`、`batches`、`users`

### 2.2 数据源现状
当前数据访问是过渡中的混合状态：

#### Product
`routers/product.py` 已接入 Supabase：

- 新增商品：`table("product").insert(...)`
- 更新商品：`table("product").update(...).eq("id", product_id)`
- 删除商品：`table("product").delete().eq("id", product_id)`
- 商品查询：`table("product").select(...)`
- 分类查询：基于 Supabase `product` 表

#### Users
`routers/users.py` 仍直接依赖 MySQL：

- `database.py`
- `mysql.connector`
- 原始 SQL

#### Batches
`routers/batches.py` 也仍直接依赖 MySQL：

- 创建批次时先查 MySQL 中 `product` 的 `shelf_life_days`
- 列表查询时 `JOIN product`
- 到期日计算和分页依赖 SQL

### 2.3 当前最关键的问题
现在真正的问题不是“代码风格不统一”，而是数据源策略已经冲突：

- `product` 已经在 Supabase 方向上运行
- `batches` 仍然假定 `product` 在 MySQL
- `users` 仍是 MySQL 示例式实现
- 运行时存在跨数据源依赖和事实来源不一致的问题

如果不直接把业务数据库统一到 Supabase，后续继续开发时 `product` 与 `batches` 的关联关系会越来越难维护。

## 3. 迁移总目标
这次迁移要一次性完成三件事：

1. 把 FastAPI 项目迁移为 Django 项目
2. 把真实业务数据后端统一迁移到 Supabase
3. 将 `users` 模块降级为基础结构模块，只保留骨架，不接入实际业务

### 3.1 功能目标
- 保留首页能力
- 保留 `product` 现有核心能力
- 保留 `batches` 现有核心能力
- 让 `product` 与 `batches` 最终共用 Supabase 数据源
- `users` 不作为第一阶段真实业务模块，只保留后续扩展入口

### 3.2 架构目标
- 用 Django 标准项目结构替代 FastAPI 入口结构
- 建立清晰分层：`views`、`services`、`gateways`、`schemas`
- 运行时只保留 Supabase 作为业务数据源
- MySQL 只在迁移脚本、校验脚本中出现，不进入 Django 运行时主链路

### 3.3 工程目标
- 补齐依赖、配置和启动说明
- 使用 `.env` 管理 Supabase 连接参数
- 将错误处理、响应结构、校验逻辑收敛到统一层
- 为后续认证、后台、定时任务预留结构

### 3.4 范围边界
本次迁移明确不做以下事情：

- 不把 `users` 做成真实业务模块
- 不在第一阶段完成完整用户认证体系
- 不要求一开始就把所有 Supabase 表都改造成 Django ORM 直连

## 4. 迁移核心判断

### 4.1 运行时必须改单一数据源
既然目标已经确定为“数据库后端全部换成 Supabase”，那 Django 运行时不应该继续保留 MySQL gateway。

结论：

- 运行时业务访问统一走 Supabase
- MySQL 只用于一次性数据迁移、校验或回溯
- `product` 和 `batches` 必须在迁移后共用同一套 Supabase 表结构
- `users` 不接业务，因此不需要继续保留 MySQL 运行时逻辑

### 4.2 第一阶段采用“Django + 服务层 + Supabase 单数据源”
建议的第一阶段方案：

- Django 负责路由、配置、请求处理、模板、错误处理
- `product` 通过 Supabase gateway 访问
- `batches` 通过 Supabase gateway 访问
- `users` 只保留 schema / service / app 骨架，不接真实业务数据流
- MySQL 只出现在独立迁移脚本或导数脚本中

这是符合你当前目标的方案，不再保留双数据源运行策略。

## 5. 推荐目标结构
建议在 `origin_django` 中采用如下目录：

```text
origin_django/
├─ docs/
│  └─ plan.md
├─ manage.py
├─ pyproject.toml
├─ README.md
├─ .env.example
├─ config/
│  ├─ __init__.py
│  ├─ settings.py
│  ├─ urls.py
│  ├─ asgi.py
│  └─ wsgi.py
├─ common/
│  ├─ __init__.py
│  ├─ responses.py
│  ├─ exceptions.py
│  ├─ logging.py
│  └─ env.py
├─ inventory/
│  ├─ __init__.py
│  ├─ apps.py
│  ├─ urls.py
│  ├─ views/
│  │  ├─ __init__.py
│  │  ├─ product_views.py
│  │  └─ batch_views.py
│  ├─ services/
│  │  ├─ __init__.py
│  │  ├─ product_service.py
│  │  └─ batch_service.py
│  ├─ gateways/
│  │  ├─ __init__.py
│  │  └─ supabase_gateway.py
│  ├─ schemas/
│  │  ├─ __init__.py
│  │  ├─ product.py
│  │  └─ batch.py
│  └─ tests/
│     ├─ __init__.py
│     ├─ test_products.py
│     └─ test_batches.py
├─ accounts/
│  ├─ __init__.py
│  ├─ apps.py
│  ├─ models.py
│  ├─ services.py
│  ├─ schemas.py
│  └─ tests/
│     ├─ __init__.py
│     └─ test_accounts_structure.py
├─ scripts/
│  ├─ migrate_mysql_to_supabase.py
│  └─ verify_supabase_data.py
├─ templates/
│  └─ index.html
└─ static/
```

说明：

- `inventory/` 承接真实业务模块 `product` 和 `batches`
- `accounts/` 只保留用户基础结构，不承载实际业务逻辑
- `scripts/` 用于一次性数据迁移与校验
- Django 运行时不再依赖 MySQL gateway

## 6. 数据源策略
这是本次计划的硬约束，不是可选分支。

### 目标策略：Supabase 单数据源运行
迁移完成后的目标状态：

- `product` 使用 Supabase
- `batches` 使用 Supabase
- Django 运行时业务读写统一走 Supabase
- MySQL 不再作为线上运行数据源

### Users 的特殊处理
`users` 不进入实际业务，因此按以下原则处理：

- 只在 Django 中保留基础 app 结构
- 只定义最小模型/Schema/Service 占位
- 不接入实际 Supabase 用户表
- 不接入当前 MySQL 用户表
- 不把它挂到当前业务 API 主链路中

换句话说，`users` 在本阶段的目标不是“迁移完成”，而是“为后续可能的账号体系预留位置”。

### MySQL 的角色
MySQL 在迁移后的职责只剩两类：

- 历史数据导出来源
- 迁移结果比对来源

不再承担运行时职责。

## 7. Supabase 侧目标设计
在正式编码前，需要先把 Supabase 当作真实业务后端来设计，而不是简单把现有接口调用搬过去。

### 7.1 Product
目标表至少覆盖：

- `id`
- `barcode`
- `product_name`
- `shelf_life_days`
- `location`
- `category`
- `unit`
- `manufacturer`
- `created_at`
- `updated_at`

### 7.2 Batches
目标表至少覆盖：

- `id`
- `product_id`
- `batch_code`
- `quantity`
- `manufacture_date`
- `expire_date`
- `status`
- `remarks`
- `received_at`
- `created_at`
- `updated_at`

### 7.3 关系约束
需要确认或补齐以下 Supabase 设计：

- `batches.product_id -> product.id` 外键关系
- `batch_code` 唯一约束
- `barcode` 唯一约束
- 状态字段的允许值
- 时间字段默认值与更新时间策略

### 7.4 RLS 与权限
在 Supabase 上至少要明确：

- 当前 Django 使用的是 service role key 还是普通 anon key
- 是否启用 RLS
- 若启用 RLS，Django 服务访问策略如何配置

这一步如果不先确认，后续接口迁移会反复卡在权限错误上。

## 8. Product 模块迁移计划
`product` 是当前最适合先落地的模块。

### 第一阶段目标
- 在 Django 中完整复刻 `product` 的现有接口行为
- 保持 Supabase 作为唯一真实数据源
- 将当前散落在 `routers/product.py` 的 Supabase 调用收拢到 gateway/service 层

### 迁移建议
- `ProductCreate` / `ProductUpdate` 转为 Django 侧 schema/serializer
- `views/product_views.py` 只负责请求和响应
- `product_service.py` 负责业务校验与异常语义
- `supabase_gateway.py` 负责 `.table("product")...execute()` 的底层调用

### 注意点
- 保持 `code`、`message`、`data` 等响应字段兼容
- 保留 `23505` 等唯一约束错误码的翻译逻辑
- `manufacturer` 字段必须纳入正式迁移范围

## 9. Batches 模块迁移计划
`batches` 是这次迁移的核心模块，因为它必须从 MySQL 迁到 Supabase，并与 `product` 回到同一数据源。

### 第一阶段目标
- 让 `batches` 在 Django 下完全脱离 MySQL 运行
- 在 Supabase 中建立与 `product` 一致的关联关系
- 修复当前依赖 MySQL `JOIN product` 的实现方式

### 迁移建议
- 新建 Supabase `batches` 表或确认既有表结构
- 用 service 层负责：
  - 批次创建
  - 到期日推导
  - 列表筛选
  - 分页
  - 过期判断
- 不再通过 MySQL SQL 直接关联 `product`
- 批次相关查询统一改为 Supabase 读取

### 必须修复的问题
- `expire_date` / `expiry_date` 命名统一
- `received_date` / `received_at` 排序字段统一
- 批次状态枚举统一
- 到期日计算逻辑从临时 SQL 逻辑改成明确的 service 逻辑

## 10. Users 模块处理计划
`users` 模块按你的要求只保留基础结构，不接入实际业务。

### 目标
- 保留一个基础 `accounts`/`users` 结构，方便后续扩展
- 不提供正式业务接口
- 不接入当前 MySQL 用户表
- 不接入 Supabase 用户业务表
- 不参与当前 `product` / `batches` 业务链路

### 建议实现范围
第一阶段只保留以下内容：

- `accounts/apps.py`
- `accounts/models.py` 中的最小占位模型或注释性结构
- `accounts/schemas.py`
- `accounts/services.py` 中的空实现或占位函数
- 一份结构性测试，确保模块可导入

### 明确不做的内容
- 不迁移 `/users/create/<name>`、`/users/delete/<id>`、`/users/get/<id>` 为正式业务接口
- 不绑定实际数据库表
- 不做登录注册
- 不做权限体系
- 不做 Django Admin 的用户管理落地

如果后续需要账号体系，再单独立项设计，不和本次 `product` / `batches` 迁移捆绑。

## 11. Django 技术选型建议

### 11.1 是否引入 DRF
建议直接引入 `djangorestframework`。

原因：
- 当前项目本质上是 API 项目
- 更容易替代 FastAPI + Pydantic 的输入校验习惯
- 后续分页、错误处理、测试更顺手

### 11.2 是否使用 Django ORM 承接业务表
第一阶段不强制把 Supabase 业务表全部映射为 Django ORM 模型。

建议：
- 先通过 Supabase gateway 跑通业务
- Django ORM 只保留给本地辅助模型或未来扩展使用
- 等 Supabase 表结构、权限和访问方式稳定后，再决定是否补 ORM 映射

### 11.3 环境变量建议
至少需要：

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `SUPABASE_URL`
- `SUPABASE_KEY`

如果后续准备让 Django 直连 Supabase Postgres，再增加：
- `SUPABASE_DB_HOST`
- `SUPABASE_DB_PORT`
- `SUPABASE_DB_NAME`
- `SUPABASE_DB_USER`
- `SUPABASE_DB_PASSWORD`

## 12. 分阶段实施方案

## Phase 0：盘点现状与目标表结构
目标：确认 MySQL 历史数据与 Supabase 目标结构。

任务：
- 盘点当前 Supabase `product` 表结构
- 盘点当前 MySQL `batches` 和 `users` 表结构
- 确认 Supabase 是否已有 `batches` 目标表
- 确认 `product` 与 `batches` 的目标字段命名
- 确认 RLS、权限策略和 key 的使用方式

产出：
- Supabase 目标表结构文档
- MySQL -> Supabase 字段映射表
- 一份明确的数据迁移清单

## Phase 1：搭建 Django 项目骨架
目标：让 Django 项目跑起来，并从一开始按 Supabase 单数据源组织。

任务：
- 初始化 `origin_django`
- 建立 `config/`
- 建立 `inventory` app
- 建立 `accounts` 占位 app
- 配置模板、首页、CORS、环境变量读取
- 补齐依赖与 README

建议依赖：
- `django`
- `djangorestframework`
- `django-cors-headers`
- `python-dotenv`
- `requests`
- `supabase`
- `postgrest`

## Phase 2：设计并落地 Supabase 业务表
目标：让 `product` 与 `batches` 在 Supabase 上拥有统一结构。

任务：
- 校正 `product` 表结构
- 设计或创建 `batches` 表结构
- 建立 `product` 与 `batches` 的关联约束
- 确认唯一键、默认值和时间字段策略
- 记录 Supabase 初始化 SQL 或建表说明

## Phase 3：执行数据迁移
目标：把运行所需的业务数据从 MySQL 迁到 Supabase。

任务：
- 编写 `scripts/migrate_mysql_to_supabase.py`
- 迁移 `product` 历史数据（如有 MySQL 残留）
- 迁移 `batches` 历史数据
- 校验迁移前后记录数和关键字段
- 编写 `scripts/verify_supabase_data.py`

说明：
- `users` 不做实际业务迁移
- 只保留结构，不迁业务数据

## Phase 4：迁移 Django 接口层
目标：让 Django 正式接管 `product` 与 `batches` 的业务访问。

任务：
- 迁移首页 `/`
- 迁移 `product` 相关接口
- 迁移 `batches` 相关接口
- 统一错误处理和响应格式
- 去掉运行时对 MySQL 的依赖

## Phase 5：补 Users 骨架
目标：按要求完成 `users` 基础结构，但不接业务。

任务：
- 建立 `accounts` app
- 提供最小 schema / service / model 占位
- 写清楚该模块当前不接实际业务
- 加入一份结构性测试

## Phase 6：测试与验收
目标：确保迁移后的系统真正切换到 Supabase 运行。

任务：
- 为 `product` 编写接口测试
- 为 `batches` 编写接口测试
- 验证首页和核心 API
- 验证 Supabase 配置缺失时的报错路径
- 验证批次与商品关联逻辑
- 验证迁移脚本和校验脚本可执行
- 执行 `python manage.py check`
- 执行测试命令

## 13. 风险清单

### 风险 1：Supabase 表结构不完整
后果：
- Django 接口迁过去后无法稳定运行
- `batches` 无法正确关联 `product`

应对：
- 在 Phase 2 先确认表结构和约束，再迁接口

### 风险 2：历史 MySQL 数据迁移质量不稳定
后果：
- 批次和商品数据对不上
- 到期日、状态、时间字段出现偏差

应对：
- 编写独立迁移脚本和校验脚本
- 不把迁移逻辑塞进运行时接口

### 风险 3：RLS / 权限策略导致 Django 无法正常访问
后果：
- 接口在本地或线上表现不一致

应对：
- 提前确认 service role key 与权限策略
- 在计划中把权限检查前置

### 风险 4：Users 结构被误做成真实业务
后果：
- 范围膨胀
- 延误核心业务迁移

应对：
- 明确 `users` 只保留骨架
- 不挂正式业务路由，不接真实数据表

## 14. 第一阶段完成标准
满足以下条件可视为第一阶段迁移完成：

- Django 项目可启动
- 首页 `/` 可访问
- `product` 接口在 Django 下可正常访问 Supabase
- `batches` 接口在 Django 下可正常访问 Supabase
- Django 运行时不再依赖 MySQL
- 有可执行的数据迁移脚本和校验脚本
- `users` 模块已建立基础结构，但没有接入实际业务
- 环境变量替代硬编码配置
- 有基本测试和验证步骤

## 15. 建议执行顺序
按你现在的目标，建议顺序如下：

1. 盘点 Supabase `product` 和目标 `batches` 表结构
2. 初始化 Django 项目骨架
3. 建立 Supabase gateway / service 分层
4. 先落地 `batches` 的 Supabase 表设计
5. 编写 MySQL -> Supabase 数据迁移脚本
6. 迁移 `product` 接口
7. 迁移 `batches` 接口
8. 最后补 `users` 骨架
9. 补测试、README、环境变量模板

## 16. 下一步建议
基于这份更新后的计划，下一步最合理的动作是：

1. 先确认 Supabase 上 `product` 的真实表结构
2. 立即设计 `batches` 的 Supabase 目标表
3. 再开始在 `origin_django` 里初始化 Django 项目和业务分层

这次迁移的关键不是先把所有旧代码搬到 Django，而是先确保：

- 运行时只剩 Supabase 一个业务数据源
- `product` 与 `batches` 最终站在同一数据后端上
- `users` 不拖慢主迁移路径，只保留基础结构
