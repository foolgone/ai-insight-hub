# 修复进度（按 Phase 记录）

> 每阶段完成后追加：改动文件、迁移、测试结果、遗留问题。
> 上一阶段：`docs/repair/01-implementation-plan.md`

---

## Phase 1 · 数据基础（数据集 / 版本 / 条目）— 已完成

**日期**：2026-11-13
**范围**：只新增 RAG 评测数据集链路；未改动对话清洗/质量评估/知识库任何代码路径。

### 1. 改动文件

| 类型 | 文件 | 说明 |
|---|---|---|
| 新增 | `backend/app/models/qa_dataset.py` | 3 个 ORM：`QaDataset` / `QaDatasetVersion` / `QaDatasetItem` |
| 新增 | `backend/app/repositories/qa_dataset.py` | 纯 SQL：数据集/版本/条目读写、计数、过滤 |
| 新增 | `backend/app/schemas/qa_dataset.py` | 请求/响应 Schema + 导入错误结构 |
| 新增 | `backend/app/services/qa_dataset_service.py` | 归属、状态机、导入校验、checksum、统计 |
| 新增 | `backend/app/api/v1/qa_datasets.py` | 13 个端点 |
| 新增 | `backend/migrations/versions/20261113_2200_b2f7c1d9e4a3_019_qa_datasets.py` | 迁移 019 |
| 新增 | `backend/tests/unit/test_qa_dataset_rules.py` | 12 条（checksum + 导入校验） |
| 新增 | `backend/tests/integration/test_qa_dataset_api.py` | 11 条（CRUD/发布/不可变/权限/回滚/样例导入） |
| 新增 | `backend/tests/fixtures/qa_dataset_sample.json` | 20 条脱敏样例（10 文档 + 10 对话） |
| 修改 | `backend/app/models/__init__.py` | 登记 3 个新模型（Alembic 依赖） |
| 修改 | `backend/app/api/v1/__init__.py` | 挂载 `/qa-datasets` |
| 修改 | `backend/app/core/errors.py` | 新增 4 个错误码 + 状态映射 |
| 修改 | `backend/app/core/exceptions.py` | 新增 4 个异常 |
| 修改 | `backend/tests/unit/test_errors.py` | 错误码契约 34 → 38 |
| 修改 | `backend/tests/unit/test_models_schema.py` | 表契约 18 → 21 + 新表列断言 |
| 修改 | `backend/tests/integration/test_openapi.py` | 契约加入 8 条新路径 |
| 修改 | `frontend/src/lib/errorMessages.js` | 4 个错误码中文文案 |
| 新增 | `docs/repair/02-database-design.md` | 表结构 / checksum 规则 / 迁移回滚 |
| 新增 | `docs/repair/03-api-design.md` | 13 个端点 / 请求响应 / 行为约定 |

### 2. 数据库迁移

```
019_qa_datasets  revision=b2f7c1d9e4a3  down_revision=9a4d2f8c6e15
新增：qa_datasets / qa_dataset_versions / qa_dataset_items
索引：3 个唯一索引 + 5 个普通索引
```

执行记录：

```
alembic current : 9a4d2f8c6e15 -> b2f7c1d9e4a3 (head)
alembic check   : No new upgrade operations detected
```

回滚：`alembic downgrade 9a4d2f8c6e15`（只删 3 张新表）。

### 3. 关键实现

| 要求 | 实现 | 证据 |
|---|---|---|
| 发布后不可变 | `_ensure_draft()`，PATCH/DELETE/import 前校验 → 409 | `test_publish_then_immutable` |
| 修改产生新版本 | `create_version(from_version_id=...)` 逐条复制（copy-on-write） | `test_new_version_copy_is_isolated` |
| 导入全量校验 + 回滚 | `validate_import_payload` 先收集错误，有错即 400 且不写库 | `test_import_rejects_bad_rows_with_index_and_rolls_back` |
| 错误行号 | `errors[].index` 为 1-based 行号；字段名转 snake_case | `test_validate_import_requires_evidence_text` |
| 证据不得只有 ID | `GoldEvidence.evidence_text` 必填且 ≥10 字 | 同上 + `test_import_sample_fixture` |
| checksum 范围稳定 | 9 字段、条目按 `item_key`、证据按四元组排序、紧凑 JSON | `test_checksum_is_stable_across_item_and_evidence_order` |
| 两类数据独立 | `source_type ∈ doc/conv/mixed`，独立数据集 | `test_create_list_and_detail` |
| 权限 | 读三角色 / 写 admin+user / 归属 admin 全通 | `test_permissions` |

