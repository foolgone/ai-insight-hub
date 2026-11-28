# M2 最小只读工作台：API 契约审计

> 状态：只读审计，供前端设计使用；**不实施 M2、不改后端、不建页面**。
> 日期：2026-11-18
> 范围：Run 列表、Run 详情、Case 详情、Evidence 追踪四个 P0 视图；Pairwise 对比只做缺口说明。
> 结论依据：`backend/app/api/v1/rag_evaluations.py`、`backend/app/api/v1/rag.py`、`backend/app/api/v1/qa_datasets.py`、`backend/app/schemas/rag_evaluation.py`、`backend/app/schemas/rag.py`、`backend/app/schemas/qa_dataset.py`、`backend/app/repositories/rag_evaluation.py`、`frontend/src/api/`、`frontend/src/router.jsx`。

## 1. 结论

| 项 | 结果 |
|---|---|
| 后端 Run 列表/详情/结果/失败样本 | 齐备，可直接支撑 P0 |
| Evidence 追踪 | 齐备：result → `trace_id` → `/rag/traces/{trace_id}` |
| Case 详情 | **没有单接口**；需要客户端把 results 按 `dataset_item_id` 聚合，再取 dataset item |
| Pairwise 对比 | **没有逐案例 diff 接口**；`/summary` 只是跨 Run 分组均值，不能冒充对比 |
| 前端 | **0**：无 RAG 评测路由、无 API client、无页面、无 E2E |
| 默认排序 | **缺失**：不传 `sort` 时 SQL 无 `ORDER BY`，列表顺序不稳定 |
| 重试子 Run | 列表未按 `parent_run_id` 过滤，父子 Run 混在同一列表；`/summary` 也不过滤 parent，会把父子重复计入 |
| 结果列表负载 | 偏重：每行带 `details` + `judge_config` + 最多 20k `raw_output` |
| v1.2.0 聚合 | 未实现 `invalid` / `insufficient` 计数；当前只有 `evaluated/skipped/failed` |

**判断：M2 P0 可以在不改后端的前提下开工，但前端必须显式传排序、按 Case 聚合、控制 results 页大小。Case 聚合和 compare 接口建议作为 M2 的 P1 后端增强，不阻塞第一版。**

### 1.1 前端现状（证据）

| 检查 | 结果 |
|---|---|
| 路由 | `frontend/src/router.jsx` 只有 7 个受保护业务页面 + 登录 + 404：dashboard / data-sources / data-cleaning / knowledge-base / quality-assessment / quality-assessment/:id / reports |
| 页面 | `frontend/src/pages/` 只有 Dashboard、DataCleaning、DataSources、KnowledgeBase、Login、NotFound、QualityAssessment、Reports |
| API client | `frontend/src/api/` 无 `rag_evaluations.js`；只有 `lib/errorMessages.js` 三条错误码文案 |
| 相邻页面 | `QualityAssessment` 是 datasource 对话质量评估，不是 RAG Judge 评测 |
| E2E | `frontend/e2e/` 只有 auth / datasources / knowledge / navigation / not-found / reports |

## 2. 端点清单

前缀：`/api/v1`。角色：`admin/user/viewer` 可读；`admin/user` 可写。

| 方法 | 路径 | 角色 | 过滤/分页 | 用途 |
|---|---|---|---|---|
| GET | `/rag/evaluations` | 读 | `dataset_id`、`dataset_version_id`、`status`、`execution_mode`、`adapter`、`page/limit/sort` | Run 列表 |
| GET | `/rag/evaluations/summary` | 读 | `dataset_id`、`execution_mode`、`adapter` | 跨 Run 分组均值（不是 diff） |
| GET | `/rag/evaluations/{run_id}` | 读 | — | Run 详情 + aggregate |
| GET | `/rag/evaluations/{run_id}/results` | 读 | `metric_name`、`status`、`dataset_item_id`、`page/limit/sort` | 结果行（按 metric） |
| GET | `/rag/evaluations/{run_id}/failures` | 读 | `metric_name`、`page/limit/sort` | `status=failed` 的结果行 |
| POST | `/rag/evaluations` | 写 | — | 创建 Run（M2 只读不用） |
| POST | `/rag/evaluations/{run_id}/retry` | 写 | — | 重试（M2 只读不用） |
| POST | `/rag/evaluations/{run_id}/cancel` | 写 | — | 取消（M2 只读不用） |
| GET | `/rag/traces/{trace_id}` | 读 | — | Trace 详情（context/answer/config） |
| GET | `/qa-datasets/{dataset_id}/versions/{version_id}/items` | 读 | `split`、`category`、`keyword`、`page/limit/sort` | 数据集条目列表 |
| GET | `/qa-datasets/{dataset_id}/versions/{version_id}/items/{item_id}` | 读 | — | 单条 query/gold/evidence |

