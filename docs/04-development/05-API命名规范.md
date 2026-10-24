# API 命名规范补充说明

> **文档版本**：v1.2  
> **更新日期**：2026年10月24日  
> **变更类型**：修正 Pydantic 驼峰配置、去掉 lodash 依赖、TypeScript 改为 JS + JSDoc

---

## 🎯 命名规范统一

### 问题描述

在原有文档中，API 字段命名存在不一致：
- 部分使用 `datasource_id`（snake_case）
- 部分使用 `datasourceId`（camelCase）

这会导致前后端联调困难和开发混淆。

---

## ✅ 统一规范

### **后端和 API 响应：统一使用 snake_case**

```python
# ✅ 正确
{
  "datasource_id": "xxx",
  "created_at": "2026-10-23T10:30:00Z",
  "user_message": "你好"
}

# ❌ 错误
{
  "datasourceId": "xxx",
  "createdAt": "2026-10-23T10:30:00Z",
  "userMessage": "你好"
}
```

### **前端 JavaScript：使用 camelCase**

```javascript
// ✅ 正确
const dataSource = {
  datasourceId: "xxx",
  createdAt: new Date(),
  userMessage: "你好"
}
```

---

## 🔄 自动转换

### 后端：Pydantic 配置

规范要求 **对外响应仍是 snake_case**，但 Pydantic v2 默认按 alias 序列化。因此正确做法是：

1. `alias_generator=to_camel` + `populate_by_name=True`：让模型既能按驼峰别名、也能按字段名接收（兼容第三方回调/前端手写请求体）；
2. 路由层显式 `response_model_by_alias=False`：让 FastAPI 输出时**忽略别名、回落到字段名**，从而保证响应是 snake_case。

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class DataSourceResponse(BaseModel):
    """API 响应统一使用 snake_case。

    - 入参：兼容 camelCase（alias）与 snake_case（字段名）
    - 出参：由路由的 response_model_by_alias=False 强制回落到 snake_case
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    datasource_id: str
    created_at: datetime
    user_message: str
```

```python
# backend/app/api/v1/datasources.py
from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/{datasource_id}",
    response_model=DataSourceResponse,
    # 关键：关闭按 alias 序列化，响应保持 snake_case
    response_model_by_alias=False,
)
async def get_datasource(datasource_id: str) -> DataSourceResponse:
    ...
```

> ⚠️ 不要写成 `alias_generator=None`：那样等于完全放弃驼峰兼容，入参传 `datasourceId` 会直接 422。也不要省略 `response_model_by_alias=False`，否则响应会变成 `datasourceId`，与本文档「响应统一 snake_case」冲突。

### 前端：Axios 拦截器自动转换

项目未引入 lodash（见 `frontend/package.json`），转换函数自研，放在 `frontend/src/lib/case.js`：

```javascript
// frontend/src/lib/case.js

/**
 * snake_case → camelCase
 * @param {string} key
 * @returns {string}
 */
export function toCamel(key) {
  return key.replace(/_([a-z0-9])/g, (_, ch) => ch.toUpperCase());
}

/**
 * camelCase / PascalCase → snake_case
 * @param {string} key
 * @returns {string}
 */
export function toSnake(key) {
  return key
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1_$2')
    .toLowerCase();
}
```

```javascript
// frontend/src/lib/api.js
import axios from 'axios';

import { toCamel, toSnake } from './case';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
});

// 请求拦截器：camelCase → snake_case
api.interceptors.request.use((config) => {
  if (config.data) {
    config.data = transformKeys(config.data, toSnake);
  }
  if (config.params) {
    config.params = transformKeys(config.params, toSnake);
  }
  return config;
});

// 响应拦截器：snake_case → camelCase
api.interceptors.response.use((response) => {
  if (response.data) {
    response.data = transformKeys(response.data, toCamel);
  }
  return response;
});

/**
 * 递归转换对象的键
 * @param {unknown} obj
 * @param {(key: string) => string} transformer
 * @returns {unknown}
 */
function transformKeys(obj, transformer) {
  if (Array.isArray(obj)) {
    return obj.map((item) => transformKeys(item, transformer));
  }

  // FormData / Blob / Date 等不要遍历
  if (obj instanceof FormData || obj instanceof Blob || obj instanceof Date) {
    return obj;
  }

  if (obj !== null && typeof obj === 'object') {
    return Object.keys(obj).reduce((result, key) => {
      result[transformer(key)] = transformKeys(obj[key], transformer);
      return result;
    }, {});
  }

  return obj;
}

export default api;
```

> ⚠️ 注意：拦截器会把 **所有** 响应键递归转驼峰，包括后端返回的业务数据体（如知识库 chunk 的 `metadata`）。如果某个字段的键必须原样保留（例如用户自定义标签、JSONB 业务键），需要在响应拦截器里按路径白名单跳过转换。

---

## 📋 规范说明

### **数据库层**
- 字段名：`snake_case`
- 表名：`snake_case`（复数形式）

```sql
CREATE TABLE data_sources (
    datasource_id UUID PRIMARY KEY,
    created_at TIMESTAMP,
    user_id UUID
);
```

### **后端层（Python）**
- 变量名：`snake_case`
- 类名：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`

```python
class DataSource:
    datasource_id: str
    created_at: datetime
    
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 常量
```

### **API 响应**
- 字段名：`snake_case`（统一）

```json
{
  "datasource_id": "xxx",
  "created_at": "2026-10-23T10:30:00Z"
}
```

### **前端层（JavaScript + JSDoc）**
- 变量名：`camelCase`
- 组件名：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`
- 项目为纯 JavaScript（非 TypeScript），对象结构用 JSDoc 注释约束

```javascript
const dataSource = {
  datasourceId: "xxx",
  createdAt: new Date()
};

const MAX_FILE_SIZE = 50 * 1024 * 1024;

/**
 * @typedef {Object} DataSource
 * @property {string} datasourceId
 * @property {Date} createdAt
 * @property {string} [userMessage]
 */
```

---

## 🔍 检查清单

在开发时，确保：

- [ ] 所有 API 端点返回 `snake_case` 字段
- [ ] Pydantic Schema 使用 `snake_case` 字段名 + `to_camel` 别名
- [ ] 路由声明 `response_model_by_alias=False`
- [ ] 数据库字段使用 `snake_case`
- [ ] 前端通过拦截器自动转换
- [ ] 前端对象结构用 JSDoc `@typedef` 标注（项目未使用 TypeScript）
- [ ] 文档示例统一使用规范命名

---

## 📝 更新记录

| 日期 | 变更 |
|------|------|
| 2026-10-23 | 新增命名规范统一说明 |
| 2026-10-23 | 添加自动转换机制 |
| 2026-10-24 | 修正 Pydantic 驼峰配置（`to_camel` + `response_model_by_alias=False`）；去掉未安装的 lodash 依赖，改为自研 `toCamel`/`toSnake`；TypeScript 改为 JavaScript + JSDoc |

---

**命名规范统一完成！** ✅
