# API 命名规范补充说明

> **文档版本**：v1.1  
> **更新日期**：2026年10月23日  
> **变更类型**：补充规范

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

```python
from pydantic import BaseModel, ConfigDict

class DataSourceResponse(BaseModel):
    """API 响应统一使用 snake_case"""
    
    model_config = ConfigDict(
        # 接收时允许驼峰，但输出统一为下划线
        alias_generator=None,
        populate_by_name=True
    )
    
    datasource_id: str
    created_at: datetime
    user_message: str
```

### 前端：Axios 拦截器自动转换

```javascript
// src/lib/api.js
import axios from 'axios';
import { camelCase, snakeCase } from 'lodash';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
});

// 请求拦截器：camelCase → snake_case
api.interceptors.request.use((config) => {
  if (config.data) {
    config.data = transformKeys(config.data, snakeCase);
  }
  if (config.params) {
    config.params = transformKeys(config.params, snakeCase);
  }
  return config;
});

// 响应拦截器：snake_case → camelCase
api.interceptors.response.use((response) => {
  if (response.data) {
    response.data = transformKeys(response.data, camelCase);
  }
  return response;
});

// 递归转换对象的键
function transformKeys(obj, transformer) {
  if (Array.isArray(obj)) {
    return obj.map(item => transformKeys(item, transformer));
  }
  
  if (obj !== null && typeof obj === 'object') {
    return Object.keys(obj).reduce((result, key) => {
      const transformedKey = transformer(key);
      result[transformedKey] = transformKeys(obj[key], transformer);
      return result;
    }, {});
  }
  
  return obj;
}

export default api;
```

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

### **前端层（JavaScript）**
- 变量名：`camelCase`
- 组件名：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`

```javascript
const dataSource = {
  datasourceId: "xxx",
  createdAt: new Date()
};

const MAX_FILE_SIZE = 50 * 1024 * 1024;
```

---

## 🔍 检查清单

在开发时，确保：

- [ ] 所有 API 端点返回 `snake_case` 字段
- [ ] Pydantic Schema 使用 `snake_case`
- [ ] 数据库字段使用 `snake_case`
- [ ] 前端通过拦截器自动转换
- [ ] TypeScript 类型定义使用 `camelCase`
- [ ] 文档示例统一使用规范命名

---

## 📝 更新记录

| 日期 | 变更 |
|------|------|
| 2026-10-23 | 新增命名规范统一说明 |
| 2026-10-23 | 添加自动转换机制 |

---

**命名规范统一完成！** ✅