## 3. 四个 P0 视图的字段映射

### 3.1 Run 列表

`RagEvaluationRunListItem` 可用字段：

| 列 | 字段 | 备注 |
|---|---|---|
| Run | `id` | 短 ID 展示 |
| 状态 | `status`、`task_status` | Run 状态与 Celery Task 状态分开 |
| 数据集 | `dataset_name`、`dataset_version_id` | 版本只给 UUID；名称需另查 |
| 模式 | `execution_mode`、`adapter` | retrieve/query |
| 数量 | `total_items`、`completed_items`、`skipped_items`、`failed_items` | 可算完成率 |
| 时间 | `created_at`、`completed_at` | 耗时 = completed_at - created_at；未完成时为空 |
| 错误 | `error_message` | 入队/执行失败 |
| 重试 | `parent_run_id`、`attempt` | 子 Run 链 |

缺口：

- **无默认排序**；前端必须传 `sort=-created_at`。
- **父子 Run 混排**：`list_runs` 不按 `parent_run_id` 过滤，重试子 Run 与父 Run 一起返回；列表项有 `parent_run_id`/`attempt`，UI 可以标注或在前端过滤根 Run，但没有服务端 `roots_only`/`parent_run_id` 过滤参数。
- 列表项不含 `judge_config` / `config_snapshot`，所以“Prompt 版本”列要么省略，要么进详情看；不要为此加 N+1 请求。
- 不含 `dataset_checksum`；需要追溯时进详情。

### 3.2 Run 详情

`RagEvaluationRunRead` 可用：

- 身份/追溯：`dataset_id`、`dataset_version_id`、`dataset_checksum`、`parent_run_id`、`attempt`、`retry_scope`；
- 配置：`execution_mode`、`adapter`、`retrieval_config`、`judge_config`、`config_snapshot`、`item_selection`；
- 进度：`total_items`、`completed_items`、`skipped_items`、`failed_items`、`task_status`、`task_progress`；
- 聚合：`aggregate`。

`aggregate` 结构（`build_aggregate`）：

```json
{
  "items": {"total": 40, "completed": 32, "failed": 0, "skipped": 8, "unprocessed": 0},
  "metrics": {
    "faithfulness": {
      "metric_version": "v2",
      "mean": 0.9,
      "evaluated": 32,
      "skipped": 8,
      "failed": 0,
      "coverage": 0.8,
      "skip_reasons": {"context_unavailable": 2}
    }
  }
}
```

缺口：

- `aggregate` 没有 `invalid`、`insufficient_count`、`insufficient_ratio`；v1.2.0 需要补，M2 第一版只能按现有字段显示。
- `judge_config` 里才有 prompt 版本/SHA；详情页应展示 `judge_config.prompt_version`、`prompt_sha256`、`schema_version`、`metric_version`。
- `config_snapshot` 是 dict，字段不稳定；前端用 key-value 表 + JSON fallback，不要硬编码全部字段。

### 3.3 Case 详情

**没有 `GET /cases/{item_id}` 聚合接口。** 推荐客户端三步：

1. 从 Run 详情拿 `dataset_id`、`dataset_version_id`；
2. `GET /rag/evaluations/{run_id}/results?dataset_item_id={item_id}&limit=100` 拿该 Case 的所有 metric 行；
3. `GET /qa-datasets/{dataset_id}/versions/{version_id}/items/{item_id}` 拿 `query`、`gold_answer`、`gold_evidence`；
4. 若任一 result 有 `trace_id`，`GET /rag/traces/{trace_id}` 拿 `answer`、`retrieved_contexts`、配置。

可用字段：

- result：`metric_name`、`metric_version`、`status`、`score`、`skipped_reason`、`details`、`judge_config`、`raw_output`、`raw_truncated`、`latency_ms`、`error_message`；
- item：`item_key`、`query`、`gold_answer`、`gold_evidence`、`category`、`difficulty`、`source`、`metadata`；
- trace：`query`、`answer`、`retrieved_contexts[]`（`document_id/chunk_id/title/content/score/rank/metadata`）、`model_config_snapshot`、`retrieval_config`、`prompt_snapshot`、`token_usage`、`missing`。

缺口/风险：