### 4. 测试结果

| 项 | 结果 |
|---|---|
| 新增单测 | 12 passed |
| 新增集成 | 11 passed |
| 后端全量 | **760 passed**（Phase 0 基线 730，净增 30：新增测试 23 + 表列参数化 3 + 异常映射参数化 4；无删除） |
| mypy | `Success: no issues found in 148 source files` |
| black / flake8 | 通过（264 文件 unchanged / 0 error） |
| lint-imports | `5 kept, 0 broken` |
| 前端 | 77 文件全绿；行 95.58% / 分支 83.36% / 函数 81.26% |
| 迁移漂移 | `alembic check` 无差异；`downgrade 9a4d2f8c6e15 → upgrade head` 往返成功 |

### 5. 与 Phase 0 方案的差异

| 项 | 方案 | 实际 | 原因 |
|---|---|---|---|
| 错误码 | 3 个（NOT_FOUND / IMMUTABLE / IMPORT_INVALID） | **4 个**（多 `QA_DATASET_NAME_EXISTS`） | 重名是 409 冲突，不应复用 400 的「导入校验失败」 |
| 端点 | 11 个（数据集 11） | **13 个**（多 `GET /versions`、`GET /items/{id}`） | 验收要求「查询单条样本」；版本列表从详情拆出便于前端 |
| 删除数据集 | 未列 | 未实现 | Phase 1 验收不含删除；避免误删不可逆（Q6 决策） |
| `source_type` | `doc/conv/mixed` | 同 | — |

### 6. 已知限制

1. **无删除/归档数据集接口**：避免误删；`qa_dataset_versions.status=archived` 已预留；
2. **单条导入上限 2000**：459 条可一次导入；更大数据集需分批；
3. **并发导入同一 `item_key`**：依赖唯一索引，捕获 `IntegrityError` 返回 400（提示重试），非静默覆盖；
4. **`metadata` 列名与 ORM 属性**：DB 列名为 `metadata`，ORM 属性为 `item_metadata`（SQLAlchemy 保留字），API 输出仍为 `metadata`；
5. **前端页面未做**：数据集管理页在 Phase 6；本阶段只保证 API 与错误文案可用；
6. **未接入 459 条真实数据**：需要业务授权后通过导入接口写入（本阶段只提供 20 条脱敏样例）。

### 7. 下一阶段（Phase 2）准备

- 需要：WeKnora 的 `BASE_URL / API_KEY / AGENT_ID / KB_ID / TENANT_ID`（Q1 决策：先用 Mock，接口契约按外部脚本实现）；
- 迁移 020：`rag_traces` / `rag_eval_results` / `experiments` / `experiment_runs`；
- 验收：Mock 下跑通「建 trace → 查 trace」，真实联调视凭据。

---

## Phase 2 · RAGPort + WeKnora/Mock Adapter + Trace — 已完成（Mock 验证）

**日期**：2026-11-13
**范围**：新增 `RAGPort`、两个适配器、`rag_traces`（迁移 020）与 4 个 API。
未实现：指标、Judge、实验、归因（Phase 3/4/5）。

### 1. 改动文件

