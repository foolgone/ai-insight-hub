# AI Insight Hub - API 接口文档

> **文档版本**：v1.0  
> **创建日期**：2026年10月23日  
> **API 版本**：v1  
> **Base URL**：`http://localhost:8000/api/v1`  
> **认证方式**：JWT Bearer Token

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
11. [错误码](#11-错误码)

---

## 1. API 概述

### 1.1 API 特性

- ✅ RESTful 风格
- ✅ JWT 认证
- ✅ 分页支持
- ✅ 过滤和排序
- ✅ 速率限制（60 请求/分钟）
- ✅ 自动生成文档（Swagger）

---

### 1.2 快速开始

```bash
# 1. 注册用户
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass123","name":"User"}'

# 2. 登录获取 Token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass123"}'

# 3. 使用 Token 访问 API
curl -X GET http://localhost:8000/api/v1/datasources \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 2. 认证

### 2.1 注册

**POST** `/auth/register`

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
- `409`: 邮箱已存在

---

### 2.2 登录

**POST** `/auth/login`

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
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

**状态码**：
- `200`: 登录成功
- `401`: 认证失败

---

### 2.3 刷新 Token

**POST** `/auth/refresh`

**请求头**：
```
Authorization: Bearer <refresh_token>
```

**响应**：
```json
{
  "access_token": "new_token",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### 2.4 登出

**POST** `/auth/logout`

**请求头**：
```
Authorization: Bearer <access_token>
```

**响应**：
```json
{
  "message": "Logged out successfully"
}
```

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

**响应**：
```json
{
  "items": [...],
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
      "datasource_id": "xxx"
    }
  }
}
```

---

## 4. 用户管理

### 4.1 获取当前用户信息

**GET** `/users/me`

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

**PATCH** `/users/me`

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

**POST** `/users/me/password`

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

---

## 5. 数据源管理

### 5.1 创建数据源

**POST** `/datasources`

**请求体**：
```json
{
  "name": "客服对话-2025年1月",
  "description": "2025年1月的客服对话数据",
  "type": "customer_service",
  "config": {
    "auto_clean": true,
    "auto_evaluate": true,
    "evaluation_dimensions": ["accuracy", "completeness", "hallucination"],
    "notification_email": "user@example.com"
  }
}
```

**响应**：
```json
{
  "id": "ds_550e8400-e29b-41d4-a716-446655440000",
  "name": "客服对话-2025年1月",
  "description": "2025年1月的客服对话数据",
  "type": "customer_service",
  "status": "active",
  "config": {...},
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
- `403`: 超出配额限制

---

### 5.2 获取数据源列表

**GET** `/datasources`

**查询参数**：
- `page`: 页码
- `limit`: 每页数量
- `status`: 过滤状态（active/archived/processing/error）
- `type`: 过滤类型
- `sort`: 排序（-created_at）

**响应**：
```json
{
  "items": [
    {
      "id": "ds_550e8400-e29b-41d4-a716-446655440000",
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
    "pages": 1
  }
}
```

---

### 5.3 获取单个数据源

**GET** `/datasources/{datasource_id}`

**响应**：
```json
{
  "id": "ds_550e8400-e29b-41d4-a716-446655440000",
  "name": "客服对话-2025年1月",
  "description": "...",
  "type": "customer_service",
  "status": "active",
  "config": {...},
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
- `404`: 数据源不存在

---

### 5.4 更新数据源

**PATCH** `/datasources/{datasource_id}`

**请求体**：
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
  "id": "ds_550e8400-e29b-41d4-a716-446655440000",
  "name": "新名称",
  "description": "新描述",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

---

### 5.5 删除数据源

**DELETE** `/datasources/{datasource_id}`

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
- `404`: 数据源不存在

---

## 6. 数据处理

### 6.1 上传文件

**POST** `/datasources/{datasource_id}/upload`

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
  "task_id": "task_550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "File uploaded, processing started",
  "file_info": {
    "filename": "data.csv",
    "size": 1024000,
    "mime_type": "text/csv"
  }
}
```

**支持格式**：
- CSV
- JSON
- Excel (xlsx)
- TXT

**文件大小限制**：50 MB

---

### 6.2 触发数据清洗

**POST** `/datasources/{datasource_id}/clean`

**请求体**：
```json
{
  "data_ids": ["id1", "id2"],  // 可选，不传则全部清洗
  "config": {
    "remove_duplicates": true,
    "normalize_text": true
  }
}
```

**响应**：
```json
{
  "task_id": "task_550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "estimated_duration": 120,  // 秒
  "message": "Cleaning task queued"
}
```

---

### 6.3 获取清洗结果

**GET** `/datasources/{datasource_id}/cleaned-data`

**查询参数**：
- `page`: 页码
- `limit`: 每页数量
- `quality_score_min`: 最低质量分
- `quality_score_max`: 最高质量分
- `has_issues`: 是否有问题（true/false）
- `date_from`: 开始日期
- `date_to`: 结束日期

**响应**：
```json
{
  "items": [
    {
      "id": "cd_550e8400-e29b-41d4-a716-446655440000",
      "dialogue_id": "dlg_xxx",
      "timestamp": "2025-01-15T10:30:00Z",
      "user_message": "iPhone 14 多少钱？",
      "ai_response": "iPhone 14 目前的价格是 5999 元起。",
      "quality_score": 95,
      "issues": [],
      "metadata": {...}
    }
  ],
  "pagination": {...}
}
```

---

### 6.4 获取单条清洗数据

**GET** `/cleaned-data/{data_id}`

**响应**：
```json
{
  "id": "cd_550e8400-e29b-41d4-a716-446655440000",
  "dialogue_id": "dlg_xxx",
  "datasource_id": "ds_xxx",
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

---

## 7. 分析与评估

### 7.1 触发质量评估

**POST** `/datasources/{datasource_id}/analyze/quality`

**请求体**：
```json
{
  "data_ids": [],  // 可选
  "dimensions": ["accuracy", "completeness", "hallucination", "tone", "compliance"],
  "threshold": 70,  // 低于此分数标记为问题
  "include_knowledge_base": true
}
```

**响应**：
```json
{
  "task_id": "task_550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "estimated_duration": 300,
  "message": "Quality evaluation task queued"
}
```

---

### 7.2 获取评估结果

**GET** `/datasources/{datasource_id}/analysis/quality`

**查询参数**：
- `page`: 页码
- `limit`: 每页数量
- `score_min`: 最低分
- `score_max`: 最高分
- `has_issues`: 是否有问题
- `dimension`: 按维度过滤

**响应**：
```json
{
  "items": [
    {
      "id": "ar_550e8400-e29b-41d4-a716-446655440000",
      "dialogue_id": "dlg_xxx",
      "overall_score": 85,
      "dimensions": {
        "accuracy": {
          "score": 90,
          "weight": 0.35,
          "issues": []
        },
        "completeness": {
          "score": 80,
          "weight": 0.25,
          "issues": ["incomplete"]
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
  "pagination": {...},
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

---

### 7.3 触发洞察分析

**POST** `/datasources/{datasource_id}/analyze/insights`

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
  "task_id": "task_550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

---

### 7.4 获取洞察结果

**GET** `/datasources/{datasource_id}/analysis/insights`

**响应**：
```json
{
  "datasource_id": "ds_xxx",
  "time_range": {...},
  
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

**POST** `/datasources/{datasource_id}/extract-knowledge`

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
  "task_id": "task_550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

---

### 8.2 获取 FAQ 列表

**GET** `/datasources/{datasource_id}/knowledge/faq`

**查询参数**：
- `category`: 分类（产品/售后/咨询）
- `min_frequency`: 最小出现次数
- `sort`: 排序（-frequency）

**响应**：
```json
{
  "items": [
    {
      "id": "kb_550e8400-e29b-41d4-a716-446655440000",
      "question": "iPhone 14 多少钱？",
      "answer": "iPhone 14 目前的价格是 5999 元起，有多种配置可选。",
      "category": "产品",
      "frequency": 120,
      "confidence": 0.95,
      "variations": [
        "iPhone 14 价格",
        "iPhone 14 售价多少"
      ],
      "tags": ["iPhone", "价格"],
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "pagination": {...}
}
```

---

### 8.3 搜索知识库

**GET** `/datasources/{datasource_id}/knowledge/search`

**查询参数**：
- `q`: 搜索关键词
- `limit`: 结果数量（默认 10）
- `threshold`: 相似度阈值（0-1）

**响应**：
```json
{
  "query": "退货",
  "results": [
    {
      "id": "kb_xxx",
      "question": "如何退货？",
      "answer": "7 天内可以无理由退货...",
      "similarity": 0.95,
      "category": "售后"
    }
  ]
}
```

---

### 8.4 获取知识盲区

**GET** `/datasources/{datasource_id}/knowledge/gaps`

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

**POST** `/datasources/{datasource_id}/knowledge/faq`

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
  "id": "kb_550e8400-e29b-41d4-a716-446655440000",
  "question": "支持货到付款吗？",
  "answer": "...",
  "status": "active",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

### 8.6 更新 FAQ

**PATCH** `/knowledge/faq/{faq_id}`

**请求体**：
```json
{
  "answer": "更新后的答案",
  "category": "新分类"
}
```

---

### 8.7 删除 FAQ

**DELETE** `/knowledge/faq/{faq_id}`

---

## 9. 报告

### 9.1 生成报告

**POST** `/datasources/{datasource_id}/reports`

**请求体**：
```json
{
  "title": "2025年1月质量分析报告",
  "report_type": "quality",  // quality/knowledge/insight/comprehensive
  "format": "pdf",  // pdf/excel/markdown
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

**响应**：
```json
{
  "id": "rpt_550e8400-e29b-41d4-a716-446655440000",
  "title": "2025年1月质量分析报告",
  "report_type": "quality",
  "format": "pdf",
  "status": "generating",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

### 9.2 获取报告列表

**GET** `/datasources/{datasource_id}/reports`

**查询参数**：
- `report_type`: 报告类型
- `status`: 状态（generating/completed/failed）
- `sort`: 排序

**响应**：
```json
{
  "items": [
    {
      "id": "rpt_550e8400-e29b-41d4-a716-446655440000",
      "title": "2025年1月质量分析报告",
      "report_type": "quality",
      "format": "pdf",
      "status": "completed",
      "file_url": "https://storage.example.com/reports/xxx.pdf",
      "file_size": 1024000,
      "created_at": "2025-01-15T10:30:00Z",
      "completed_at": "2025-01-15T10:35:00Z"
    }
  ],
  "pagination": {...}
}
```

---

### 9.3 获取单个报告

**GET** `/reports/{report_id}`

**响应**：
```json
{
  "id": "rpt_550e8400-e29b-41d4-a716-446655440000",
  "title": "2025年1月质量分析报告",
  "datasource_id": "ds_xxx",
  "report_type": "quality",
  "format": "pdf",
  "status": "completed",
  "file_url": "https://storage.example.com/reports/xxx.pdf",
  "file_size": 1024000,
  "generation_duration": 45.2,
  "view_count": 10,
  "download_count": 3,
  "created_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T10:35:00Z",
  "expires_at": "2025-02-15T10:30:00Z"
}
```

---

### 9.4 下载报告

**GET** `/reports/{report_id}/download`

**响应**：
- 重定向到预签名 URL
- 或直接返回文件流

---

### 9.5 删除报告

**DELETE** `/reports/{report_id}`

---

## 10. 任务管理

### 10.1 获取任务状态

**GET** `/tasks/{task_id}`

**响应**：
```json
{
  "id": "task_550e8400-e29b-41d4-a716-446655440000",
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

**GET** `/tasks`

**查询参数**：
- `datasource_id`: 数据源 ID
- `task_type`: 任务类型
- `status`: 状态

**响应**：
```json
{
  "items": [
    {
      "id": "task_xxx",
      "task_type": "clean",
      "status": "completed",
      "progress": 100,
      "duration": 120.5,
      "created_at": "2025-01-15T10:30:00Z",
      "completed_at": "2025-01-15T10:32:00Z"
    }
  ],
  "pagination": {...}
}
```

---

### 10.3 取消任务

**POST** `/tasks/{task_id}/cancel`

**响应**：
```json
{
  "id": "task_xxx",
  "status": "cancelled",
  "message": "Task cancelled successfully"
}
```

---

### 10.4 重试失败任务

**POST** `/tasks/{task_id}/retry`

**响应**：
```json
{
  "id": "task_xxx",
  "status": "pending",
  "retry_count": 1,
  "message": "Task queued for retry"
}
```

---

## 11. 错误码

### 11.1 HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 204 | 成功（无内容） |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 冲突（如重复创建） |
| 422 | 验证失败 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

---

### 11.2 业务错误码

| 错误码 | 说明 |
|--------|------|
| `AUTH_INVALID_CREDENTIALS` | 认证失败 |
| `AUTH_TOKEN_EXPIRED` | Token 过期 |
| `USER_NOT_FOUND` | 用户不存在 |
| `USER_EMAIL_EXISTS` | 邮箱已存在 |
| `DATASOURCE_NOT_FOUND` | 数据源不存在 |
| `DATASOURCE_QUOTA_EXCEEDED` | 超出数据源配额 |
| `FILE_TOO_LARGE` | 文件过大 |
| `FILE_FORMAT_INVALID` | 文件格式不支持 |
| `TASK_NOT_FOUND` | 任务不存在 |
| `TASK_ALREADY_RUNNING` | 任务已在运行 |
| `INSUFFICIENT_CREDITS` | 余额不足 |
| `RATE_LIMIT_EXCEEDED` | 超出速率限制 |

---

## 12. Webhook（可选）

### 12.1 配置 Webhook

**POST** `/webhooks`

**请求体**：
```json
{
  "url": "https://your-server.com/webhook",
  "events": ["task.completed", "task.failed"],
  "secret": "your_secret"
}
```

---

### 12.2 Webhook 事件

**task.completed**：
```json
{
  "event": "task.completed",
  "task_id": "task_xxx",
  "task_type": "clean",
  "datasource_id": "ds_xxx",
  "result": {...},
  "timestamp": "2025-01-15T10:30:00Z"
}
```

---

## 📊 API 开发清单

- [ ] 实现所有端点
- [ ] 添加输入验证
- [ ] 实现认证中间件
- [ ] 添加速率限制
- [ ] 配置 CORS
- [ ] 生成 Swagger 文档
- [ ] 编写 API 测试
- [ ] 设置监控

---

**API 接口文档完成！** 🚀

**自动生成文档访问**：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