- **N+1**：Case 列表需要先按 `dataset_item_id` 分组；若逐题取 item，40 题就是 40 次请求。建议一次拉取版本条目（`limit=100`，最多 2 页）建 map。
- **result 不含 query/gold**：历史 Run 必须回查 dataset version；dataset 版本是不可变发布版，条目可读；但没有 dataset 删除接口，所以短期可用。若未来允许删 dataset，需要 Run 级 item 快照，否则 Case 详情会 404。
- **trace_id 可能为空**：skipped/failed 结果没有 trace；Case 页必须能只靠 result + item 渲染。
- **raw_output 20k/行**：Case 详情只取该题 3–5 行，仍可能 60–100KB；不要把它放进列表页。

### 3.4 Evidence 追踪

数据源：

- `RagEvaluationResultRead.details`：Faithfulness 的 `claims[]`、`evidence_refs[]`、`validation_errors`（若存在）；
- `RagTraceRead.retrieved_contexts[]`：context 原文、`context_id` 对应关系在 `details.claims[].evidence_refs[].context_id`（C1..Cn 对应 contexts 顺序）；
- `raw_output`：模型原始输出，`raw_truncated=true` 时只保留前 20,000 字符。

前端应展示：

| 区块 | 来源 |
|---|---|
| Context 列表 | trace.retrieved_contexts，按 rank/顺序编号 C1..Cn |
| Claim 列表 | details.claims，显示 `claim_type`、`claim_subtype`、`support_status`、`is_contradictory` |
| Evidence | `evidence_refs` → `context_id` + `quote`；高亮 quote 在 context 中的位置 |
| 判定原因 | `reason`、`validation_errors`、`error_message` |
| 原始输出 | `raw_output` + `raw_truncated` 提示 |

缺口：

- `context_id` 到 `retrieved_contexts` 的映射是**当次 trace 的顺序约定**（C1 = 当次第 1 条），不是显式字段；前端必须读该 result 对应的 trace，不能用当前知识库或重新检索的 contexts 代替，否则 quote 会对错片段。
- 没有 trace 保留期；旧 Run 的 trace 可能被清理（当前无清理任务，但 M4 会定义）。
- Faithfulness `details` 的 claim 结构随 schema v1/v2/v3 变化；M2 必须按 `metric_version`/`schema_version` 分支渲染，不能假设 `support_status` 一定存在。

## 4. 权限契约

| 规则 | 实现 | 前端影响 |
|---|---|---|
| 读角色 | `admin/user/viewer` | viewer 可进只读页；隐藏创建/重试/取消 |
| 写角色 | `admin/user` | viewer 不显示写按钮 |
| Run 归属 | 非 admin 只能看自己的 Run（`assert_owner`） | 他人 Run → 403，不是 404 |
| Dataset 归属 | 同上 | 数据集条目也受 owner 约束 |
| 租户 | **无**；只有 user_id | 不能宣称“租户隔离”；M4 决策前只适合内部单组织 |
| 错误泄露 | 他人资源返回 403 而非 404 | UI 统一“无权访问”，不要显示资源是否存在 |

## 5. 分页、排序、错误

- 分页：`page` 从 1，`limit` 默认 20、最大 100；响应 `{items, pagination:{page,limit,total,pages,has_next,has_prev}}`。
- 排序白名单：
  - Run：`created_at`、`completed_at`；**不传则无 ORDER BY**。
  - Result：`created_at`、`metric_name`。
- **前端必须显式传**：
  - Run 列表：`sort=-created_at`；
  - Result 列表：`sort=metric_name` 或 `sort=created_at`（保证稳定分页）。
- 错误体：`{"error":{"code","message","details"}}`。
  - `RAG_EVALUATION_NOT_FOUND` → 404
  - `RAG_EVALUATION_INVALID` → 400
  - `RAG_EVALUATION_CONFLICT` → 409
  - `PERMISSION_DENIED` → 403
  - 422 为请求校验错误
- 前端已有 `normalizeError`，直接复用；不要为新页面另造错误解析。

### 5.1 Coverage 术语（M1-B-003 契约）

| 术语 | 含义 | UI 标签 |
|---|---|---|
| `faithfulness` 的分数 | `S/(S+U+I)`，证据覆盖 | **Faithfulness（证据覆盖）** |
| `aggregate.metrics[].coverage` | `evaluated_rows / total_items`，评测覆盖率 | **评测覆盖率** |
| `insufficient_ratio` | `I/(S+U+I)`，无法判定的 Claim 比例 | **证据不足比例** |

三者不能共用“Coverage”一个标签；M2 页面必须按上表显示。

## 6. 负载与性能