| 类型 | 文件 | 说明 |
|---|---|---|
| 新增 | `backend/app/ports/rag.py` | `RAGPort` / `RAGResult` / `RetrievedContext`（统一结构） |
| 新增 | `backend/app/services/rag/__init__.py` | 适配器工厂（`mock` / `weknora`，未知→400） |
| 新增 | `backend/app/services/rag/weknora.py` | httpx + SSE 解析 + 重试 + 原始响应留存 |
| 新增 | `backend/app/services/rag/mock.py` | 确定性 Mock（`model_config.mock=true`） |
| 新增 | `backend/app/services/rag/execute.py` | 执行一次查询 → trace；幂等键；失败也落库 |
| 新增 | `backend/app/models/rag.py` | `RagTrace` |
| 新增 | `backend/app/repositories/rag_trace.py` | trace 读写 + 幂等键查询 |
| 新增 | `backend/app/schemas/rag.py` | 请求/响应（`trace_id`/`execution_mode`/`context_available`） |
| 新增 | `backend/app/api/v1/rag.py` | 4 个端点 |
| 新增 | `backend/migrations/versions/20261113_2330_c9d2a4f7b1e6_020_rag_traces.py` | 迁移 020（只建 `rag_traces`） |
| 新增 | `backend/tests/unit/test_rag_adapters.py` | 15 条 |
| 新增 | `backend/tests/integration/test_rag_api.py` | 10 条 |
| 修改 | `backend/app/core/config.py` | `RAG_ADAPTER / RAG_TIMEOUT_SECONDS / RAG_MAX_RETRIES / WEKNORA_*` |
| 修改 | `backend/app/models/__init__.py` | 登记 `RagTrace`（22 张表） |
| 修改 | `backend/app/api/v1/__init__.py` | 挂载 `/rag` |
| 修改 | `backend/app/core/errors.py` / `exceptions.py` | `RAG_TRACE_NOT_FOUND`（404） |
| 修改 | `backend/tests/unit/test_errors.py` | 错误码契约 38 → 39 |
| 修改 | `backend/tests/unit/test_models_schema.py` | 表契约 21 → 22 + `rag_traces` 列断言 |
| 修改 | `backend/tests/integration/test_openapi.py` | +4 条路径 |
| 修改 | `frontend/src/lib/errorMessages.js` | `RAG_TRACE_NOT_FOUND` 文案 |

### 2. 接口契约（WeKnora，实测反推）

| 能力 | 请求 | 解析要点 |
|---|---|---|
| 建会话 | `POST /api/v1/sessions` `{title, description}` + `X-API-Key` | `data.id` |
| 问答 | `POST /api/v1/agent-chat/{sid}` `{query, agent_enabled, agent_id}` | JSON：`data.answer` / `data.results`；SSE：`answer` 事件拼答案、`tool_result.data.results` 取上下文 |
| 检索 | `POST /api/v1/knowledge-bases/{kb}/hybrid-search` `{query_text, match_count, vector_threshold, keyword_threshold}` + `X-API-Key`/`X-Tenant-ID` | `{success, data[]}`，字段 `knowledge_id / knowledge_title / content` |

**待验证（无凭据，未联调）**

1. `hybrid-search` 是否返回 `score`（当前有则取、无则 `null` + `missing`）；
2. `agent-chat` 是否稳定返回上下文（不返回则 `context_source=none`）；
3. 多 KB / 分页参数是否支持。

### 3. 关键语义

| 规则 | 实现 | 测试 |
|---|---|---|
| 检索上下文不得冒充生成上下文 | `context_source` 三态 + `missing` | `test_query_without_contexts_marks_none` |
| 缺 answer / 空检索 | `answer=null` / `contexts=[]`，均记 `missing` | `test_query_missing_answer` / `test_retrieve_empty_result_is_success` |
| 不伪造 score/token/latency | 缺失记入 `missing`；latency 为实测 | `test_retrieve_maps_contexts_and_marks_missing_score` |
| 失败也留痕 | `status=failed` + 错误原文；API 仍 201 | `test_failed_adapter_is_persisted` |
| SSE 中途断开 | 保留已收内容，不抛异常 | `test_sse_truncated_midstream_keeps_received_content` |
| SSE 错误事件 | 抛 `WeKnoraError` → failed trace | `test_sse_error_event_raises` |
| 重试边界 | 仅 429/502/503/504 重试，达到上限抛错 | `test_retry_on_429_then_success` / `test_retry_exhausted_raises` |
| 幂等 | `idempotency_key` 唯一，重复调用复用 trace | `test_idempotent_execution_reuses_trace` |

### 4. 测试结果

| 项 | 结果 |
|---|---|
| 新增单测 | 15 passed（MockTransport，无网络） |
| 新增集成 | 10 passed（mock 适配器） |
| 后端全量 | **787 passed**（Phase 1 基线 760，净增 27：新增 25 + 契约参数化 2；无删除） |
| 前端 | 77 文件全绿；95.58% / 83.35% / 81.26% |
| lint-imports | 5 kept, 0 broken |
| 迁移 | `c9d2a4f7b1e6 (head)`；`alembic check` 无漂移 |

### 5. 与 Phase 0/本轮指令的差异

