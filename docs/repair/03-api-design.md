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

---

## 6. Phase 2 增量：RAG 执行与 Trace

> 前缀 `/api/v1/rag`；错误码新增 `RAG_TRACE_NOT_FOUND`(404)。

| # | 方法 | 路径 | 说明 |
|---|---|---|---|
| 1 | POST | `/rag/queries` | 执行一次检索/问答并落 trace（201） |
| 2 | GET | `/rag/traces` | Trace 列表（task_id / dataset_item_id / status / adapter） |
| 3 | GET | `/rag/traces/{trace_id}` | Trace 详情 |
| 4 | GET | `/rag/health` | 适配器可用性（不返回密钥） |

### 6.1 执行查询

```json
POST /rag/queries
{
  "dataset_item_id": "可选：数据集条目（问题取该条目）",
  "query": "可选：临时问题（与 dataset_item_id 二选一）",
  "mode": "retrieve | query",
  "adapter": "mock | weknora（缺省取配置）",
  "top_k": 5,
  "config": {"vector_threshold": 0, "keyword_threshold": 0}
}
```

响应（201）：

```json
{
  "trace_id": "…",
  "execution_mode": "query",
  "adapter": "weknora",
  "context_source": "agent_chat",
  "context_available": true,
  "query": "怎么退款？",
  "answer": "…",
  "retrieved_contexts": [
    {"document_id": "k-1", "chunk_id": "c-1", "title": "退款说明",
     "content": "…", "score": null, "rank": 1, "metadata": {}}
  ],
  "retrieved_scores": [null],
  "model_config_snapshot": {"agent_id": "…"},
  "retrieval_config": {"agent_enabled": true},
  "prompt_snapshot": {},
  "latency_ms": 1234,
  "token_usage": null,
  "missing": ["token_usage", "score"],
  "execution_status": "success",
  "error_message": null
}
```

**失败也是 201**：trace 已落库（`execution_status=failed`，`error_message` 为外部错误原文），
便于排查；只有「入参非法 / 无权限 / 条目不存在」才是 4xx。

### 6.2 两种模式与上下文规则（Q2 决策）

| 模式 | 调用 | `context_source` | 可用于 |
|---|---|---|---|
| `retrieve` | `hybrid-search` | `hybrid_search` | 检索指标（Phase 3） |
| `query` | `sessions` + `agent-chat` | `agent_chat`（有上下文）/ `none`（无） | 回答类指标 |

- **禁止**把 `retrieve` 的上下文当作 `query` 的生成上下文；
- `query` 模式拿不到上下文 → `context_source="none"`、`context_available=false`、
  `missing` 含 `retrieved_contexts`；Phase 3 的 Faithfulness 必须 skip 并记录原因；
- 外部未提供 `score` / `token_usage` → `null` + `missing`，不补零。

### 6.3 WeKnora 契约（实现依据，字段为实测反推）

| 能力 | 请求 | 关键响应 |
|---|---|---|
| 建会话 | `POST /api/v1/sessions` `{title, description}`，Header `X-API-Key` | `data.id` |
| 问答 | `POST /api/v1/agent-chat/{sid}` `{query, agent_enabled, agent_id}` | JSON 或 SSE；`answer` 事件拼答案，`tool_result.data.results` 为上下文 |
| 检索 | `POST /api/v1/knowledge-bases/{kb}/hybrid-search` `{query_text, match_count, vector_threshold, keyword_threshold}`，Header `X-API-Key` + `X-Tenant-ID` | `{success, data:[{knowledge_id, knowledge_title, content, score?}]}` |

**待验证项**（无真实凭据，未联调）：

1. `hybrid-search` 是否返回 `score`（实现按「有则取、无则 null + missing」处理）；
2. `agent-chat` 的 SSE 是否稳定包含 `tool_result`（若不含，则 `context_source=none`）；
3. 分页/多 KB 参数是否支持（当前只支持单 `kb_id`）。

---

## 7. Phase 3 增量：批量评测（`/api/v1/rag/evaluations`，8 个端点）

| # | 方法 | 路径 | 说明 |
|---|---|---|---|
| 1 | POST | `/rag/evaluations` | 创建 Run（202），`{run_id, task_id, status}` |
| 2 | GET | `/rag/evaluations` | 列表（dataset / version / status / mode / adapter） |
| 3 | GET | `/rag/evaluations/summary` | 跨 Run 分组汇总 |
| 4 | GET | `/rag/evaluations/{run_id}` | 详情（含 `task_status`/`task_progress` 与 aggregate） |
| 5 | GET | `/rag/evaluations/{run_id}/results` | 结果列表（metric / status / item） |
| 6 | GET | `/rag/evaluations/{run_id}/failures` | 失败结果（等价 `results?status=failed`） |
| 7 | POST | `/rag/evaluations/{run_id}/retry` | 重试失败样本 → 新 Run（202） |
| 8 | POST | `/rag/evaluations/{run_id}/cancel` | 取消（任务同步 cancel） |

### 7.1 创建请求

```json
{
  "dataset_version_id": "uuid",
  "execution_mode": "retrieve",
  "adapter": "mock",
  "split": "test",
  "limit": 200,
  "top_k": 5,
  "precision_mode": "at_k",
  "metrics": ["hit_rate", "mrr", "context_recall"],
  "item_ids": null
}
```

- `retrieve`：不接受 `judge_metrics`；`context_precision_at_k` 与 `context_precision_ap_at_k` 互斥，
  由 `precision_mode` 决定补哪一个；默认 4 个检索指标。
- `query`：不接受 `metrics`；默认 3 个 Judge 指标（faithfulness / answer_correctness / answer_relevancy）。
- `limit` 上限 200（`RAG_EVAL_MAX_ITEMS`）。
- 版本未发布 → **409**；空数据集 / `item_ids` 不属于该版本 → **400**。

### 7.2 状态约定

- `run.status`：`pending/running/completed/partial_failed/failed/cancelled`；
- `task.status`：现有 5 态；**run=partial_failed 时 task=completed**（执行完毕≠全部成功），
  两者在详情里分别返回，前端不得只显示其中一个；
- 失败重试：父 Run 结果不变，新 Run 带 `parent_run_id` / `attempt+1` / `retry_scope=failed_only`；
  同一父 Run 已有子 Run → **409**。

### 7.3 错误码

`RAG_EVALUATION_NOT_FOUND`(404) / `RAG_EVALUATION_INVALID`(400) / `RAG_EVALUATION_CONFLICT`(409)，
错误码总数 39 → 42。