| 风险 | 事实 | 建议 |
|---|---|---|
| results 列表过重 | 每行含 `details`、`judge_config`、`raw_output`（≤20k） | 列表 `limit=20`；Case 详情按 `dataset_item_id` 取；不要一次拉 100 行 |
| summary 无分页 | 最多 1000 个 Run，服务端聚合；**不过滤 `parent_run_id`，父子 Run 会重复计入** | 第一版只用根 Run 或按 `parent_run_id` 去重；否则均值会被重试污染 |
| Run 列表 N+1 | `task_status` 已批量查，无 N+1 | 可直接用 |
| Case 列表 N+1 | result 不含 item query/gold | 一次拉版本条目建 map，不要逐题请求 |
| 大字段截断 | `raw_output` 20k 截断，`raw_truncated` 标记 | UI 必须显示“已截断”，不能当完整原文 |

## 7. 缺口与建议（不在本轮实施）

### P0（前端可在不改后端的情况下解决）

1. 显式排序：Run 列表 `-created_at`，Result 列表 `metric_name`。
2. Case 聚合：客户端按 `dataset_item_id` 分组；一次拉版本条目建 map。
3. 按 `schema_version`/`metric_version` 分支渲染 claim 字段。
4. viewer 只读；403/404/空态/截断态都要有。

### P1（M2 第一版之后）

1. **Case 聚合接口**：`GET /rag/evaluations/{run_id}/cases` 或 `results?group_by=item`，返回每题 query/gold/metrics/trace 摘要，减少 N+1 和大字段传输。
2. **轻量 results 投影**：`include=summary|details|raw`，列表默认不返回 `raw_output`。
3. **Pairwise compare**：`GET /rag/evaluations/compare?base=...&target=...`，按 `dataset_item_id` 对齐，输出逐题 diff；现有 `/summary` 不能替代。
4. **默认排序**：仓储层在无 `sort` 时给 `created_at desc`，避免前端遗漏。
5. **重试子 Run 过滤**：列表增加 `parent_run_id` / `roots_only` 过滤，或在 UI 按 `parent_run_id` 分组；当前父子混排，容易把重试结果当独立评测。
6. **summary 去重**：`list_runs_for_summary` 增加 `parent_run_id IS NULL` 或按最新 attempt 去重，避免父子重复计入。

### P2（v1.2.0/M4 依赖）

1. `aggregate.metrics` 增加 `invalid`、`insufficient_count`、`insufficient_ratio`；否则 M2 无法展示 M1-B-002 的新口径。
2. Run 列表增加 `prompt_version`、`schema_version`、`metric_version`（或 `judge_config` 摘要），避免详情页才能看版本。
3. Trace/Result 保留期与删除策略（M4-A）。
4. Dataset 删除/导出对历史 Run 的影响（M4-A）。

## 8. 建议的前端 API client（只读）

只列契约，不写实现：

```text
listRagEvalRuns({ page, limit, sort: '-created_at', dataset_id?, status?, execution_mode?, adapter? })
getRagEvalRun(runId)
listRagEvalResults(runId, { page, limit, sort: 'metric_name', metric_name?, status?, dataset_item_id? })
listRagEvalFailures(runId, { page, limit, sort: 'metric_name', metric_name? })
getRagTrace(traceId)
listQaDatasetItems(datasetId, versionId, { page, limit, split?, category?, keyword? })
getQaDatasetItem(datasetId, versionId, itemId)
```

约束：

- 响应是 snake_case（后端 `response_model_by_alias=False`）；不要在 client 里做 camelCase 假设。
- 请求体可 snake_case；新建/重试/取消不在 M2 第一版。
- 所有列表必须带 `sort`，否则分页可能重复/漏项。

## 9. M2 第一版边界与验收

**做**：Run 列表、Run 详情、Case 详情、Evidence 追踪；只读；分页；空态/错误态/截断态；viewer 只读。

**不做**：创建/重试/取消、Gold/Prompt/知识库编辑、Pairwise 对比、趋势图、报告导出、租户管理。

**验收（后续执行，不在本轮）**：

- Run 列表 → 详情 → Case → Evidence 全链路可走；
- 403/404/空结果/`raw_truncated` 都有明确 UI；
- viewer 看不到写操作；
- E2E 覆盖核心浏览路径；
- 不出现“页面显示 F 均值但不知道 prompt/schema/metric 版本”的情况。

## 10. 待人工确认

1. M2 第一版是否接受“Case 客户端聚合 + 一次拉版本条目”的 N+1 替代方案，还是先加 `cases` 接口？
2. `raw_output` 是否对 viewer 展示？若数据可能含敏感原文，M4 安全约束前应默认折叠/隐藏。
3. 内部用户是否只限单组织？若是，M2 可以按 user_id 隔离上线；若不是，租户隔离必须先做。
4. Run 列表是否需要 Prompt 版本列？需要则建议 P2 加字段，避免前端 N+1。