| 项 | 方案 | 实际 | 原因 |
|---|---|---|---|
| `rag_eval_results` | 020 一起建 | **未建**（推迟 Phase 3） | 本轮指令「无使用场景可暂缓」+ 禁止空表 |
| `experiments` / `experiment_runs` | 020 | 未建 | Phase 4 |
| `rag_traces` 字段 | 基础字段 | +`context_source`、`missing`、`idempotency_key` | 区分「缺失/空」，并为 Phase 3 幂等做准备 |
| API | 3 个（queries/traces/detail） | **4 个**（+`/rag/health`） | 外部服务可用性探测，避免把「未配置」误判为算法问题 |
| 错误码 | 未列 | +`RAG_TRACE_NOT_FOUND` | 语义清晰，避免复用 QA 数据集错误码 |

### 6. 真实联调状态

- **已完成**：Mock 全链路（执行 → 标准化 → trace → API 查询）；
- **未完成**：WeKnora 真实调用（缺 `WEKNORA_*` 凭据；不伪造成功）；
- 真机联调只需配置环境变量后执行：
  `POST /api/v1/rag/queries {"mode":"retrieve","adapter":"weknora","query":"…"}`。

### 7. 遗留问题

1. **Trace 无保留策略**（长期膨胀；Phase 6 加清理或分区）；
2. **单条 trace 同步执行**（`POST /queries` 等待外部返回；批量评测在 Phase 3 走 Celery）；
3. **WeKnora session 每查询新建**（隔离优先，成本是每题多一次调用）；
4. **`raw_response` 上限 200k 字符**（超出截断并标记，未落对象存储）；
5. **score 可能恒为 null**：Phase 3 的 MRR 仍可用排名，Context Precision 只能用 ID 命中率。

---

## Phase 3A · 确定性检索指标 — 已完成（待审核）

**日期**：2026-11-14
**范围**：仅纯函数与单测；不改数据库、不接入 LLM、不做批量任务（3B/3C 待审）。

### 1. 改动文件

| 类型 | 文件 | 说明 |
|---|---|---|
| 新增 | `backend/app/application/metrics.py` | 5 个纯函数 + 匹配/去重/规范化工具 |
| 新增 | `backend/tests/unit/test_rag_metrics.py` | 37 条表驱动单测 |
| 新增 | `docs/repair/04-evaluation-design.md` | 指标定义/匹配规则/Judge/表结构/任务设计/测试计划 |

### 2. 指标与公式（已实现）

| metric_name | 公式 | 跳过条件 |
|---|---|---|
| `hit_rate` | Top-K 内存在匹配 → 1，否则 0 | Gold 为空 |
| `mrr` | `1 / 首个匹配排名`，未命中 0 | Gold 为空 |
| `context_recall` | `命中 Gold 数 / Gold 总数` | Gold 为空 |
| `context_precision_at_k` | `Top-K 相关数 / 实际返回数` | Gold 为空 / 检索为空 |
| `context_precision_ap_at_k` | `(1/min(|G|,K))·Σ P@i·rel_i` | 同上 |

- `value=None` 表示 skipped（**不是 0**）；
- K 在 `details.k`，聚合时按 `metric_name + k` 分组；
- 两个 Precision 使用不同 metric_name，禁止只写 `context_precision`。

### 3. 匹配策略

| Gold 粒度 | 匹配方式 |
|---|---|
| 有 `chunk_id` | 仅 `chunk_id` 相等（同文档其它 chunk 不算） |
| 无 chunk、有 `document_id` | `document_id` 相等 |
| 只有文本 | `NFKC + casefold + 去空白/标点` 后**完全相等** |

- 不使用 embedding 相似度判定命中；
- 检索结果按 `chunk_id → document_id → 规范化文本` 去重，保留首次排名；
- Gold 按粒度+值去重；
- 匹配依据（`chunk_id`/`document_id`/`text`）写入 `details`。

### 4. 测试结果

| 项 | 结果 |
|---|---|
| 新增单测 | **37 passed** |
| 覆盖 | 完全/部分/未命中、Top-K 边界、空检索、空 Gold、文档级、chunk 级、重复检索、重复 Gold、文本规范化、混合粒度、K 非法、两种 Precision 口径、failed 结构 |
| mypy | 0 issue（158 文件） |
| black / flake8 | 通过 |
| lint-imports | 5 kept, 0 broken |
| 全量回归 | 见本次结果（基线 787，不得减少） |

### 5. 与设计文档的差异

无。实现与 `04-evaluation-design.md` 第 2 节一致；`failed_result()` 为 3C 预留（运行期异常用），本阶段未被指标函数调用。

