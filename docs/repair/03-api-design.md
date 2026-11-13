# API 设计（Phase 1：数据集）

> 前缀：`/api/v1/qa-datasets`
> 鉴权：Bearer JWT；读 `admin/user/viewer`，写 `admin/user`；归属：admin 全通，其余仅本人。
> 响应：统一 `snake_case`（路由 `response_model_by_alias=False`）；分页 `{items, pagination}`。

---

## 1. 错误码（新增）

| code | HTTP | 含义 |
|---|---|---|
| `QA_DATASET_NOT_FOUND` | 404 | 数据集 / 版本 / 条目不存在 |
| `QA_DATASET_NAME_EXISTS` | 409 | 同一用户下重名 |
| `QA_DATASET_IMMUTABLE` | 409 | 已发布版本不可修改 |
| `QA_DATASET_IMPORT_INVALID` | 400 | 导入校验失败 / 空版本发布（`details.errors[]`） |

错误体沿用现有结构：

```json
{"error": {"code": "QA_DATASET_IMPORT_INVALID", "message": "导入数据校验失败",
           "details": {"errors": [{"index": 2, "field": "gold_evidence.0.evidence_text", "message": "..."}],
                       "error_count": 1, "imported": 0}}}
```

---

## 2. 端点清单（12 个）

| # | 方法 | 路径 | 说明 | 成功码 |
|---|---|---|---|---|
| 1 | POST | `/qa-datasets` | 创建数据集 | 201 |
| 2 | GET | `/qa-datasets` | 列表（`keyword`、分页） | 200 |
| 3 | GET | `/qa-datasets/{dataset_id}` | 详情（含版本列表） | 200 |
| 4 | PATCH | `/qa-datasets/{dataset_id}` | 改名/描述/类型 | 200 |
| 5 | POST | `/qa-datasets/{dataset_id}/versions` | 创建草稿版本（可 `from_version_id` 复制） | 201 |
| 6 | GET | `/qa-datasets/{dataset_id}/versions` | 版本列表（版本号倒序） | 200 |
| 7 | POST | `/qa-datasets/{dataset_id}/versions/{version_id}/import` | 导入条目 | 200 |
| 8 | POST | `/qa-datasets/{dataset_id}/versions/{version_id}/publish` | 发布版本 | 200 |
| 9 | GET | `/qa-datasets/{dataset_id}/versions/{version_id}/items` | 条目列表（`split/category/keyword`） | 200 |
| 10 | GET | `/qa-datasets/{dataset_id}/versions/{version_id}/items/{item_id}` | 条目详情 | 200 |
| 11 | PATCH | `/qa-datasets/{dataset_id}/versions/{version_id}/items/{item_id}` | 更新条目（仅 draft） | 200 |
| 12 | DELETE | `/qa-datasets/{dataset_id}/versions/{version_id}/items/{item_id}` | 删除条目（仅 draft） | 204 |
| 13 | GET | `/qa-datasets/{dataset_id}/stats?version_id=` | 统计（split/分类/证据覆盖率） | 200 |

---

## 3. 关键请求/响应

### 3.1 创建数据集

```json
POST /qa-datasets
{"name": "机器人后台设置-文档类", "description": "222 条文档 Gold", "source_type": "doc"}
```

`source_type ∈ doc|conv|mixed`。重名 → 409。

### 3.2 创建版本

```json
POST /qa-datasets/{id}/versions
{"note": "v2 补充 12 条售后问题", "from_version_id": "可选：从已发布版本复制"}
```

返回：

```json
{"id": "...", "dataset_id": "...", "version": 2, "status": "draft",
 "item_count": 222, "checksum": null, "note": "...", "published_at": null, "created_at": "..."}
```

### 3.3 导入

```json
POST /qa-datasets/{id}/versions/{vid}/import
{
  "items": [
    {
      "item_key": "CONV-10215",
      "query": "我有针对SKU配置的话术，为什么没有触发？",
      "gold_answer": "……",
      "gold_evidence": [
        {"document_id": "doc-1", "chunk_id": "chunk-1",
         "evidence_text": "订单状态识别为售后-已签收……", "page_number": null, "metadata": {}}
      ],
      "category": "关键词/话术配置",
      "difficulty": "medium",
      "source": "conv:knowledge",
      "split": "test",
      "metadata": {"session_id": "10215"}
    }
  ]
}
```

规则：
- `items` 1–2000 条/次；
- `item_key` 必填、批内唯一、版本内唯一；
- `query` 必填；
- `gold_evidence[]` 每项 **`evidence_text` 必填且 ≥10 字**（只给 `document_id` 会被拒）；
- `split ∈ train|valid|test`，默认 `test`；
- **全量校验**：任何一条不合格 → 400，整批不落库，`errors[].index` 为 1-based 行号。

成功：

```json
{"imported": 20, "version_item_count": 20}
```

### 3.4 发布

```json
POST /qa-datasets/{id}/versions/{vid}/publish
```

返回含 `status=published`、`item_count`、`checksum`（64 位）。
空版本 → 400；重复发布/已发布 → 409。

### 3.5 条目读取

```json
GET /qa-datasets/{id}/versions/{vid}/items?split=test&category=售后&keyword=退款&page=1&limit=20
```

响应条目：

```json
{
  "id": "...", "item_key": "Q001", "query": "如何申请退款？",
  "gold_answer": "在订单详情页提交退款申请。",
  "gold_evidence": [{"document_id": "doc-100", "chunk_id": "chunk-1",
                     "evidence_text": "订单详情页提供申请退款入口。",
                     "page_number": 2, "metadata": {"section": "售后"}}],
  "category": "售后", "difficulty": "easy", "source": "doc:robot-backend",
  "split": "test", "metadata": {"origin": "unit-test"}, "created_at": "..."
}
```

### 3.6 统计

```json
GET /qa-datasets/{id}/stats?version_id={vid}
{
  "dataset_id": "...", "version_id": "...", "item_count": 20,
  "split_counts": {"train": 2, "valid": 1, "test": 17},
  "category_counts": {"售后": 2, "物流": 1, "...": 0},
  "evidence": {"with_evidence": 10, "without_evidence": 10, "coverage_rate": 0.5}
}
```

---

## 4. 行为约定

| 场景 | 行为 |
|---|---|
| 发布后 PATCH/DELETE 条目 | 409 `QA_DATASET_IMMUTABLE` |
| 发布后 import | 409 `QA_DATASET_IMMUTABLE` |
| 从已发布版本复制新版本 | 允许；新版本为 draft，条目独立复制 |
| 非本人数据集 | 403 `AUTH_FORBIDDEN`（admin 例外） |
| 不存在的 dataset/version/item | 404 `QA_DATASET_NOT_FOUND` |
| viewer 写操作 | 403 `AUTH_FORBIDDEN` |
| 重名 | 409 `QA_DATASET_NAME_EXISTS` |
| 空版本发布 | 400 `QA_DATASET_IMPORT_INVALID` |

---

## 5. 与后续 Phase 的接口契约

- Phase 2/3 的评测创建接口只需接收 `dataset_version_id`，即可锁定这一批不可变条目；
- `rag_traces.dataset_item_id` 指向 `qa_dataset_items.id`，保证「指标 → 样本 → 版本」可追溯；
- Phase 4 的实验对比要求「同数据集版本」，直接比较 `qa_dataset_versions.id`。
