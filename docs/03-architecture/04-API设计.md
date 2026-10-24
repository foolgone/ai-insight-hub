# AI Insight Hub - API 接口文档

> **文档版本**：v1.1  
> **创建日期**：2026年10月23日  
> **最后更新**：2026年10月24日  
> **API 版本**：v1  
> **Base URL**：`http://localhost:8000/api/v1`（与 `backend/.env.example` 的 `API_V1_PREFIX=/api/v1` 一致）  
> **认证方式**：JWT Bearer Token（access 60 分钟 / refresh 7 天）  
> **路径口径**：所有接口均以 `/api/v1/datasources` 为基准（**不是** `data_sources`）；清洗接口固定为 `POST /api/v1/datasources/{datasource_id}/clean`

---

## 📋 目录

1. [API 概述](#1-api-概述)
2. [认证](#2-认证)
3. [通用规范](#3-通用规范)
4. [用户管理](#4-用户管理)
5. [数据源管理](#5-数据源管理)
6. [数据处理](#6-数据处理)
7. [分析与评估](#7-分析与评估)
8. [知识库](#8-知识库)
9. [报告](#9-报告)
10. [任务管理](#10-任务管理)
11. [API Key 管理（Phase 2）](#11-api-key-管理phase-2)
12. [错误码](#12-错误码)
13. [Webhook（Phase 2）](#13-webhookphase-2)

---

## 1. API 概述

### 1.1 API 特性

- ✅ RESTful 风格
- ✅ JWT 认证（access + refresh）
- ✅ 分页支持
- ✅ 过滤和排序
- ✅ 速率限制（60 请求/分钟，`RATE_LIMIT_PER_MINUTE=60`）
- ✅ 自动生成文档（Swagger）

---

### 1.2 快速开始

```bash
# 1. 注册用户
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass123","name":"User"}'

# 2. 登录获取 access_token + refresh_token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass123"}'

# 3. 使用 access_token 访问 API
curl -X GET http://localhost:8000/api/v1/datasources \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# 4. access_token 过期后用 refresh_token 换新
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"YOUR_REFRESH_TOKEN"}'
```

---

### 1.3 路径约定

| 规则 | 说明 | 示例 |
|---|---|---|
| 统一前缀 | 所有业务接口都在 `/api/v1` 下 | `/api/v1/datasources` |
| 集合归属于数据源 | 子资源用嵌套路径 | `/api/v1/datasources/{datasource_id}/cleaned-data` |
| 子资源单体 | 嵌套 + 自身 id | `/api/v1/datasources/{datasource_id}/knowledge/faq/{faq_id}` |
| 跨数据源的全局资源 | 顶层路径，用查询参数过滤 | `/api/v1/tasks?datasource_id=...`、`/api/v1/reports/{report_id}` |
| 命名 | 复数、短横线分隔，**不用下划线** | `cleaned-data` ✅ / `cleaned_data` ❌ |
| 更新语义 | 局部更新用 `PATCH`，不用 `PUT` | `PATCH /api/v1/datasources/{datasource_id}` |
| 资源 ID | **纯 UUID**（与库表 `UUID` 类型一致），不加 `ds_`/`task_`/`cd_` 前缀 | `550e8400-e29b-41d4-a716-446655440000` |

---

## 2. 认证

### 2.1 注册

**POST** `/api/v1/auth/register`

**所需角色**：匿名（无需认证）

**请求体**：
```json
{
  "email": "user@example.com",
  "password": "secure_password",
  "name": "John Doe"
}
```

**响应**：
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "user",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**状态码**：
- `201`: 创建成功
- `400`: 参数错误
- `409`: 邮箱已存在（`USER_EMAIL_EXISTS`）

---

### 2.2 登录

**POST** `/api/v1/auth/login`

**所需角色**：匿名（凭据即认证）

**请求体**：
```json
{
  "email": "user@example.com",
  "password": "secure_password"
}
```

**响应**：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJ0eXAiOiJhY2Nlc3MiLCJleHAiOjE3MzY5NDUwMDB9.signature",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJ0eXAiOiJyZWZyZXNoIiwiZXhwIjoxNzM3NTQ5ODAwfQ.signature",
  "token_type": "bearer",
  "expires_in": 3600,
  "refresh_expires_in": 604800,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "name": "John Doe",
    "role": "user"
  }
}
```

**字段说明**：

| 字段 | 说明 |
|---|---|
| `access_token` | 访问令牌，有效期 `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60`（`expires_in=3600` 秒） |
| `refresh_token` | 刷新令牌，有效期 `JWT_REFRESH_TOKEN_EXPIRE_DAYS=7`（`refresh_expires_in=604800` 秒） |
| `token_type` | 固定 `bearer` |

**状态码**：
- `200`: 登录成功
- `401`: 认证失败（`AUTH_INVALID_CREDENTIALS`）

> ⚠️ `refresh_token` 只能用于 `POST /api/v1/auth/refresh`，不能用于业务接口；业务接口只接受 `access_token`。

---

### 2.3 刷新 Token

**POST** `/api/v1/auth/refresh`

**所需角色**：持有有效 `refresh_token`

**请求体（推荐）**：
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJ0eXAiOiJyZWZyZXNoIiwiZXhwIjoxNzM1NDk4MDB9.signature"
}
```

**兼容方式（请求头）**：
```
Authorization: Bearer <refresh_token>
```

> 两种方式任选其一，服务端优先读请求体，请求体缺失时回退到 `Authorization` 头。

**响应**：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJ0eXAiOiJhY2Nlc3MiLCJleHAiOjE3MzY5NDg2MDB9.signature",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJ0eXAiOiJyZWZyZXNoIiwiZXhwIjoxNzM3NTUzNDAwfQ.signature",
  "token_type": "bearer",
  "expires_in": 3600,
  "refresh_expires_in": 604800
}
```

**状态码**：
- `200`: 刷新成功
- `401`: refresh token 无效/过期/已吊销（`AUTH_REFRESH_TOKEN_INVALID`）

> 刷新即轮换：旧 refresh token 立即失效（MVP 用 Redis 黑名单记录已吊销 `jti`，TTL = 剩余有效期）。

---

### 2.4 登出

**POST** `/api/v1/auth/logout`

**所需角色**：已登录用户

**请求头**：
```
Authorization: Bearer <access_token>
```

**请求体（可选，建议传以便同时吊销 refresh token）**：
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJ0eXAiOiJyZWZyZXNoIiwiZXhwIjoxNzM1NTM0MDB9.signature"
}
```

**响应**：
```json
{
  "message": "Logged out successfully"
}
```

> 实现：把 access token（及请求体里的 refresh token）的 `jti` 写入 Redis 黑名单，TTL 取其剩余有效期；黑名单内的 token 一律返回 `401 AUTH_TOKEN_EXPIRED`。

---

### 2.5 JWT 认证流程（时序）

```
① 注册/登录
   浏览器 --POST /auth/login {email,password}--> 后端
   后端 --校验 bcrypt--> 签发 access_token(60min) + refresh_token(7d) --> 浏览器
   浏览器：access_token 放内存/Zustand，refresh_token 落 httpOnly cookie 或安全存储

② 调用业务接口
   浏览器 --Authorization: Bearer <access_token>--> 后端
   后端：验签 → 校验 exp → 校验 Redis 黑名单 → 校验角色/归属 → 返回数据
   失败(expired) → 401 AUTH_TOKEN_EXPIRED

③ 刷新（access 过期后）
   浏览器 --POST /auth/refresh {refresh_token}--> 后端
   后端：验签 + 校验 type=refresh + 校验黑名单 → 吊销旧 refresh_token
        → 返回新 access_token + 新 refresh_token
   刷新失败 → 401 AUTH_REFRESH_TOKEN_INVALID → 前端跳登录页

④ 登出
   浏览器 --POST /auth/logout (Bearer access_token, body.refresh_token)--> 后端
   后端：两个 jti 入 Redis 黑名单（TTL=剩余有效期）→ 204/200
```

**Token 载荷（最小集）**：

| Claim | 说明 |
|---|---|
| `sub` | 用户 UUID |
| `role` | `admin` / `user` / `viewer` |
| `type` | `access` / `refresh` |
| `jti` | 唯一 ID，用于吊销 |
| `exp` / `iat` | 过期时间 / 签发时间 |

---

## 3. 通用规范

### 3.1 请求头

所有需要认证的接口都需要携带：

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

---

### 3.2 分页

**查询参数**：
- `page`: 页码（从 1 开始）
- `limit`: 每页数量（默认 20，最大 100）
- `sort`: 排序字段（前缀 `-` 表示降序）

**示例**：
```
GET /api/v1/datasources?page=2&limit=50&sort=-created_at
```

**响应结构**（`items` 的元素结构见各接口，此处省略）：
```json
{
  "items": [],
  "pagination": {
    "page": 2,
    "limit": 50,
    "total": 1000,
    "pages": 20,
    "has_next": true,
    "has_prev": true
  }
}
```

---

### 3.3 过滤

**查询参数**：
```
GET /api/v1/datasources?status=active&type=customer_service
```

---

### 3.4 错误响应

```json
{
  "error": {
    "code": "DATASOURCE_NOT_FOUND",
    "message": "Data source not found",
    "details": {
      "datasource_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  }
}
```

> 完整错误码见[第 12 节](#12-错误码)。

---

### 3.5 角色与接口权限（RBAC）

系统内置三种角色（对应 `users.role`）：`admin` / `user` / `viewer`。

**通用规则**：
- `admin`：可见并可操作**全部用户**的数据源、报告、任务；
- `user`：只能操作**自己创建**的数据源、报告、任务（越权访问返回 `403 AUTH_FORBIDDEN`）；
- `viewer`：只读；任何写操作（POST/PATCH/DELETE）返回 `403 AUTH_FORBIDDEN`；
- 所有接口默认要求已登录，`/auth/*` 与 Swagger 文档除外。

| 接口组 | admin | user | viewer | 匿名 |
|---|---|---|---|---|
| `POST /api/v1/auth/register`、`/login`、`/refresh` | ✅ | ✅ | ✅ | ✅ |
| `POST /api/v1/auth/logout` | ✅ | ✅ | ✅ | ❌ |
| `GET/PATCH /api/v1/users/me`、`POST /users/me/password` | ✅ | ✅ | 仅 GET | ❌ |
| `GET /api/v1/datasources`、`GET /api/v1/datasources/{id}` | ✅ 全部 | ✅ 自己的 | ✅ 只读 | ❌ |
| `POST/PATCH/DELETE /api/v1/datasources`（含 `/{id}`） | ✅ | ✅ 自己的 | ❌ | ❌ |
| `POST /api/v1/datasources/{id}/upload`、`POST .../clean` | ✅ | ✅ 自己的 | ❌ | ❌ |
| `GET /api/v1/datasources/{id}/cleaned-data`（含 `/{data_id}`） | ✅ | ✅ 自己的 | ✅ | ❌ |
| `POST /api/v1/datasources/{id}/analyze/quality`、`POST .../analyze/insights`、`POST .../extract-knowledge` | ✅ | ✅ 自己的 | ❌ | ❌ |
| `GET /api/v1/datasources/{id}/analysis/quality`、`GET .../analysis/insights` | ✅ | ✅ 自己的 | ✅ | ❌ |
| `GET /api/v1/datasources/{id}/knowledge/faq`、`.../search`、`.../gaps` | ✅ | ✅ 自己的 | ✅ | ❌ |
| `POST/PATCH/DELETE /api/v1/datasources/{id}/knowledge/faq`（含 `/{faq_id}`） | ✅ | ✅ 自己的 | ❌ | ❌ |
| `POST /api/v1/datasources/{id}/reports`、`DELETE /api/v1/reports/{id}` | ✅ | ✅ 自己的 | ❌ | ❌ |
| `GET /api/v1/reports/{id}`、`GET .../reports/{id}/download` | ✅ | ✅ 自己的 | ✅ | ❌ |
| `GET /api/v1/tasks`、`GET /api/v1/tasks/{task_id}` | ✅ 全部 | ✅ 自己的 | ✅ 只读 | ❌ |
| `POST /api/v1/tasks/{id}/cancel`、`POST .../retry` | ✅ | ✅ 自己的 | ❌ | ❌ |
| `/api/v1/api-keys`（Phase 2） | ✅ 全部 | ✅ 自己的 | ❌ | ❌ |
| `/api/v1/webhooks`（Phase 2） | ✅ 全部 | ✅ 自己的 | ❌ | ❌ |

> 数据归属判定：`data_sources.user_id == current_user.id`；报告/任务通过 `datasource_id` 间接归属。
> `/metrics`（Prometheus）不在 `/api/v1` 下，由 `PROMETHEUS_ENABLED` 控制，生产环境建议只对内网暴露。

---

## 4. 用户管理

### 4.1 获取当前用户信息

**GET** `/api/v1/users/me`

**所需角色**：admin / user / viewer

**响应**：
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "user",
  "quota": {
    "max_datasources": 10,
    "max_monthly_records": 100000,
    "max_monthly_tokens": 1000000
  },
  "usage": {
    "datasources_count": 3,
    "monthly_records": 15000,
    "monthly_tokens": 50000
  },
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

### 4.2 更新用户信息

**PATCH** `/api/v1/users/me`

**所需角色**：admin / user（viewer 不可写）

**请求体**：
```json
{
  "name": "New Name",
  "avatar_url": "https://example.com/avatar.jpg"
}
```

**响应**：
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "New Name",
  "avatar_url": "https://example.com/avatar.jpg",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

---

### 4.3 修改密码

**POST** `/api/v1/users/me/password`

**所需角色**：admin / user（viewer 不可写）

**请求体**：
```json
{
  "current_password": "old_password",
  "new_password": "new_password"
}
```

**响应**：
```json
{
  "message": "Password updated successfully"
}
```

**状态码**：
- `200`: 修改成功
- `400`: 原密码错误

---

## 5. 数据源管理

### 5.1 创建数据源

**POST** `/api/v1/datasources`

**所需角色**：admin / user（viewer ❌）

**请求体**：
```json
{
  "name": "客服对话-2025年1月",
  "description": "2025年1月的客服对话数据",
  "type": "customer_service",
  "config": {
    "auto_clean": true,
    "auto_evaluate": true,
    "evaluation_dimensions": ["accuracy", "completeness", "tone", "compliance", "hallucination"],
    "notification_email": "user@example.com"
  }
}
```

> `evaluation_dimensions` 默认值固定为 5 维：`accuracy` / `completeness` / `tone` / `compliance` / `hallucination`。

**响应**：
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "客服对话-2025年1月",
  "description": "2025年1月的客服对话数据",
  "type": "customer_service",
  "status": "active",
  "config": {
    "auto_clean": true,
    "auto_evaluate": true,
    "evaluation_dimensions": ["accuracy", "completeness", "tone", "compliance", "hallucination"],
    "notification_email": "user@example.com"
  },
  "statistics": {
    "total_records": 0,
    "cleaned_records": 0,
    "quality_score_avg": 0
  },
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**状态码**：
- `201`: 创建成功
- `400`: 参数错误
- `429`: 超出配额限制（`DATASOURCE_QUOTA_EXCEEDED`，如 `quota.max_datasources` 已用尽）

---

### 5.2 获取数据源列表

**GET** `/api/v1/datasources`

**所需角色**：admin（全部）/ user（仅自己的）/ viewer（只读）

**查询参数**：
- `page`: 页码
- `limit`: 每页数量
- `status`: 过滤状态（active/archived/processing/error）
- `type`: 过滤类型
- `sort`: 排序（`-created_at`）

**响应**：
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "客服对话-2025年1月",
      "type": "customer_service",
      "status": "active",
      "statistics": {
        "total_records": 1000,
        "cleaned_records": 950,
        "quality_score_avg": 85.5
      },
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 5,
    "pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

---

### 5.3 获取单个数据源

**GET** `/api/v1/datasources/{datasource_id}`

**所需角色**：admin（全部）/ user（自己的）/ viewer（只读）

**响应**：
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "客服对话-2025年1月",
  "description": "2025年1月的客服对话数据",
  "type": "customer_service",
  "status": "active",
  "config": {
    "auto_clean": true,
    "auto_evaluate": false,
    "evaluation_dimensions": ["accuracy", "completeness", "tone", "compliance", "hallucination"],
    "notification_email": "user@example.com"
  },
  "statistics": {
    "total_records": 1000,
    "cleaned_records": 950,
    "quality_score_avg": 85.5,
    "last_processed_at": "2025-01-15T10:30:00Z"
  },
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**状态码**：
- `200`: 成功
- `404`: 数据源不存在（`DATASOURCE_NOT_FOUND`）

---

### 5.4 更新数据源

**PATCH** `/api/v1/datasources/{datasource_id}`

**所需角色**：admin / user（自己的）；viewer ❌

**请求体**（局部更新，未传字段不变）：
```json
{
  "name": "新名称",
  "description": "新描述",
  "config": {
    "auto_clean": false
  }
}
```

**响应**：
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "新名称",
  "description": "新描述",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**状态码**：
- `200`: 更新成功
- `403`: 无权限（`AUTH_FORBIDDEN`）
- `404`: 数据源不存在（`DATASOURCE_NOT_FOUND`）

---

### 5.5 删除数据源

**DELETE** `/api/v1/datasources/{datasource_id}`

**所需角色**：admin / user（自己的）；viewer ❌

**查询参数**：
- `force`: 是否强制删除（删除所有关联数据）

**响应**：
```json
{
  "message": "Data source deleted successfully",
  "deleted_records": 1000
}
```

**状态码**：
- `200`: 删除成功
- `404`: 数据源不存在（`DATASOURCE_NOT_FOUND`）

---

## 6. 数据处理

### 6.1 上传文件

**POST** `/api/v1/datasources/{datasource_id}/upload`

**所需角色**：admin / user（自己的）；viewer ❌

**请求头**：
```
Content-Type: multipart/form-data
```

**请求体**：
```
file: <binary>
```

**响应**：
```json
{
  "task_id": "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
  "status": "pending",
  "message": "File uploaded, processing started",
  "file_info": {
    "filename": "data.csv",
    "size": 1024000,
    "mime_type": "text/csv"
  }
}
```

**支持格式**：CSV / JSON / Excel (xlsx) / TXT（`ALLOWED_UPLOAD_EXTENSIONS=csv,json,xlsx,txt`）

**文件大小限制**：50 MB（`MAX_UPLOAD_SIZE_MB=50`）

**状态码**：
- `202`: 已接收，异步处理中
- `413`: 文件过大（`FILE_TOO_LARGE`）
- `415`: 格式不支持（`FILE_FORMAT_INVALID`）

---

### 6.2 触发数据清洗

**POST** `/api/v1/datasources/{datasource_id}/clean`

**所需角色**：admin / user（自己的）；viewer ❌

**请求体**：
```json
{
  "data_ids": ["3f2504e0-4f89-41d3-9a0c-0305e82c3301"],
  "config": {
    "remove_duplicates": true,
    "normalize_text": true
  }
}
```

> `data_ids` 可选；不传（或传空数组）表示清洗该数据源下全部待处理记录。

**响应**：
```json
{
  "task_id": "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
  "status": "pending",
  "estimated_duration": 120,
  "message": "Cleaning task queued"
}
```

> `estimated_duration` 单位为秒，按历史平均耗时估算，仅用于前端展示。

**状态码**：
- `202`: 任务已入队
- `409`: 已有同类任务在运行（`TASK_ALREADY_RUNNING`）

---

### 6.3 获取清洗结果列表

**GET** `/api/v1/datasources/{datasource_id}/cleaned-data`

**所需角色**：admin / user（自己的）/ viewer（只读）

**查询参数**：
- `page`: 页码
- `limit`: 每页数量
- `quality_score_min`: 最低质量分（0–100）
- `quality_score_max`: 最高质量分（0–100）
- `has_issues`: 是否有问题（true/false）
- `date_from`: 开始日期
- `date_to`: 结束日期

**响应**：
```json
{
  "items": [
    {
      "id": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
      "dialogue_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "timestamp": "2025-01-15T10:30:00Z",
      "user_message": "iPhone 14 多少钱？",
      "ai_response": "iPhone 14 目前的价格是 5999 元起。",
      "quality_score": 95,
      "issues": [],
      "metadata": {
        "source": "zendesk",
        "session_id": "session_123"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 950,
    "pages": 48,
    "has_next": true,
    "has_prev": false
  }
}
```

---

### 6.4 获取单条清洗数据

**GET** `/api/v1/datasources/{datasource_id}/cleaned-data/{data_id}`

**所需角色**：admin / user（自己的）/ viewer（只读）

**响应**：
```json
{
  "id": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
  "dialogue_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "datasource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-01-15T10:30:00Z",
  "user_message": "iPhone 14 多少钱？",
  "ai_response": "iPhone 14 目前的价格是 5999 元起。",
  "metadata": {
    "source": "zendesk",
    "session_id": "session_123"
  },
  "quality_score": 95,
  "issues": [],
  "agent_version": "v1.2.0",
  "processing_duration": 1.2,
  "token_usage": {
    "input": 100,
    "output": 50
  },
  "created_at": "2025-01-15T10:30:00Z"
}
```

**状态码**：
- `200`: 成功
- `404`: 记录不存在（`CLEANED_DATA_NOT_FOUND`）

---

## 7. 分析与评估

### 7.1 触发质量评估

**POST** `/api/v1/datasources/{datasource_id}/analyze/quality`

**所需角色**：admin / user（自己的）；viewer ❌

**请求体**：
```json
{
  "data_ids": [],
  "dimensions": ["accuracy", "completeness", "tone", "compliance", "hallucination"],
  "threshold": 70,
  "include_knowledge_base": true
}
```

> `data_ids` 为空表示评估全部清洗后数据；`threshold` 为 0–100 的问题标记阈值；`dimensions` 默认即上面 5 维。

**响应**：
```json
{
  "task_id": "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
  "status": "pending",
  "estimated_duration": 300,
  "message": "Quality evaluation task queued"
}
```

**状态码**：
- `202`: 任务已入队
- `409`: 已有同类任务在运行（`TASK_ALREADY_RUNNING`）
- `429`: 当日/当月成本额度用尽（`INSUFFICIENT_CREDITS`，阈值见 `DAILY_COST_LIMIT` / `MONTHLY_COST_LIMIT`）

---

### 7.2 获取评估结果

**GET** `/api/v1/datasources/{datasource_id}/analysis/quality`

**所需角色**：admin / user（自己的）/ viewer（只读）

**查询参数**：
- `page`: 页码
- `limit`: 每页数量
- `score_min`: 最低分（0–100）
- `score_max`: 最高分（0–100）
- `has_issues`: 是否有问题
- `dimension`: 按维度过滤（accuracy/completeness/tone/compliance/hallucination）

**响应**：
```json
{
  "items": [
    {
      "id": "9b2f0e4c-1b5a-4f2e-9a3d-8c7b6a5d4e3f",
      "dialogue_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "overall_score": 85,
      "dimensions": {
        "accuracy": {
          "score": 90,
          "weight": 0.3,
          "issues": []
        },
        "completeness": {
          "score": 80,
          "weight": 0.2,
          "issues": ["incomplete"]
        },
        "tone": {
          "score": 88,
          "weight": 0.15,
          "issues": []
        },
        "compliance": {
          "score": 95,
          "weight": 0.15,
          "issues": []
        },
        "hallucination": {
          "score": 82,
          "weight": 0.2,
          "issues": ["price_uncertain"]
        }
      },
      "quality_level": "good",
      "needs_review": false,
      "suggestions": [
        "建议补充产品配置信息"
      ],
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 1000,
    "pages": 50,
    "has_next": true,
    "has_prev": false
  },
  "summary": {
    "total_evaluated": 1000,
    "avg_score": 82.5,
    "excellent_count": 300,
    "good_count": 500,
    "acceptable_count": 150,
    "poor_count": 50
  }
}
```

> 所有分数字段均为 **0–100** 量纲（不是 0–1）。

---

### 7.3 触发洞察分析

**POST** `/api/v1/datasources/{datasource_id}/analyze/insights`

**所需角色**：admin / user（自己的）；viewer ❌

**请求体**：
```json
{
  "time_range": {
    "start": "2025-01-01",
    "end": "2025-01-31"
  },
  "analyze_sentiment": true,
  "identify_trends": true,
  "find_pain_points": true
}
```

**响应**：
```json
{
  "task_id": "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
  "status": "pending"
}
```

**状态码**：
- `202`: 任务已入队
- `429`: 成本额度用尽（`INSUFFICIENT_CREDITS`）

---

### 7.4 获取洞察结果

**GET** `/api/v1/datasources/{datasource_id}/analysis/insights`

**所需角色**：admin / user（自己的）/ viewer（只读）

**响应**：
```json
{
  "datasource_id": "550e8400-e29b-41d4-a716-446655440000",
  "time_range": {
    "start": "2025-01-01",
    "end": "2025-01-31"
  },
  "intent_distribution": {
    "咨询": 450,
    "投诉": 300,
    "建议": 150,
    "其他": 100
  },
  "top_questions": [
    {
      "question": "退货政策",
      "frequency": 120,
      "category": "售后"
    }
  ],
  "sentiment_distribution": {
    "正面": 40,
    "中性": 50,
    "负面": 10
  },
  "pain_points": [
    {
      "issue": "退货流程复杂",
      "frequency": 50,
      "severity": "high",
      "suggestions": "简化退货流程"
    }
  ],
  "emerging_topics": [
    "新产品咨询增加 30%",
    "物流时效问题减少 15%"
  ],
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

## 8. 知识库

### 8.1 提取知识

**POST** `/api/v1/datasources/{datasource_id}/extract-knowledge`

**所需角色**：admin / user（自己的）；viewer ❌

**请求体**：
```json
{
  "min_frequency": 3,
  "similarity_threshold": 0.85,
  "max_faq_count": 100
}
```

**响应**：
```json
{
  "task_id": "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
  "status": "pending"
}
```

**状态码**：
- `202`: 任务已入队
- `429`: 成本额度用尽（`INSUFFICIENT_CREDITS`）

---

### 8.2 获取 FAQ 列表

**GET** `/api/v1/datasources/{datasource_id}/knowledge/faq`

**所需角色**：admin / user（自己的）/ viewer（只读）

**查询参数**：
- `category`: 分类（产品/售后/咨询）
- `min_frequency`: 最小出现次数
- `sort`: 排序（`-frequency`）

**响应**：
```json
{
  "items": [
    {
      "id": "8f14e45f-ceea-467a-9c1e-0f3c5d2b7a61",
      "question": "iPhone 14 多少钱？",
      "answer": "iPhone 14 目前的价格是 5999 元起，有多种配置可选。",
      "category": "产品",
      "frequency": 120,
      "confidence": 0.95,
      "quality_score": 88,
      "variations": [
        "iPhone 14 价格",
        "iPhone 14 售价多少"
      ],
      "tags": ["iPhone", "价格"],
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

---

### 8.3 搜索知识库

**GET** `/api/v1/datasources/{datasource_id}/knowledge/search`

**所需角色**：admin / user（自己的）/ viewer（只读）

**查询参数**：
- `q`: 搜索关键词
- `limit`: 结果数量（默认 10）
- `threshold`: 相似度阈值（0–1）

**响应**：
```json
{
  "query": "退货",
  "results": [
    {
      "id": "8f14e45f-ceea-467a-9c1e-0f3c5d2b7a61",
      "question": "如何退货？",
      "answer": "7 天内可以无理由退货...",
      "similarity": 0.95,
      "category": "售后"
    }
  ]
}
```

> 检索实现：MVP 用 `pg_trgm` 模糊匹配 + `embedding <=> query_vector` 余弦相似度混合排序（`VECTOR(384)`，HNSW 索引）。

---

### 8.4 获取知识盲区

**GET** `/api/v1/datasources/{datasource_id}/knowledge/gaps`

**所需角色**：admin / user（自己的）/ viewer（只读）

**响应**：
```json
{
  "gaps": [
    {
      "question": "支持分期付款吗？",
      "frequency": 25,
      "category": "支付",
      "priority": "high",
      "suggested_answer": null
    }
  ],
  "summary": {
    "total_gaps": 15,
    "high_priority": 5,
    "medium_priority": 7,
    "low_priority": 3
  }
}
```

---

### 8.5 创建 FAQ（手动）

**POST** `/api/v1/datasources/{datasource_id}/knowledge/faq`

**所需角色**：admin / user（自己的）；viewer ❌

**请求体**：
```json
{
  "question": "支持货到付款吗？",
  "answer": "是的，支持货到付款，但需要额外支付 10 元手续费。",
  "category": "支付",
  "tags": ["支付方式", "货到付款"]
}
```

**响应**：
```json
{
  "id": "8f14e45f-ceea-467a-9c1e-0f3c5d2b7a61",
  "question": "支持货到付款吗？",
  "answer": "是的，支持货到付款，但需要额外支付 10 元手续费。",
  "status": "active",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

### 8.6 更新 FAQ

**PATCH** `/api/v1/datasources/{datasource_id}/knowledge/faq/{faq_id}`

**所需角色**：admin / user（自己的）；viewer ❌

**请求体**：
```json
{
  "answer": "更新后的答案",
  "category": "新分类"
}
```

**响应**：同 8.5 的 FAQ 结构（返回更新后的对象）。

**状态码**：
- `200`: 更新成功
- `404`: FAQ 不存在（`FAQ_NOT_FOUND`）

---

### 8.7 删除 FAQ

**DELETE** `/api/v1/datasources/{datasource_id}/knowledge/faq/{faq_id}`

**所需角色**：admin / user（自己的）；viewer ❌

**状态码**：
- `204`: 删除成功
- `404`: FAQ 不存在（`FAQ_NOT_FOUND`）

---

## 9. 报告

### 9.1 生成报告

**POST** `/api/v1/datasources/{datasource_id}/reports`

**所需角色**：admin / user（自己的）；viewer ❌

**请求体**：
```json
{
  "title": "2025年1月质量分析报告",
  "report_type": "quality",
  "format": "pdf",
  "config": {
    "include_charts": true,
    "include_recommendations": true,
    "time_range": {
      "start": "2025-01-01",
      "end": "2025-01-31"
    }
  }
}
```

> 枚举口径（与 `reports` 表 CHECK 一致）：
> - `report_type`: `quality` / `knowledge` / `insight` / `comprehensive`
> - `format`: `pdf` / `excel` / `markdown` / `html`

**响应**：
```json
{
  "id": "b1d5f7a2-3c4e-4d6b-9f80-2a3b4c5d6e7f",
  "title": "2025年1月质量分析报告",
  "report_type": "quality",
  "format": "pdf",
  "status": "generating",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**状态码**：
- `202`: 已受理，生成中
- `422`: 格式/类型不在枚举内（`REPORT_FORMAT_INVALID`）
- `429`: 成本额度用尽（`INSUFFICIENT_CREDITS`）

---

### 9.2 获取报告列表

**GET** `/api/v1/datasources/{datasource_id}/reports`

**所需角色**：admin / user（自己的）/ viewer（只读）

**查询参数**：
- `report_type`: 报告类型
- `status`: 状态（generating/completed/failed）
- `sort`: 排序

**响应**：
```json
{
  "items": [
    {
      "id": "b1d5f7a2-3c4e-4d6b-9f80-2a3b4c5d6e7f",
      "title": "2025年1月质量分析报告",
      "report_type": "quality",
      "format": "pdf",
      "status": "completed",
      "file_url": "https://storage.example.com/reports/b1d5f7a2.pdf",
      "file_size": 1024000,
      "created_at": "2025-01-15T10:30:00Z",
      "completed_at": "2025-01-15T10:35:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 12,
    "pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

---

### 9.3 获取单个报告

**GET** `/api/v1/reports/{report_id}`

**所需角色**：admin（全部）/ user（自己的）/ viewer（只读）

**响应**：
```json
{
  "id": "b1d5f7a2-3c4e-4d6b-9f80-2a3b4c5d6e7f",
  "title": "2025年1月质量分析报告",
  "datasource_id": "550e8400-e29b-41d4-a716-446655440000",
  "report_type": "quality",
  "format": "pdf",
  "status": "completed",
  "file_url": "https://storage.example.com/reports/b1d5f7a2.pdf",
  "file_size": 1024000,
  "generation_duration": 45.2,
  "view_count": 10,
  "download_count": 3,
  "created_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T10:35:00Z",
  "expires_at": "2025-02-15T10:30:00Z"
}
```

**状态码**：
- `200`: 成功
- `404`: 报告不存在（`REPORT_NOT_FOUND`）

---

### 9.4 下载报告

**GET** `/api/v1/reports/{report_id}/download`

**所需角色**：admin（全部）/ user（自己的）/ viewer（只读）

**响应**：
- 重定向到预签名 URL（MinIO/S3）
- 或直接返回文件流

---

### 9.5 删除报告

**DELETE** `/api/v1/reports/{report_id}`

**所需角色**：admin / user（自己的）；viewer ❌

**状态码**：
- `204`: 删除成功
- `404`: 报告不存在（`REPORT_NOT_FOUND`）

---

## 10. 任务管理

### 10.1 获取任务状态

**GET** `/api/v1/tasks/{task_id}`

**所需角色**：admin（全部）/ user（自己的）/ viewer（只读）

**响应**：
```json
{
  "id": "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
  "task_type": "clean",
  "task_name": "数据清洗",
  "status": "running",
  "progress": 45,
  "current_step": "正在清洗第 450/1000 条",
  "started_at": "2025-01-15T10:30:00Z",
  "estimated_completion": "2025-01-15T10:32:00Z"
}
```

**状态**：
- `pending`: 排队中
- `running`: 运行中
- `completed`: 已完成
- `failed`: 失败
- `cancelled`: 已取消

---

### 10.2 获取任务列表

**GET** `/api/v1/tasks`

**所需角色**：admin（全部）/ user（自己的）/ viewer（只读）

**查询参数**：
- `datasource_id`: 数据源 ID
- `task_type`: 任务类型
- `status`: 状态

**响应**：
```json
{
  "items": [
    {
      "id": "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
      "task_type": "clean",
      "status": "completed",
      "progress": 100,
      "duration": 120.5,
      "created_at": "2025-01-15T10:30:00Z",
      "completed_at": "2025-01-15T10:32:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 30,
    "pages": 2,
    "has_next": true,
    "has_prev": false
  }
}
```

---

### 10.3 取消任务

**POST** `/api/v1/tasks/{task_id}/cancel`

**所需角色**：admin / user（自己的）；viewer ❌

**响应**：
```json
{
  "id": "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
  "status": "cancelled",
  "message": "Task cancelled successfully"
}
```

**状态码**：
- `200`: 取消成功
- `404`: 任务不存在（`TASK_NOT_FOUND`）
- `409`: 任务已结束无法取消（`TASK_NOT_CANCELLABLE`）

---

### 10.4 重试失败任务

**POST** `/api/v1/tasks/{task_id}/retry`

**所需角色**：admin / user（自己的）；viewer ❌

**响应**：
```json
{
  "id": "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
  "status": "pending",
  "retry_count": 1,
  "message": "Task queued for retry"
}
```

**状态码**：
- `202`: 已重新入队
- `409`: 任务不是失败状态（`TASK_NOT_RETRYABLE`）

---

## 11. API Key 管理（Phase 2）

> **MVP 不开放**：本节接口标记为 Phase 2，表 `api_keys` 已在数据库设计中落地（见 `03-数据库设计.md` 3.9），MVP 阶段仅支持 JWT 认证。
> 开放后，API Key 通过请求头 `X-API-Key: aih_xxx` 认证；作用域 `scopes` 取值为 `read` / `write` / `admin`。

### 11.1 创建 API Key

**POST** `/api/v1/api-keys`

**所需角色**：admin / user（Phase 2）

**请求体**：
```json
{
  "name": "报表导出脚本",
  "description": "CI 定时导出质量报告",
  "scopes": ["read"],
  "expires_at": "2026-01-15T00:00:00Z"
}
```

**响应**（`key` 明文仅在创建时返回一次）：
```json
{
  "id": "c2e6a8b4-5d7f-4e8a-b1c2-3d4e5f6a7b8c",
  "name": "报表导出脚本",
  "key": "aih_3f2504e04f8941d39a0c0305e82c3301",
  "key_prefix": "aih_3f25",
  "scopes": ["read"],
  "expires_at": "2026-01-15T00:00:00Z",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### 11.2 获取 API Key 列表

**GET** `/api/v1/api-keys`

**所需角色**：admin（全部）/ user（自己的）

**响应**（不返回明文，只返回前缀）：
```json
{
  "items": [
    {
      "id": "c2e6a8b4-5d7f-4e8a-b1c2-3d4e5f6a7b8c",
      "name": "报表导出脚本",
      "key_prefix": "aih_3f25",
      "scopes": ["read"],
      "is_active": true,
      "last_used_at": "2025-01-20T08:00:00Z",
      "usage_count": 42,
      "created_at": "2025-01-15T10:30:00Z",
      "expires_at": "2026-01-15T00:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 1,
    "pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

### 11.3 吊销 API Key

**DELETE** `/api/v1/api-keys/{key_id}`

**所需角色**：admin / user（自己的）

**响应**：
```json
{
  "id": "c2e6a8b4-5d7f-4e8a-b1c2-3d4e5f6a7b8c",
  "is_active": false,
  "message": "API key revoked"
}
```

**状态码**：
- `200`: 已吊销（软删除，`is_active=false`）
- `404`: Key 不存在（`API_KEY_NOT_FOUND`）

**作用域语义**：

| scope | 允许的操作 |
|---|---|
| `read` | 所有 `GET` 接口 |
| `write` | `read` + 数据源/清洗/分析/FAQ/报告/任务的写接口 |
| `admin` | 全部，含用户与 API Key 管理 |

---

## 12. 错误码

### 12.1 HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 202 | 已受理（异步任务入队） |
| 204 | 成功（无内容） |
| 400 | 请求参数错误 |
| 401 | 未认证 / Token 无效或过期 |
| 403 | 无权限（角色不足或越权访问他人资源） |
| 404 | 资源不存在 |
| 409 | 冲突（重复创建 / 任务已在运行 / 状态不允许） |
| 413 | 上传文件过大 |
| 415 | 上传文件格式不支持 |
| 422 | 请求体校验失败 |
| 429 | 请求过于频繁 / 配额或成本额度超限 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

---

### 12.2 业务错误码

| 错误码 | HTTP | 说明 | 出现位置 |
|--------|------|------|----------|
| `AUTH_INVALID_CREDENTIALS` | 401 | 邮箱或密码错误 | `POST /api/v1/auth/login` |
| `AUTH_TOKEN_EXPIRED` | 401 | access token 过期或已登出（黑名单） | 所有需认证接口 |
| `AUTH_REFRESH_TOKEN_INVALID` | 401 | refresh token 无效/过期/已轮换 | `POST /api/v1/auth/refresh` |
| `AUTH_FORBIDDEN` | 403 | 角色不足或访问他人资源 | 写接口、跨用户访问 |
| `USER_NOT_FOUND` | 404 | 用户不存在 | `GET /api/v1/users/me` |
| `USER_EMAIL_EXISTS` | 409 | 邮箱已注册 | `POST /api/v1/auth/register` |
| `DATASOURCE_NOT_FOUND` | 404 | 数据源不存在 | `/api/v1/datasources`、`/api/v1/datasources/{id}` |
| `DATASOURCE_QUOTA_EXCEEDED` | 429 | 数据源数量超配额 | `POST /api/v1/datasources` |
| `CLEANED_DATA_NOT_FOUND` | 404 | 清洗数据不存在 | `GET /api/v1/datasources/{id}/cleaned-data/{data_id}` |
| `FILE_TOO_LARGE` | 413 | 文件超过 50 MB | `POST /api/v1/datasources/{id}/upload` |
| `FILE_FORMAT_INVALID` | 415 | 文件格式不支持 | `POST /api/v1/datasources/{id}/upload` |
| `TASK_NOT_FOUND` | 404 | 任务不存在 | `/api/v1/tasks/{task_id}` |
| `TASK_ALREADY_RUNNING` | 409 | 同类任务已在运行 | `.../clean`、`.../analyze/quality`、`.../analyze/insights` |
| `TASK_NOT_CANCELLABLE` | 409 | 任务已结束，无法取消 | `POST /api/v1/tasks/{id}/cancel` |
| `TASK_NOT_RETRYABLE` | 409 | 任务不是失败态，无法重试 | `POST /api/v1/tasks/{id}/retry` |
| `FAQ_NOT_FOUND` | 404 | FAQ 不存在 | `PATCH/DELETE .../knowledge/faq/{faq_id}` |
| `REPORT_NOT_FOUND` | 404 | 报告不存在 | `/api/v1/reports/{report_id}` |
| `REPORT_FORMAT_INVALID` | 422 | 报告类型或格式不在枚举内 | `POST /api/v1/datasources/{id}/reports` |
| `INSUFFICIENT_CREDITS` | 429 | 当日/当月成本额度用尽（`DAILY_COST_LIMIT` / `MONTHLY_COST_LIMIT`） | `.../analyze/quality`、`.../analyze/insights`、`.../extract-knowledge`、`.../reports` |
| `RATE_LIMIT_EXCEEDED` | 429 | 超出速率限制（60 请求/分钟） | 全局中间件 |
| `API_KEY_NOT_FOUND` | 404 | API Key 不存在 | `DELETE /api/v1/api-keys/{key_id}`（Phase 2） |
| `API_KEY_INVALID` | 401 | API Key 无效/已吊销/已过期 | Phase 2 |
| `API_KEY_SCOPE_DENIED` | 403 | API Key 作用域不足 | Phase 2 |
| `WEBHOOK_NOT_FOUND` | 404 | Webhook 配置不存在 | `/api/v1/webhooks`、`/api/v1/webhooks/{id}`（Phase 2） |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 | 全部 |

---

### 12.3 限流与配额响应头

所有返回 `429` 的响应会带以下头部，便于前端退避：

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1736945400
Retry-After: 30
```

> `INSUFFICIENT_CREDITS` 与 `DATASOURCE_QUOTA_EXCEEDED` 同样返回 `429`，但 `error.code` 不同；前端按 `code` 区分提示（成本额度 / 配额 / 频率）。

---

## 13. Webhook（Phase 2）

> **MVP 不投递**：接口与 `webhooks` 表（见 `03-数据库设计.md` 3.11）已定义，转发逻辑在 Phase 2 实现。当前版本任务完成以轮询 `GET /api/v1/tasks/{task_id}` 为准。

### 13.1 配置 Webhook

**POST** `/api/v1/webhooks`

**所需角色**：admin / user（Phase 2）

**请求体**：
```json
{
  "url": "https://your-server.com/webhook",
  "events": ["task.completed", "task.failed"],
  "secret": "your_secret"
}
```

**响应**：
```json
{
  "id": "d3f7b9c5-6e8a-4f9b-a2c3-4e5f6a7b8c9d",
  "url": "https://your-server.com/webhook",
  "events": ["task.completed", "task.failed"],
  "is_active": true,
  "created_at": "2025-01-15T10:30:00Z"
}
```

**状态码**：
- `201`: 创建成功
- `422`: `url` 不是合法 HTTPS 地址或 `events` 为空

### 13.2 获取 Webhook 列表

**GET** `/api/v1/webhooks`

**所需角色**：admin（全部）/ user（自己的）

**响应**：
```json
{
  "items": [
    {
      "id": "d3f7b9c5-6e8a-4f9b-a2c3-4e5f6a7b8c9d",
      "url": "https://your-server.com/webhook",
      "events": ["task.completed", "task.failed"],
      "is_active": true,
      "last_triggered_at": "2025-01-20T08:00:00Z",
      "failure_count": 0
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 1,
    "pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

### 13.3 删除 Webhook

**DELETE** `/api/v1/webhooks/{webhook_id}`

**所需角色**：admin / user（自己的）

**状态码**：
- `204`: 删除成功
- `404`: 配置不存在（`WEBHOOK_NOT_FOUND`）

### 13.4 Webhook 事件负载

**task.completed**：
```json
{
  "event": "task.completed",
  "task_id": "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
  "task_type": "clean",
  "datasource_id": "550e8400-e29b-41d4-a716-446655440000",
  "result": {
    "cleaned_records": 950,
    "quality_score_avg": 85.5
  },
  "timestamp": "2025-01-15T10:30:00Z"
}
```

**签名头**：`X-AIH-Signature: sha256=<HMAC-SHA256(raw_body, secret)>`，接收方需用同一 `secret` 校验。

---

## 📊 API 开发清单

- [ ] 实现所有端点（统一前缀 `/api/v1`）
- [ ] 添加输入验证（Pydantic v2）
- [ ] 实现认证中间件（access + refresh + Redis 黑名单）
- [ ] 实现角色与资源归属校验（RBAC）
- [ ] 添加速率限制（429 + `Retry-After`）
- [ ] 配置 CORS（`BACKEND_CORS_ORIGINS`）
- [ ] 生成 Swagger 文档
- [ ] 编写 API 测试
- [ ] 设置监控（`PROMETHEUS_ENABLED` / `METRICS_PATH`）

---

**API 接口文档完成！** 🚀

**自动生成文档访问**：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