### 6. 遗留问题（3B/3C）

1. 文本级匹配要求完全相等，实际命中率会低于文档/Chunk 级——按设计「宁缺毋滥」；
2. 没有 `gold_evidence` 的样本（237 条 conv）在检索指标上会被 skip，聚合需单独展示 `skipped` 比例；
3. 3C 需要实现「同一 trace 多 Judge 版本」的结果唯一键与聚合。

### 7. 环境问题（已处理）

本机与 VM 数据库存在时钟偏差（宿主 `2026-11-14 05:06 UTC`，DB `2026-11-13 15:24 UTC`），
导致 `test_cost_monitor_alerts_when_limit_exceeded` 与 `test_cost_tracker_db` 失败：
它们用「宿主日界」过滤由 DB 写入的时间戳。

处理：`run_cost_monitor(..., *, now=None)` 增加显式注入口，两个测试改用 `select(func.now())`
（DB 时间）；不传 `now` 时生产行为不变（仍用系统 UTC 时间）。

### 8. 过程事故与修正（重要）

新增测试文件最初命名为 `tests/unit/test_metrics.py`，**与既有的 Prometheus 指标测试重名**，
覆盖后导致 4 个原有用例（`test_record_llm_call_updates_all_metrics` 等）消失。

- 已重命名为 `tests/unit/test_rag_metrics.py`；
- 原 `test_metrics.py` 已从 HEAD 还原；
- 全量计数从 820 恢复到 **824**（基线 787 + 新增 37），证明无测试丢失。

教训：新增测试文件前先检查同名；`git diff` 中出现的 `-def test_` 必须逐条确认为「重命名」而非「删除」。

---

## Phase 3A 审核核查（2026-11-14）

### 1. Precision@K 语义

| 项 | 结论 |
|---|---|
| 实现与设计一致性 | ✅ 一致：`value = 相关数 / len(去重后实际返回)`，实现 `metrics.py: context_precision_at_k` |
| 返回数 < K | 分母取**实际返回数**（例：返回 2 条、K=5、1 条相关 → 0.5，而非 0.2） |
| 测试覆盖 | 原有 k 截断/重复用例之外，新增 `test_context_precision_denominator_is_actual_returned_count` 锁定语义 |
| 是否改公式 | **否**；已在设计文档明确它是「返回结果中的相关比例」，不同返回条数的查询间不宜直接横向比较（需要时用 AP@K） |

### 2. 检索去重粒度

| 项 | 结论 |
|---|---|
| 有 `chunk_id` | 只按 `chunk_id` 去重 ✅（`RetrievedItem.identity`） |
| 无 chunk、有 `document_id` | 按 `document_id` 去重 ✅ |
| 两者都无 | 按规范化文本去重 ✅ |
| 同文档不同 chunk | **保留为两条** ✅（新增 `test_same_document_different_chunks_are_not_merged`） |
| 首次排名 | 保留 ✅（`test_duplicate_retrieved_keeps_first_rank`） |
| 去重与 K 的顺序 | 先去重再截断（重复项不占 K 名额）；新增 `test_dedupe_happens_before_k_truncation` 锁定 |
| 是否改代码 | **否**，实现已符合要求；补充 3 条测试与文档说明 |

### 3. 变更与测试

- 代码：**无改动**（仅测试与文档）；
- 新增测试 3 条（`test_rag_metrics.py` 40 条）；
- `04-evaluation-design.md` 更新：Precision 语义、去重与截断顺序、Phase 3B 完整设计。

---

## Phase 3B 设计已提交（待审核，未编码）

设计见 `docs/repair/04-evaluation-design.md` 第 3 节，要点：

1. 一个 `RagJudgeAgent` 按 metric 切换 Prompt 与输出 Schema，复用 `BaseAgent`；
2. Faithfulness **仅**使用 Trace 的真实上下文（`context_source=agent_chat`），否则 skipped 且不调用模型；
3. score 由代码计算（claims 支持比例），不信任模型自报；
4. Prompt 版本 + SHA256 + metric_version + 模型参数全部随结果返回；
5. 3B 不建表、不调度，结果结构完整，3C 落库与聚合；
6. 测试全部 Mock LLM（含非法 JSON/超时/缺字段/无上下文等 20+ 场景规划）。

> 等待人工确认后再编码。

---

## Phase 3B · LLM Judge（Faithfulness / Correctness / Relevancy）— 已完成（待审核）

**日期**：2026-11-14
**范围**：Judge Agent + Prompt + Schema + 编排服务 + 测试；**不建表、不落库、不调度**（3C 负责）。

### 1. 改动文件

| 类型 | 文件 | 说明 |
|---|---|---|
| 新增 | `backend/app/schemas/agents/rag_judge.py` | 输入 + 三个输出 Schema + metric_version |
| 新增 | `backend/app/agents/rag_judge_agent.py` | 单 Agent 按 metric 切 Prompt/Schema |
| 新增 | `backend/app/services/rag_judge_service.py` | 跳过规则、指标编排、原始输出截断 |
| 新增 | `backend/app/prompts/rag_judge/` | `faithfulness.txt` / `answer_correctness.txt` / `answer_relevancy.txt` / `version.txt` |
| 新增 | `backend/tests/unit/test_rag_judge_agent.py` | 10 条 |
| 新增 | `backend/tests/unit/test_rag_judge_service.py` | 12 条 |
| 新增 | `backend/tests/integration/test_rag_judge_integration.py` | 2 条（真实 DB + Fake LLM） |
| 修改 | `backend/app/agents/base.py` | `AgentResult.raw_text`（默认 None）+ 记录最终解析文本 |
| 修改 | `backend/app/agents/structured_output.py` | `parse_with_repair(raw_sink=...)` 返回最终用于解析的原文 |
| 修改 | `backend/app/core/config.py` | `RAG_JUDGE_MAX_TOKENS=8192` |
| 修改 | `docs/repair/04-evaluation-design.md` | 3B 设计与实现落点 |

### 2. 关键实现

| 约束 | 实现 |
|---|---|
| Faithfulness 总分由代码算 | `supported / total`；模型只输出 claims |
| 无 claim | `skipped(no_claims)`，score=None（不是 1.0） |
| 无真实上下文 | `context_source != agent_chat` 或 contexts 为空 → `skipped(context_unavailable)`，**不创建也不调用 Judge** |
| 上下文不混用 | 只用 `trace.retrieved_contexts`（agent_chat）；`hybrid_search` 的 Trace 一律 skip |
| 分数范围 | Schema `ge=0, le=1` + `_validate_parsed` 有限性校验；非法 → 修复轮 → 仍非法则 failed |
| 原始输出 | `AgentResult.raw_text` = **最终实际用于解析**的文本（含修复轮）；服务层截断 20000 字符并标 `raw_truncated` |
| 版本追溯 | `judge_config` 含 agent/model/temperature/max_tokens/prompt_version/prompt_sha256/metric_version |
| 指标隔离 | 三个指标输入字段互不串用（有测试断言 payload） |
| 失败隔离 | 单指标失败只标记该指标 failed，不影响其它指标与 Trace |

### 3. Prompt 与版本

- 目录 `app/prompts/rag_judge/`，`version.txt = 2026-11-14.1`；
- `prompt_sha256` 运行时按实际 Prompt 文本计算；
- `metric_version`：三个指标当前均为 `v1`，与 Prompt 版本独立；
- 同一 Trace 可用不同版本重复评测：3B 每次调用返回独立 `judge_config`，**不覆盖**；
  3C 以 `(run_id, dataset_item_id, metric_name, metric_version)` 唯一键落库。

### 4. 测试结果（本阶段新增 24 条）

| 项 | 结果 |
|---|---|
| Agent 单测 | 10（解析、修复轮 raw_text、非法输出、输入校验、超时、Prompt 版本/SHA） |
| 服务单测 | 12（无上下文不调用、retrieval 上下文不冒充、无 claims、部分支持、缺 gold、空答案、失败隔离、截断、版本元信息、输入隔离） |
| 集成 | 2（真实 DB Trace + Fake LLM；Judge 不改 Trace；不同 Prompt 版本产生不同 config） |
| 全量回归 | **851 passed**（3A 827 + 24，无删除） |
| mypy / black / flake8 | 0 issue / 通过 / 通过 |
| lint-imports | 5 kept, 0 broken |

### 5. 与设计的差异

| 项 | 设计 | 实现 | 原因 |
|---|---|---|---|
| 原始输出 | `raw_text` | 同，且 `parse_with_repair` 返回「最终解析文本」 | 修复轮存在时不能存首次输出 |
| 截断 | 合理长度保护 | 20,000 字符 + `raw_truncated` | 避免大对象入库/日志 |
| 上下文条数 | 未定 | 最多 20 条、每条 6,000 字符 | 控制 Prompt 体积 |
| 指标版本 | 常量 | `v1`（三个指标） | 与 Prompt 版本解耦 |

### 6. 遗留问题

1. Judge 结果尚未落库（3C）；
2. 真实 WeKnora 未联调，所有测试为 Mock/Fake；
3. 上下文截断策略（20×6000）需在真实长文档场景复核；
4. `AgentResult.raw_text` 让所有 Agent 多存一份原文（内存态），未写入 `llm_calls`；
   如需全链路原文留存，3C/后续可考虑按需落对象存储。

---

## Phase 3C · 持久化与批量执行 — 设计完成（待审核，未编码）

**日期**：2026-11-14
**范围**：仅审计 + 设计（`docs/repair/04-evaluation-design.md` 第 4 节）。**未改业务代码、未建迁移、未操作数据库。**

### 1. 审计事实（代码核对）

| 项 | 事实 |
|---|---|
| 迁移 head | 生产 `9a4d2f8c6e15`（018，**无 rag 表**）；开发 `c9d2a4f7b1e6`（020） |
| `tasks.task_type` | CHECK 仅 6 种，**不含 `rag_eval`** → 021 需调整约束 |
| `tasks.status` | 仅 `pending/running/completed/failed/cancelled`，**无 partial_failed** → 由 run 承载 |
| Celery | `acks_late=False`（仅 clean 开启）；`prefetch=1`；visibility 3600s；`time_limit=1800s`；concurrency=2 |
| 连接池 | `pool_size=20 / max_overflow=40`，API 与 worker 共享 |
| Phase 1 | 发布后版本不可变（409）+ checksum |
| Phase 2 | `rag_traces.idempotency_key` 唯一；含 `dataset_item_id` / `task_id` |
| Phase 3B | `judge_trace` 返回 `JudgeOutcome`（含 judge_config/raw_output），不落库 |

### 2. 8 个核查问题结论

| # | 结论 |
|---|---|
| 1 | Faithfulness 的 evidence **未**与输入上下文校验；3C 落库时加 `evidence_verified` 统计，不改分数 |
| 2 | Judge 原始输出 20k 截断 + `raw_truncated`，足够复盘（超长除外） |
| 3 | Run 配置可重现（版本+checksum+judge_config+prompt_sha）；缺代码版本/随机种子，已知限制 |
| 4 | 重复投递/崩溃：任务级 `acks_late` + run 级 advisory lock + 唯一键 + 心跳/stale 回收 |
| 5 | 事务：每条样本 savepoint + 逐条 commit，单条失败不回滚整批 |
| 6 | 数据集发布后不可变；Run 固定版本 + checksum，执行前比对 |
| 7 | 每 Run 每样本独立 Trace；重试按 idempotency key 复用父 Run 成功 Trace |
| 8 | WeKnora 最小验收：1 条 retrieve + 1 条 query，核对 contexts/context_source/耗时与外部基线 |

### 3. 设计交付（第 4 节）

- **ER**：`tasks 1─1 runs 1─n results`；runs 自关联 `parent_run_id`；results FK items（RESTRICT）/ traces（SET NULL）。
- **唯一键**：`unique(run_id, dataset_item_id, metric_name, metric_version)`；前提是 Run 内 Judge 配置固定，换配置必须新建 Run。
- **状态机**：run `pending/running/completed/partial_failed/failed/cancelled`；task 仅用现有 5 态映射。
- **Celery**：`tasks.rag_evaluation`（acks_late + advisory lock + 逐条 savepoint + 心跳），复用现有 tasks/enqueue/executors。
- **重试**：新建 Run（`parent_run_id`、`failed_only`），复用成功 Trace；同一父 Run 已有子 Run → 409。
- **聚合**：mean/coverage/skip_reasons，skipped/failed 不计 0；按 doc/conv、mode、adapter、metric_version 分组。
- **API**：8 个（创建/列表/详情/结果/失败/重试/取消/汇总）。
- **迁移 021**：新增 2 表 + 调整 tasks CHECK；给出了锁、顺序、回滚方案。

### 4. 状态

设计待审核；审核通过后按 Phase 3C 实施（迁移 021 → 服务/任务 → API → 测试）。
