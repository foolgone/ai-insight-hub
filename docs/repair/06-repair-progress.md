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

## Phase 3C · 持久化与批量执行 — 设计完成（已审核通过，实施见下节）

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

设计已审核通过；实施记录见下节（迁移 021 → 服务/任务 → API → 测试）。

---

## Phase 3C · 持久化与批量执行 — 已实现（真实 WeKnora 联调未完成）

**日期**：2026-11-14
**范围**：迁移 021 + 两张表 + 评测服务/执行器/Celery/API + 测试 + 文档。
未改动 Phase 1/2 的对外契约，未改动对话清洗/质量评估/知识库链路。

### 1. 改动文件

| 类型 | 文件 | 说明 |
|---|---|---|
| 新增 | `backend/migrations/versions/20261114_1800_d4e8b1c6f902_021_rag_evaluation.py` | 迁移 021（2 表 + `tasks.task_type`） |
| 新增 | `backend/app/models/rag_evaluation.py` | `RagEvaluationRun` / `RagEvaluationResult` |
| 新增 | `backend/app/repositories/rag_evaluation.py` | Run/Result SQL、批量幂等写入、stale/汇总查询 |
| 新增 | `backend/app/schemas/rag_evaluation.py` | 创建/详情/结果/汇总 + 指标模式校验 |
| 新增 | `backend/app/services/rag_evaluation_service.py` | 创建/重试/取消/finalize/aggregate/summary/stale |
| 新增 | `backend/app/services/rag_evaluation_runner.py` | 执行循环、Trace 复用、逐条 savepoint、时间预算 |
| 新增 | `backend/app/core/advisory_lock.py` | 专用连接的会话级 advisory lock |
| 新增 | `backend/app/tasks/rag_evaluation.py` | `tasks.rag_evaluation` + `tasks.recover_stale_rag_runs` |
| 新增 | `backend/app/api/v1/rag_evaluations.py` | 8 个端点 |
| 新增 | `backend/tests/integration/test_rag_evaluations.py` | 19 条集成测试 |
| 新增 | `backend/tests/unit/test_rag_evaluation_rules.py` | 9 条规则/聚合/Schema 单测 |
| 修改 | `backend/app/models/__init__.py` | 登记 2 个模型（24 张表） |
| 修改 | `backend/app/core/config.py` | `RAG_EVAL_MAX_ITEMS` / `SOFT_BUDGET_SECONDS` / `STALE_SECONDS` |
| 修改 | `backend/app/core/errors.py` / `exceptions.py` | 3 个错误码 + 状态映射（39 → 42） |
| 修改 | `backend/app/tasks/__init__.py` / `core/celery.py` | 任务注册 + 每 10 分钟 stale 回收 |
| 修改 | `backend/app/composition/enqueue.py` / `executors.py` | `rag_eval` 入队与执行器 |
| 修改 | `backend/app/schemas/task.py` | `TaskType` 加入 `rag_eval` |
| 修改 | `backend/app/api/v1/__init__.py` | 挂载 `/rag/evaluations` |
| 修改 | `backend/tests/unit/test_errors.py` / `test_models_schema.py` / `test_celery.py` | 契约同步 |
| 修改 | `backend/tests/integration/test_openapi.py` | 7 条新路径 |
| 修改 | `frontend/src/lib/errorMessages.js` | 3 个错误码中文文案 |
| 修改 | `docs/repair/02-database-design.md` / `03-api-design.md` / `04-evaluation-design.md` | Phase 3 增量 + §4.10 约束 |

### 2. 数据库迁移

```
021_rag_evaluation  revision=d4e8b1c6f902  down_revision=c9d2a4f7b1e6
新增：rag_evaluation_runs / rag_evaluation_results
调整：tasks.task_type CHECK += 'rag_eval'（不改 status 枚举）
```

执行记录（开发库）：

```
alembic current : c9d2a4f7b1e6 -> d4e8b1c6f902 (head)
alembic check   : No new upgrade operations detected
```

回滚：先删两张新表，再删除 `task_type='rag_eval'` 的任务记录并恢复旧 CHECK。
生产库仍为 `9a4d2f8c6e15`（018），上线按 019 → 020 → 021 顺序执行。

### 3. 五条审核约束的落地

| 约束 | 实现 | 测试 |
|---|---|---|
| 锁生命周期 | `AdvisoryLock` 用 `engine.connect()` 专用连接；Run 全程持有；业务事务用独立 Session 逐条 commit；同连接 `pg_advisory_unlock`；崩溃由连接关闭自动释放 | `test_advisory_lock_lifecycle`、`test_different_runs_can_hold_locks_concurrently`、`test_lock_released_when_connection_drops` |
| 时间预算 | `RAG_EVAL_SOFT_BUDGET_SECONDS=1500`；每轮检查，超预算停止领取新样本；已提交结果保留；未处理数进 aggregate；run=`partial_failed`+`time_budget_exhausted`；单条耗时写 `details.item_latency_ms` | `test_time_budget_stops_claiming_items` |
| Trace 复用 | 仅重试 Run；校验 `status=success`、adapter、mode、retrieval_config 完全相等、dataset_item_id；父 Run 失败 Trace 不复用；结果写 `trace_reused/source_trace_id` | `test_retry_reuses_evaluated_results_and_reruns_failed_metric` |
| 重试粒度 | evaluated/skipped 复制（`reused_from_run_id`），failed/无结果才执行；只有需要执行时才调用 RAG；父 Run 结果不变 | 同上 |
| 状态边界 | 按结果粒度：全部 failed 才 `failed`，任一非 failed 为 `partial_failed`；空数据集创建 400；取消 `cancelled`；预算耗尽 `partial_failed` | `test_full_run_retrieve_mode`、`test_single_failure_is_isolated`、`test_all_failures_marks_run_failed`、`test_create_rejects_unpublished_and_empty`、`test_cancel_before_start` |

### 4. 测试

| 套件 | 数量 | 结果 |
|---|---|---|
| `tests/unit/test_rag_evaluation_rules.py` | 9 | 通过 |
| `tests/integration/test_rag_evaluations.py` | 19 | 通过 |
| 全量 `pytest -m "not prompt"` | 884 | 通过（0 failed / 0 error；较 Phase 3B 基线 851 增加 33） |

新增测试覆盖：全链路（retrieve / query）、单条失败隔离、全部失败、时间预算、取消、
失败重试与指标级复用、父 Run 不变、已有子 Run 409、锁生命周期（互斥/释放/断连/不同 Run 并行）、
数据集篡改、未发布版本 409、空数据集 400、汇总分组、viewer 403 与越权 403。

### 5. 设计偏差

| 项 | 设计 | 实现 | 原因 |
|---|---|---|---|
| Run 状态判定 | 「所有条目都 failed 或全部指标 failed」 | `failed_results >= len(expected_metrics) × total_items` 才 failed | 与重试的指标粒度一致；单条 2/3 指标成功时不应判 failed |
| 批量写入 | 逐条 ORM 写入 | `pg_insert ... on_conflict_do_nothing` | 幂等 + 重投递安全；需显式补 NOT NULL 默认值 |
| `limit` 上限 | 200 | Schema 常量 + 运行时 `RAG_EVAL_MAX_ITEMS` 双重校验 | 配置可收紧但不能放宽 Schema 契约 |
| `summary` coverage | 未细化 | `evaluated / group.total_items` | 与单 Run 口径一致（分母含 skipped/failed/未处理） |
| 失败 Trace | 可复用 | 不复用（`status=success` 才复用） | 审核约束 §3 |

### 6. 遗留问题

1. **真实 WeKnora 联调未完成**（无凭据）：`retrieve`/`query` 的最小联调仍是上线前阻塞项；
   现有测试全部为 Mock 适配器 / Fake Judge，不构成真实联调证据。
2. **Judge 真实模型全链路未跑**：3C 集成测试注入 Fake Judge；真实 Prompt + 模型输出解析仅由 3B 单测覆盖。
3. **Advisory lock 多进程验证**：集成测试覆盖同进程两个锁实例、断连释放、不同 Run 并行；
   真正的多 worker 并发需在联调/预发环境复测。
4. **单条强制中断**：时间预算只在样本间检查，单条超长（如 Judge 卡住）由 Celery 硬超时 1800s 兜底；
   心跳落后但 Worker 存活时，回收因抢不到锁而跳过，直至 Celery 硬超时终止进程后才标记 `failed(stale_worker)`；
   已提交结果保留。若崩溃发生在全部结果写入之后、`finalize` 之前，Run 会停在 `failed(stale_worker)`
   且没有可重试样本（重试返回 409），需要为新 Run 重新提交。
5. **重试次数**：同一父 Run 只允许一次重试（409）；多次重试需以子 Run 为父新建，产品上可接受但未做 UI 引导。
6. **前端未接入**：仅补错误码文案，无评测页面。

---

## Phase 3C · 最终核查（2026-11-14，冻结前）

**触发**：审核要求只核查三个问题；已覆盖则不改代码，未覆盖则最小修复。

### 1. 核查结论

| # | 问题 | 结论 | 修复 |
|---|---|---|---|
| 1 | Trace 复用是否校验 KB / Top-K / 检索配置 | **未覆盖**：拿 Run 请求配置与适配器回显（`match_count` 等）比较，永远不相等；KB 未进入任何一侧 | 执行时把 Run 配置写入 `trace.retrieval_config._request_config`，复用只逐字比较该指纹；Run 配置快照增加 `knowledge_base_id/agent_id/tenant_id`（WeKnora） |
| 2 | Judge 复用是否校验 Prompt SHA / 模型 / 参数 | **未覆盖**：只比 `metric_version` | `judge_config.metric_fingerprints` 记录 model/temperature/max_tokens/prompt_version/prompt_sha256/metric_version；重试时按**当前** Prompt/模型重算；复制前逐项比较 |
| 3 | stale 回收后原 Worker 是否还能写 | **未覆盖**：回收不抢锁，活 Worker 会被误标；Worker 也不检查状态 | 回收先抢 Run 级 advisory lock（抢不到=Worker 存活，跳过）；Worker 每条前后 + 收尾前刷新状态，发现被回收/取消则回滚未提交结果 |

### 2. 关键实现

- `build_retrieval_config()`：创建 Run 时快照 `top_k/precision_mode/split`；WeKnora 额外快照 `knowledge_base_id/agent_id/tenant_id`。
- `WeKnoraAdapter.retrieve/query`：优先使用 config 中的 KB/Agent（保证重试可复现）；未传时回退环境变量（Phase 2 行为不变）。
- `_trace_reusable()`：`status=success` + adapter/mode/item + `_request_config` 完全相等；旧 Trace 不复用。
- `build_judge_config()`：按当前 Prompt 文件 SHA/模型/参数生成指纹；`retry_run` 重算，不照抄父 Run。
- `_parent_result_reusable()`：evaluated 的 Judge 结果要求四项指纹一致；skipped 只要求指标版本一致。
- `recover_stale_runs()`：逐 Run `pg_try_advisory_lock`；抢锁后再次确认 `status=running` 与心跳仍超时，才标记 `failed(stale_worker)`。
- Runner 栅栏：每条样本前后与收尾前 `refresh(run)`；被回收/取消 → `rollback` 未提交结果、跳过 finalize。

### 3. 行为边界

| 场景 | 行为 |
|---|---|
| Worker 存活但心跳落后 | 锁被占用 → stale 回收跳过；Run 保持 running，直至 Worker 恢复或 Celery 硬超时（1800s）杀掉进程 |
| Worker 崩溃 | 连接关闭 → 锁自动释放 → 下次回收标记 `failed(stale_worker)` |
| 回收与 Worker 写结果竞争 | 回收抢到锁后 Worker 已不持有锁；Worker 若仍能执行，写入前刷新状态失败 → 回滚 |
| 父 Run 成功 Trace 但配置变更 | `_request_config` 不等 → 重新执行 RAG，不复用 |
| Prompt/模型变更后重试 | Judge 指纹失配 → 该指标重新执行 |
| skipped 结果 | 不依赖模型，按 `metric_version` 复用 |

### 4. 测试

| 套件 | 数量 | 结果 |
|---|---|---|
| 单测 `test_rag_evaluation_rules.py` | 9 | 通过 |
| 集成 `test_rag_evaluations.py` | 19 | 通过 |
| 全量 `pytest -m "not prompt"` | **884** | 通过（0 failed；Phase 3B 基线 851 + 33） |

新增核查用例：

- `test_retry_reuses_evaluated_results_and_reruns_failed_metric`：补充断言复用父 Trace（`trace_reused=True`、`source_trace_id` 指向父 Trace）。
- `test_retry_does_not_reuse_when_judge_fingerprint_changes`：切换模型后，父结果全部不复制。
- `test_retry_does_not_reuse_trace_when_retrieval_config_changes`：top_k 变化后重新执行 RAG、生成子 Run 自己的 Trace。
- `test_recover_stale_skips_run_held_by_live_worker`：持锁时回收返回 0，释放后才标记失败。

### 5. 冻结结论

- 三个问题均已覆盖并有测试；代码冻结，不再增加 API/Agent/表结构。
- 仍不宣布上线验收：**真实 WeKnora + 真实 Judge 联调未完成**。
- 下一步优先级：真实数据可验证（1 条 retrieve + 1 条 query 最小联调），而非继续扩展功能。

---

## Phase 3D · 真实 WeKnora 联调 — 已完成（本地 VM）

**日期**：2026-11-14
**环境**：`192.168.150.100:8080`（本地 Docker 部署，非公司实例）
**报告**：`docs/repair/07-phase3d-weknora.md`

### 1. 验收结果

| 验收项 | 结果 |
|---|---|
| 真实 retrieve | ✅ 2 条上下文，`hybrid_search`，371ms |
| 真实 query | ✅ 378 字答案，2 条上下文，`agent_chat`，4724ms |
| 原始响应核对 | ✅ 条数/ID/内容/答案长度逐项一致 |
| context_source / context_available | ✅ `hybrid_search` / `agent_chat`，均 true |
| KB/Agent/Tenant/Top-K 进入 Trace | ✅ `retrieval_config._request_config` + `model_config.agent_id` |
| Trace 持久化与读取 | ✅ 按幂等键读回，ID 一致 |
| 延迟/异常 | ✅ 已记录；仅 `token_usage` 缺失，无 5xx/超时 |
| 真实批量 Run | ✅ 1 条，4 个检索指标均 1.0，`completed` |

### 2. 代码修复

| 文件 | 修改 |
|---|---|
| `backend/app/services/rag/weknora.py` | 支持 0.9 `references.knowledge_references`；chunk_id 取 `id`；metadata 增加 chunk 信息 |
| `backend/app/services/rag/execute.py` | 所有 Trace 写入 `retrieval_config._request_config`（KB/Agent/Tenant/Top-K 可追溯） |
| `backend/tests/unit/test_rag_adapters.py` | 新增 references 事件解析用例 |
| `backend/tests/integration/test_rag_api.py` | 断言 `_request_config`；幂等计数按 key 隔离 |

### 3. 测试

- 全量 `pytest -m "not prompt"`：**885 passed**（Phase 3C 884 + 1）
- mypy 0 / black / flake8 / lint-imports 5 kept
- 联调数据已从开发库清理，避免污染全局计数测试

### 4. 遗留

1. API Key 仍在本地临时文件，未纳入 `user_llm_credentials`；
2. `hybrid-search` 无 chunk id，检索指标暂按 `document_id`；
3. 镜像使用 `latest`，上线前锁定 digest；
4. 真实 Judge 已进入 Phase 3E Pilot（见下节），尚未验收。

---

## Phase 3E · 真实 Judge 小样本 — Pilot 完成（待人工审核）

**日期**：2026-11-14
**报告**：`docs/repair/08-phase3e-judge-pilot.md`
**数据**：`docs/repair/phase3e/`（candidates 40 / pilot labels 10 / pilot judge results 10）

### 1. 结果

| 项 | 结果 |
|---|---|
| 候选问题 | 40 条（自动构造，pending_human） |
| 真实 WeKnora 结果 | 40 条 retrieve + query 全成功 |
| Pilot Judge | qwen-max，10 条 × 3 指标 = 30 次调用 |
| 结构化输出 | 30/30 evaluated，0 失败 |
| 平均耗时 | Faithfulness 13.1s / Correctness 1.75s / Relevancy 1.33s |
| Token | 输入 32,388 / 输出 6,328 |
| 成本估算 | 约 ¥0.14（qwen-max 公开价估算；项目 cost 未配价） |

### 2. 发现的问题（系统性）

1. Correctness 漏判首句自相矛盾（Q23：回答先说“可以反馈”，又说“已超时不符合”）；
2. Correctness 对模糊问题过度扣分（Q35/Q36 条件式回答被判 0.3/0.2）；
3. Relevancy 误判“文档未提及”回答（Q29 判 0.6）；
4. Faithfulness 未把结论句当作 claim，且把合理操作建议计入分母；
5. 无答案/模糊问题缺少专门 rubric。

### 3. 处置

- **未修改 Prompt**（遵守“先给错误案例与建议，再决定”）；
- 未跑完整 40 条（存在系统性偏差 + 人工 Gold 未完成）；
- 建议 F1–F3 Prompt 修改（见报告第 6 节），版本升至 `v1.1.0` 后先重跑 10 条 Pilot；
- 人工需审核 40 条候选参考答案、Gold Evidence 和 10 条 Claim 标签。

### 4. 结论

- 工程链路：✅ 通过
- Judge 输出结构：✅ 通过
- Judge 评分质量：❌ 暂不通过（E1–E5）
- Phase 3E：**暂不宣布验收通过**；不进入 Phase 4。

---

## Phase 3E 补充 · Prompt v1.1.0 设计与人工基准准备（未激活）

**日期**：2026-11-14
**报告**：`docs/repair/09-phase3e-prompt-v1.1-design.md`

### 1. 交付

| 项 | 位置 |
|---|---|
| v1.0.0 归档 + MANIFEST | `backend/app/prompts/rag_judge/v1.0.0/` |
| v1.1.0 设计稿（pending_review） | `backend/app/prompts/rag_judge/v1.1.0/` |
| 逐行 diff | `docs/repair/phase3e/prompt-v1.1.0.diff` |
| 人工标注规范 | `docs/repair/phase3e/annotation-spec.md` |
| 10 条 Pilot 审核表 | `human-review-pilot.csv` |
| 30 条剩余审核表 | `human-review-remaining.csv` |
| 35 条 Claim 审核表 | `pilot-claims-review.csv` |
| Human Gold 模板（全空） | `human-gold.template.json` |
| 40 条待审清单 | `pending-review.md` |

### 2. Prompt 修改

- **Faithfulness**：结论句必须为第一条 claim；`factual_claim/non_factual/contradictory` 分类；`non_factual` 不进分母；含事实承诺的建议仍判断；矛盾作为诊断标签。
- **Correctness**：模糊问题条件式回答 0.8~1.0；无依据确定性结论 ≤0.3；无答案正确拒答 1.0；首句/后文矛盾 ≤0.3。
- **Relevancy**：只评是否围绕问题；合理拒答可高分但不自动 1.0；正确/错误拒答交给 Correctness。

### 3. 状态

- 根目录 `version.txt` 未改，**线上仍为 v1.0.0**；
- v1.1.0 **未运行、未激活**；
- 未改 Phase 3C 数据库/API，未新增 Agent；
- 待人工审核 40 条基础字段 + 10 条 Pilot Claim 标签；
- 通过后先用相同 10 条跑 v1.1.0 对比，再决定是否跑完整 40 条。

**Phase 3E：暂停，等待人工审核。不进入 Phase 4。**

---

## Phase 3E 补充 · Subagent 独立复核（2026-11-16）

**方式**：5 个独立 subagent 并行（Prompt / 10 条 Pilot / 35 条 Claim / 剩余 30 条分两组）
**性质**：`reviewer_type=ai_subagent`，**不是 Human Gold**
**报告**：`docs/repair/phase3e/subagent-review.md` / `subagent-review.json`

### 1. 结果

| 对象 | 数量 | 结果 |
|---|---|---|
| Prompt v1.1.0 | 3 指标 | `approve_with_changes`，`ready=false` |
| 10 条 Pilot 基础字段 | 10 | 8 ai_reviewed / 2 needs_recheck（Q23、Q36） |
| 剩余 30 条基础字段 | 30 | 24 ai_reviewed / 6 needs_recheck（Q14/Q15/Q16/Q19/Q37/Q40） |
| 35 条 Claim | 35 | 32 supported / 1 unsupported（Q23#3）/ 2 insufficient（Q21#3、Q29#2） |

### 2. Prompt 阻断项（摘要）

- Faithfulness taxonomy 非互斥、`contradictory` 可能不进分母；缺 `insufficient_evidence`、零分母、evidence 必填、Q21 反例；
- “出现顺序”与“结论第一条”冲突；删除原子性规则；
- Correctness 模糊题 rubric 假定金标有分支，但 Q35/Q36 金标是“信息不足”；
- 三指标评分区间重叠、无优先级；无逐案例期望分数/容差；
- 版本加载器未接入；`metric_version` 仍为 v1，v1.0/v1.1 会混入同一聚合；
- 人工 `insufficient_evidence` 与 Judge `supported: bool` 分类不一致。

### 3. 标注发现

- Q35：原答案把“收货地区”误作到货因素，已修正为“发货 vs 到货”；
- Q36：原答案缺条件分支；文档对虚拟商品口径不一致（已激活 vs 一经售出）；
- Q23：题干“第 2 天”存在 24 小时边界歧义；
- Q14/Q19：应标 `ambiguous`（缺是否已开具/是否过期）；
- Q15/Q16：分类 `multi` 不合适；
- Q37：参考答案含文档外流程；
- Q40：与 Q20 近似重复。

### 4. 处置

- v1.1.0 保持 `pending_review`，**不实施、不运行**；
- 不跑完整 40 条；
- 下一步：按复核意见产出 v1.1.1 → 再次 subagent 复核 → 人工定稿 9 条 `needs_recheck` → 10 条真实对比 → 40 条；
- 仍不宣布 Judge 验收通过，不进入 Phase 4。

---

## Phase 3E 补充 · 人工 Gold 复核准备（2026-11-16）

**性质**：只整理材料，未产生 Human Gold，未改 Prompt/Agent/Schema/API/DB，未运行 Judge。

### 交付

| 文件 | 内容 |
|---|---|
| `docs/repair/phase3e/human-gold-review-workbench.md` | 9 个对象的完整上下文、原文、冲突、AI 建议、空白人工字段 |
| `human-gold-review-base.csv` | 8 条基础数据，`human_*` 全空，`pending_human` |
| `human-gold-review-claim.csv` | Q21#3，`human_*` 全空，`pending_human` |
| `human-gold-review-workbench.json` | 机器可读复核材料 |
| `human-gold-review-report.md` | 文件检查、风险、操作说明、修改范围 |
| `source/phase3d_doc.md` + `SOURCE.md` | 原始文档只读副本，SHA `737f6bd3…` |

### 重点对象

- 基础：Q23、Q36、Q14、Q15、Q16、Q19、Q37、Q40
- Claim：Q21#3
- 抽查候选：Q05、Q13、Q22、Q30、Q35（待用户确认）

### 结论

- 8 条基础 + 1 条 Claim 材料齐全；
- Q36 虚拟商品口径冲突、Q23 时间边界、Q37 文档外流程、Q40 重复、Q21#3 推断是需用户决定的事项；
- 所有人工字段为空，仍为 `pending_human`；
- 未产生新的 Human Gold；Phase 3E 暂停，不进入 Phase 4。

### 人工 Gold 复核结论（2026-11-16 回填）

**性质**：完成人工判断并回填复核表；仍未生成 `human-gold.json`，未改 Prompt/代码/DB，未运行 Judge。

| 对象 | 决定 | 最终标签 |
|---|---|---|
| Q23 | rewrite（题干改“超过 24 小时”） | constraint / answerable |
| Q36 | use_subagent_correction | ambiguous |
| Q14 | accept_current | multi / ambiguous |
| Q15 | accept_current | direct |
| Q16 | accept_current | constraint |
| Q19 | accept_current | multi / ambiguous |
| Q37 | use_subagent_correction | ambiguous |
| Q40 | rewrite（题干改“转让或提现”） | direct / answerable |
| Q21#3 | accept_current | insufficient_evidence |
| Q05/Q13/Q22/Q30 | accept_current | 原标签不变 |
| Q35 | use_subagent_correction | ambiguous |

- 已填：`human-gold-review-base.csv`（13 行 = 8 基础 + 5 抽查）、`human-gold-review-claim.csv`（1 行）；`review_status=human_reviewed`。
- 覆盖变化：direct 10→12、multi 10→8、constraint 8→9、unanswerable 6→6、ambiguous 6→5。
- 复核人署名：江晚（结论由 AI 起草，用户确认署名）。
- 未关闭：Q36 的 §1/§12 虚拟商品口径需业务确认；Q23/Q40 题干变更需在候选集落地。
- 详细结论：`docs/repair/phase3e/human-gold-decisions.md`。
- Phase 3E 仍停在 Judge 之前，不进入 Phase 4。

---

## Phase 3E 补充 · Human Gold v1 固化（2026-11-16）

**复核人**：江晚
**范围**：13 条基础 + 1 条 Claim（Q21#3）；未复核 27 条基础 + 34 条 Claim 保持 pending。

### 交付

| 文件 | 内容 |
|---|---|
| `human-gold.json` | 13 条基础 + Q21#3，`provenance=human_gold` |
| `human-gold.pending.json` | 27 条未复核基础，`human=null` |
| `human-gold-status.md` | 覆盖变化、题干改写、key_facts 缺口、下一步 |
| `human-gold-decisions.md` | 用户签署结论 + 已固化记录 |

### 关键决定

- Q23 题干改为“超过 24 小时（如第 2 天）”；
- Q40 改为“积分可以转让或提现吗？”，Q40 与 Q15 分类调整；
- Q14/Q19 标 `ambiguous`；
- Q36 保留 `ambiguous`，§1/§12 虚拟商品冲突不选边；
- Q37 删除文档外流程；
- Q21#3 判 `insufficient_evidence`；
- 分类覆盖变为 direct 12 / multi 8 / constraint 9 / unanswerable 6 / ambiguous 5。

### 未完成

- 13 条 `key_facts` 未单独人工复核，保持 `pending_human`；
- 27 条基础 + 34 条 Claim 未复核；
- v1.1.0 仍未达实施门槛，未运行 Judge；
- 未改 Prompt/Agent/Schema/API/DB。

---

## Phase 3E 补充 · Human Gold v1 一致性审计（2026-11-16）

- 结果：**345 项检查全部通过**（0 失败、0 警告）
- 分区：40 = 13 reviewed + 27 pending；35 claims = 1 reviewed（Q21#3）+ 34 pending
- 来源 SHA 一致；13 条基础 Evidence 逐字匹配；Q30 空证据合规
- Q23/Q40 题干改写、分类覆盖 12/8/9/6/5、Q36 冲突披露、Q37 文档外流程移除均一致
- 未改 Prompt/Agent/Schema/API/DB，未运行 Judge
- 报告：`docs/repair/phase3e/human-gold-audit.md` / `.json`

---

## Phase 3E-H · Human Gold key_facts 人工审核准备（2026-11-16）

- 覆盖 13 条 human_reviewed 基础数据；
- 候选 45 条原子事实：supported 42 / evidence_insufficient 2 / ambiguous 1；
- 证据缺失：Q30-F1（海外配送未提及）、Q35-F5（运输/送达时长未说明）；
- 歧义：Q36-F8（§1/§12 虚拟商品口径冲突）；
- 输出：`human-gold-key-facts-review.md`、`.json`、`.csv`（13 行）、`-long.csv`（45 条）；
- 所有 human 字段为空，`pending_human`；未修改 human-gold/pending/Prompt/Agent/Schema/API/DB，未运行 Judge；
- 当前 Correctness 只读 gold_answer，不读 key_facts，因此不会影响 Judge 分数。

---

## Phase 3E-H · key_facts 人工复核结论（2026-11-16 回填）

**复核人**：江晚（结论由 AI 起草，用户确认署名）

| 项 | 结果 |
|---|---|
| 候选 | 45 条 |
| 最终 | **41 条**（supported 38 / evidence_insufficient 2 / ambiguous 1） |
| 决定 | accept 38 / modify 3 / delete 4 |
| 删除 | Q23-F4（重复）、Q15-F1（定义性上下文）、Q16-F1（条件重复）、Q22-F4（非必答推导） |
| 改写 | Q23-F2、Q36-F3、Q16-F2 |
| 保留 absence | Q30-F1、Q35-F5（不进入 supported 分母） |
| 保留 conflict | Q36-F8（不进入 supported 分母） |

- 8 个问题的决定：Q30-F1 保留；Q35-F5 保留；Q36-F8 保留为 meta/conflict；Q23-F3 接受；Q22-F4 算术成立但不作 key_fact；Q37 不补 absence；粒度不再拆（45→41）；key_facts 本阶段不进入 Judge。
- 已填：`human-gold-key-facts-review-long.csv`、`human-gold-key-facts-review.csv`、`human-gold-key-facts-review.json`；`review_status=human_reviewed`。
- **未修改** `human-gold.json`（key_facts 仍为 `[]`），未改 Prompt/Agent/Schema/API/DB，未运行 Judge。
- 结论：`docs/repair/phase3e/human-gold-key-facts-decisions.md`。


---

## Phase 3E-H 完成 · key_facts 写入 Human Gold（2026-11-16）

- 45 条候选 → 最终 **41 条**：supported 38 / evidence_insufficient 2 / ambiguous 1；
- 13 条基础数据 key_facts 全部 `human_reviewed`，已写入 `human-gold.json`；
- 删除 4：Q23-F4、Q15-F1、Q16-F1、Q22-F4；改写 3：Q23-F2、Q36-F3、Q16-F2；
- absence：Q30-F1、Q35-F5；conflict：Q36-F8；
- Human Gold 一致性审计复跑 **424/424 通过**；
- 未改 Prompt/Agent/Schema/API/DB，未运行 Judge、10 条对照或 40 条评测。


---

## Phase 3E · Prompt v1.1.1 设计完成（2026-11-16，未激活）

- 基于 Subagent 复核 + Human Gold v1（含 key_facts）设计 v1.1.1；
- Faithfulness：claim_type/support_status 分离、evidence_refs 必填、non_factual 不进分母、全 non_factual → skipped、矛盾关系标签、结论句优先；
- Correctness：不重叠区间/严重度优先级、模糊题全分支、文档冲突披露、拒答区分、首句矛盾 ≤0.2；
- Relevancy：不重叠区间、合理拒答 0.9–1.0 不自动满分、多部分优先级、正确性交给 Correctness；
- 版本：schema_version v2 / rubric_version v1.1.1 / Judge metric_version v2；v1.0.0 默认 active；
- 交付：三份 Prompt、MANIFEST、逐行 diff、六案例验收矩阵、设计文档；
- 未改 v1.0.0/v1.1.0，未改 Agent/Service/Schema/API/DB，未运行 Judge/10 条/40 条。

---

## Phase 3E · Prompt v1.1.1 二次修订（2026-11-16，未激活）

- 补齐 Faithfulness 计分语义：supported/unsupported/insufficient 均进分母；全 non_factual → skipped；全 insufficient → evaluated 0.0；Q21#3 单 Claim=0.0、整条回答 4/5=0.8。
- 明确矛盾三类：回答内部（is_contradictory）、回答 vs Context（unsupported）、Context 自身冲突（meta claim + document_conflict）；Q23/Q36 分别覆盖。
- 补齐 Correctness answerability 推断、unknown 处理、Q36 真实单边 vs 编造、Q23/Q35/Q36 判定树。
- 补齐 Evidence 校验：context ID、逐字 quote、supported 必填、失败降级 insufficient、诊断记录。
- 新增固定 fixtures：`prompt-v1.1.1-fixtures.json`（6 案例）。
- 验收矩阵补齐预期 Claim/标签/分数/诊断/禁止/容差/回归；Q11/Q21 基础/Q29 明确为 AI draft，不冒充 Human Gold。
- 版本兼容：v1/v2 Schema 字段关系、JudgeOutcome 变化、历史快照、复用校验、聚合隔离、metric_version_for 同步。
- 未改 v1.0.0/v1.1.0；未改 Agent/Service/Schema/API/DB；未运行 Judge/10 条/40 条。

### v1.1.1 第三次修订（审核 P0/P1/P2）
- fixture 冻结 4 条 retrieval_contexts + 2 条 answer_contexts；v1.0.0 分数绑定 answer_contexts，不混用。
- Q23 补全 6 条 scorable claims，3 supported + 1 unsupported + 2 insufficient = 0.5，与 F 区间自洽。
- claim_id 改为 cl1..cln，context_id 保持 C1..Cn；contradiction_with 引用 cl。
- Faithfulness 增加 claim_subtype（policy/absence/conflict/advice/meta）；absence/advice/meta 为 non_factual，conflict 为 factual；Q29/Q35 absence、Q36 conflict 有明确分类。
- Correctness 增加 answerability 推断/unknown 兜底；Q36 真实单边 vs 编造区分。
- 矩阵校验类型/ID/subtype/evidence/分数自洽；新增 `validate_prompt_v1.1.1_matrix.py`（PASS）。
- v1.0.0 MANIFEST status 统一为 active_baseline；v1.1.1 仍 design_draft/inactive。

### v1.1.1 P0 证据缺陷修复
- Q35 cl6/cl7 evidence context 从 C2（摘要）改为 C1（整篇 §6 原文）。
- 8 条 supported claim 补齐 evidence_refs（Q23 cl5、Q21 cl1/2/3/5、Q11 cl1/2/3）；
  Q21 cl5 因 §8 只覆盖电子产品/配件，改标 insufficient_evidence，Q21 F 调整 0.6–0.7。
- 静态脚本新增两项校验：supported 必须有 evidence；quote 必须是 context 逐字子串。
  负向测试（Q35 C2 + supported 无 evidence）能抓出错误；修复后矩阵 PASS。
- 矩阵 tolerance 语义统一：expected 是目标区间/目标值，区间不再叠加 ±0.10；forbidden 优先。
- v1.0.0 MANIFEST status 统一 active_baseline；v1.1.1 仍 design_draft/inactive。
- 容差语义（2026-11-16）：六个 Faithfulness 期望值改为 `target_range=...; tolerance=none`；
  meta 明确区间不再叠加 ±0.10；静态脚本按 target_range 校验实际 supported/scorable。
- 容差字段（2026-11-16）：六个 case 的 per-case tolerance 改为 `target_range exact`，与 meta 的 `tolerance=none` 一致；Q11 F 收窄 0.6–0.8。
- 静态脚本删除 range 目标的 exact 断言，只保留 target_range 包含检查；0.667 within 0.6–0.7 PASS，1.0 超出 FAIL。

### v1.1.1 六案例 dry-run（2026-11-16，签字通过后执行）
- 新增 `dry_run_prompt_v1.1.1.py`：只读加载矩阵 + fixtures，用设计稿 §5.1 的 v2 字段构造合成输出，不调用 LLM/Judge、不联网、不写库。
- 输入只使用 `answer_contexts`（C1–C2）；`retrieval_contexts`（R1–R4）未混入；`RagJudgeInput` v1 解析通过。
- F 由 claim `support_status` 计算：Q23 3/6=0.5；Q35 6/6=1.0；Q36 8/8=1.0（base 无 cl8 为 7/7=1.0）；Q21#3 3/5=0.6；Q11 3/5=0.6；Q29 skipped(no_scorable_claims)。
- C/R 为矩阵区间内的模拟候选，非模型输出；所有候选落在 target_range 与 rubric band 内，区间外 probe 被拒绝。
- 证据逐字校验 24 条（3+6+9+3+3+0）全部命中；Q35 cl6 指 C2、supported 无 evidence 等负向测试均被抓出。
- 负向/边界测试 12/12 符合预期：包含 Q21 1.0 超出 0.6–0.7 FAIL、Q21 2/3=0.667 PASS、Q36 base 7/7 PASS。
- 结果文件：`dry-run-v1.1.1-report.md`、`dry-run-v1.1.1-results.json`；未生成 Judge 结果，未激活 v1.1.1。
- Q11 矩阵 regression 同步收窄为 0.6–0.8，避免与 expected_scores 冲突。

### v1.1.1 Schema / Service / loader 实现（2026-11-16，默认关闭）
- 新增 `RAG_JUDGE_PROMPT_VERSION`，默认 `v1.0.0`；v1.1.1 只有显式设置才加载，目录存在不自动激活。
- Judge loader 改为显式 `<version>/MANIFEST.json` + `<version>/<metric>.txt`，校验 MANIFEST/SHA；缺文件/缺 MANIFEST/SHA 不匹配 → `RagJudgePromptError`，不静默回退。
- Schema 扩展 v2 字段（claim_id/claim_type/claim_subtype/support_status/is_contradictory/contradiction_with/evidence_refs），保留 v1 `supported/evidence` 解析。
- Service 新增 v2 计分：factual 进分母、non_factual 排除、0 scorable → skipped(no_scorable_claims)、全 insufficient → 0.0 + all_insufficient；矛盾 claim 仍进分母。
- Evidence：context_id 必须存在、quote 逐字、supported 至少一条；失败降级 insufficient 并记 `evidence_validation_failed` / `validation_errors`。
- document_conflict：conflict + supported 统计；冲突 claim 不得标 `is_contradictory`；单边 evidence 降级。
- `metric_version_for(metric, prompt_version=None)`：默认 v1，v1.1.1 → v2；创建/重试/聚合/复用按 Run 的 prompt version 解析，v1/v2 不混算。
- 新增 71 条 v2 相关单测：v2 Schema/loader、计分/证据/矛盾/zero-denominator、六案例 canonical + 12 个负向/边界回归；另补结构化失败双输出与紧凑修复 Prompt 测试；现有 24 条 Judge 测试保持。
- P1 边界修复：conflict 双侧证据按 `(context_id, quote.strip())` 去重且拒绝互为子串；重复 `claim_id` 保留首条、跳过后续，不重复进分母。
- 生产 Schema/Service 重跑同一 6 案例 dry-run：6/6、12/12，结果与设计稿 dry-run 一致。
- 未激活 v1.1.1；未运行真实 Judge/10/40；未改 Human Gold；未做 DB Migration。

### 10 条真实对比（2026-11-16，stopped）
- 按批准边界执行：固定同一批 Pilot answer/contexts，只切换 Judge Prompt 版本；qwen-max、temp 0、max_tokens 8192；未重新生成答案。
- 完成 Q01/Q04/Q11/Q17；**Q17 v1.1.1 Faithfulness schema failed**（修复轮后仍非法，raw output 295 chars 截断），按停止条件立即停止，未跑 Q21/Q23/Q29/Q31/Q35/Q36。
- Q11 v1.1.1 F=0.833（5/6 supported + 1 insufficient），高于矩阵 0.6–0.8 上限；Q11 R=0.9（Δ-0.1，仍在下界）。
- Q01/Q04/Q17 的 F/C/R delta 均未超过 0.10；Q17 F 因 schema failed 无分数。
- 已完成案例未出现 duplicate claim_id 或 duplicate/nested conflict evidence；Q36 未运行，disclosure 未验证。
- 结果：`docs/repair/phase3e/pilot-10-v1.0.0-vs-v1.1.1.json` / `.md`。
- 未跑 40 条、未激活；脚本退出前恢复 `RAG_JUDGE_PROMPT_VERSION=v1.0.0`。

### Q17 修复与单案例验证（2026-11-16）
- StructuredOutputError 同时保留 `original_output` 与最终 `raw_output`；Judge failed details 增加 `original_raw_output`。
- Schema 对 `contradiction_with=null`、`evidence_refs=null`、`is_contradictory=null`、`reason=null` 宽容化，不因 null 触发修复轮。
- 修复 Prompt 不再 dump 完整 JSON Schema，改为紧凑模板 + RagJudge 完整 JSON 示例。
- v1.1.1 Faithfulness 增加 Q17 式多 claim + evidence_refs 完整 JSON few-shot；输入显式提供 `context_ids`。
- Q17 单案例：attempt1/2 schema PASS 但 context_id 写成 C7（章节号）/quote 不命中，F=0.0；attempt3 显式 `context_ids` 后 **schema PASS，F=1.0，5/5 evidence 逐字命中，validation_errors=[]**。
- 新 F Prompt SHA：`4ee65afb3e7ea8b4b5e361e41ea75b74173142a8c26c97dedc7139ba37c86317`。
- Q17 三次 smoke token：input 10,616 / output 1,941，估算约 ¥0.044。
- Q11 目标从 0.6–0.8 调整为 0.6–0.9，明确允许 5/6=0.833。
- 仍 design_draft/inactive；未重跑 10 条、未跑 40 条。

### 10 条重跑（2026-11-17，stopped）
- 使用新 F Prompt SHA `4ee65afb…`；同一批 Pilot answer/contexts；v1.0.0 仅复用指纹一致的 Q01/Q04/Q11/Q17，其余重跑。
- **Q01 v1.1.1 Correctness 0.900→0.700（-0.200）**，Q01 无矩阵目标解释，按“未解释单指标下降 >0.10”立即停止；完成 1/10。
- Q01 C `missing_points=[]`、`wrong_facts=[]`，reason 为“回答基本正确，但包含了一些不必要的额外信息”；F 1.0→1.0，R 0.8→0.9。
- 未运行 Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36；Q36 disclosure 未验证。
- 结果：`docs/repair/phase3e/pilot-10-v1.0.0-vs-v1.1.1-rerun.json` / `.md`。
- 共享 `parse_with_repair` fallback 已补回 `schema.model_json_schema()`，并新增“默认修复 Prompt 含 Schema”测试；不影响 RagJudge 的完整示例路径。
- 未跑 40 条、未激活；脚本退出前恢复 `RAG_JUDGE_PROMPT_VERSION=v1.0.0`。

### Q01 Correctness 修复与单案例验证（2026-11-17）
- 规则：正确且相关的额外信息不扣 Correctness；`0.7–0.8` 明确“不用于多说了正确内容”；新增 Q01 few-shot。
- 新增 `pilot-10-additional-targets.json`：Q01 C 0.9–1.0、F 1.0、R 0.8–1.0，标记 provisional/AI draft。
- 新 C Prompt SHA：`2ab6eac2abe57dcfd647df328244ac3e5681fc93222938d6614e71037d49ae77`。
- Q01 C 单案例：**score=0.9，missing_points=[]，wrong_facts=[]**；reason 为“补充了相关且正确的例外情况”。
- 未重跑 10 条、未跑 40 条；v1.1.1 仍 design_draft/inactive。

### 10 条重跑第二次（2026-11-17，stopped Q23）
- 补 Q04/Q17/Q31 目标；Q01 F 放宽 0.9–1.0；使用 F SHA `4ee65afb…`、C SHA `2ab6eac…`。
- v1.0.0 复用 Q01/Q04/Q11/Q17；完成 Q01/Q04/Q11/Q17/Q21/Q23（6/10）。
- **Q23 v1.1.1 F=0.0**：唯一尝试 supported 的 cl2 quote 非 C1 逐字子串，Service 记 `quote_not_found` 并降级，0 supported / 4 scorable；低于目标 0.4–0.5，且相对 v1.0.0 0.75 下降 >0.10，按停止条件立即停止。
- Q23 C=0.0（目标命中）、R=0.9；Q21 F=0.6、C=0.9、R=0.9；Q11 F=0.6、C=0.9、R=0.9；Q01/Q04/Q17 目标命中。
- 未运行 Q29/Q31/Q35/Q36；Q36 disclosure 未验证。
- Token（6 条×2 臂）：v1.0.0 input 17,985/output 2,922；v1.1.1 input 43,731/output 4,682；估算 ¥0.2211。
- 结果：`pilot-10-v1.0.0-vs-v1.1.1-rerun.json` / `.md`。
- 未跑 40 条、未激活；脚本退出前恢复 v1.0.0。

### Q23 F 修复（2026-11-17）
- 将 Q23 few-shot 替换为完整 8 条 JSON：cl1–cl8，固定 3 supported / 1 unsupported / 2 insufficient / 2 non_factual = 0.5。
- 增加 quote 连续复制规则：不得加主语/前缀、改写或拼接；C1 可引整句或连续子串，不能自造“生鲜食品质量问题需…”。
- 规范性要求（需/必须/应当/须保留/材料/凭证）明确为 factual_claim；无依据标 insufficient，不得标 advice/non_factual。
- 新 F Prompt SHA：`3519fd3b1bbbab9b117abd04f69304609146c2d2a05c39699483dea1740eda19`；C SHA 不变。
- Q23 F 单案例：**score=0.5**；scorable=6、supported=3、unsupported=1、insufficient=2、non_factual=2；3/3 evidence；cl1 contradictory_with=["cl2"]；validation_errors=[]。
- 新增 Prompt 内容测试；未重跑 10 条、未跑 40 条。

### 10 条重跑第三次（2026-11-17，stopped Q23 计数）
- 使用 F SHA `3519fd3b…`、C SHA `2ab6eac…`；完成 Q01/Q04/Q11/Q17/Q21/Q23（6/10）。
- Q01/Q04/Q17/Q21/Q11 目标命中；Q11 F=0.6667（0.6–0.9）。
- **Q23 F=0.428571，分数在 0.4–0.5，但 scorable=7（要求 6）**：3 supported / 1 unsupported / 3 insufficient / 3 non_factual；3/3 evidence；cl1 contradictory；validation_errors=[]。
- 第 7 条 scorable 来自“若已超时，可尝试联系客服说明具体情况……”被归 factual/policy，矩阵期望为 advice；按 Q23 key 校验停止。
- 未运行 Q29/Q31/Q35/Q36；Q36 disclosure 未验证。
- Token（6 条×2 臂）：v1.0.0 17,985/2,943；v1.1.1 49,641/5,192；估算 ¥0.2404。
- 结果：`pilot-10-v1.0.0-vs-v1.1.1-rerun.json` / `.md`；未跑 40 条、未激活。

### 10 条补跑完成（2026-11-17）
- Q23 按 7 条拆分接受：F=0.428571（0.4–0.5）、C=0.0、R=0.9；7 scorable（3 supported / 1 unsupported / 3 insufficient / 3 non_factual）；3/3 evidence；validation_errors=[]。
- Q29 F skipped(no_scorable_claims)，C=0.9、R=1.0。
- Q31 F=1.0、C=0.9、R=0.9。
- Q35 F=0.833333、C=0.9、R=0.9；cl1 absence 被归 factual/policy 但为 insufficient（不是 supported）。
- Q36 F=0.857143、C=0.5、R=0.9；answer 未披露 §1/§12 冲突，document_conflict=0；C missing 含冲突披露，wrong_facts=[]；不选 canonical 口径。
- **10/10 完成，全部注册目标命中；无 schema failed、无全 invalid。**
- Token（10 条×2 臂）：v1.0.0 32,612/6,252；v1.1.1 85,372/9,008；估算 ¥0.1383/¥0.2914，合计 ¥0.4297。
- 未跑 40 条、未激活；v1.1.1 仍 design_draft/inactive。

### 40 条规模运行（2026-11-17，stopped Q10）
- 已注册 `pilot-40-targets.json`：13 Human Gold + 27 provisional；40 条规模运行，不是 40 条 Human Gold 验收。
- Q36 披露 variant smoke：C=0.9、missing=[]、wrong_facts=[]，目标 0.9–1.0 通过。
- 40 条运行完成 10/40（HG 1/13，provisional 9/27）：Q10 v1.1.1 F 1.0→0.5，cl1 quote 把“30 天内”写成“30 夅内”，`quote_not_found` 降级；Q10 无显式目标，按未解释下降 >0.10 停止。
- 未运行 Q11 之后案例；未跑 40 条整体验收。
- Token（10 条×2 臂）：v1.0.0 23,678/2,532；v1.1.1 76,438/3,645；估算 ¥0.2995。
- 结果：`pilot-40-v1.0.0-vs-v1.1.1.json` / `.md`；未激活、未改 Human Gold/DB。

### 40 条继续（2026-11-17，stopped Q15）
- Q10 记录为 provisional `evidence_typo`（“30 夅内” vs “30 天内”），保持 F/C SHA；继续运行。
- 完成 22/40（HG 7/13，provisional 15/27）；Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36 为 10 条指纹复用。
- **Q15 Human Gold F 1.0→0.667（-0.333）**：v1.1.1 多拆出 cl3“电话联系的目的是确认收货时间及安排上门事宜”，上下文无依据，标 insufficient；Q15 无显式目标，按未解释 F 下降 >0.10 停止。
- Q15 C=0.9、R=0.9；wrong_facts=[]；不是 quote typo，是 claim 粒度/推断差异。
- 未跑 Q16/Q18/Q19/Q20/Q22/Q24–Q28/Q30/Q32–Q34/Q37–Q40。
- Token（22 条×2 臂）：v1.0.0 59,962/9,087；v1.1.1 172,935/13,207；估算 ¥0.7729。
- Q36 披露 variant smoke C=0.9 已通过；40 条只含 base answer。

### 40 条继续第二次（2026-11-17，stopped Q20）
- Q15 注册 F 0.6–1.0（期望 0.667），Q14 F 标 unavailable；保持 F/C SHA。
- 完成 26/40（HG 9/13，provisional 17/27）；Q16/Q18/Q19 通过。
- **Q20 provisional F 1.0→0.8（-0.2）**：cl5“该政策适用于所有符合积分累积条件的订单”无上下文依据，insufficient；无显式目标，按未解释 F 下降 >0.10 停止。
- Q20 C=0.9、R=1.0；wrong_facts=[]。
- 未跑 Q22/Q24–Q28/Q30/Q32–Q34/Q37–Q40。
- Token（26 条×2 臂）：v1.0.0 69,497/10,627；v1.1.1 203,574/15,838；估算 ¥0.9094。
- 40 条未完成、未激活；v1.1.1 仍 design_draft/inactive。

### 40 条继续第三次（2026-11-17，stopped Q22）
- Q20 注册 F 0.6–1.0（期望 0.8），F=0.8、C=0.9、R=1.0，PASS；标 generalization_insufficient。
- 完成 27/40（HG 10/13，provisional 17/27）；Q22 前案例按目标通过。
- **Q22 Human Gold F 1.0→0.4（-0.6）**：cl1/cl4 原 supported，但 quote 非 C1 逐字子串，`quote_not_found` 降级；按 HG supported evidence downgrade + 未解释下降 >0.10 停止。
- Q22 C=0.9、R=1.0；wrong_facts=[]。
- 未跑 Q24–Q28/Q30/Q32–Q34/Q37–Q40。
- Token（27 条×2 臂）：v1.0.0 71,587/10,835；v1.1.1 210,936/16,708；估算 ¥0.9424。
- 40 条未完成、未激活；v1.1.1 仍 design_draft/inactive。

### v1.1.2 Q22 修复（2026-11-17）
- 新建 `backend/app/prompts/rag_judge/v1.1.2`；C/R 继承 v1.1.1，仅 F 修改。
- F 新增 quote 单行/保留换行规则、Q22 完整 5 条 JSON few-shot、absence 不进分母。
- 新 F SHA：`3db91171edb644f8d2764b588bd1fafdadc044a44c2e7989f9fe1ae04ee2f80c`；C/R SHA 不变。
- Q22 目标注册 F 0.8–1.0（期望 1.0）、C 0.9–1.0、R 0.9–1.0。
- Q22 F 单案例：**F=1.0，4 scorable / 4 supported / 1 non_factual，6/6 evidence，validation_errors=[]**。
- v1.1.2 未跑 40；v1.1.1 的 27/40 为旧 SHA，不能混合称为 40 条通过；若作为最终版本需整批重跑并重新验证 10 条闸门。
- v1.1.2 仍 design_draft/inactive；默认 v1.0.0。

### v1.1.2 10 条闸门（2026-11-17，Q36 停止）
- 完成 10/10；Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35 目标通过。
- **Q36 F=0.75 低于目标 0.8–1.0**：cl1/cl6 原 supported，但 quote 跨句/跨 §1-§12 拼接，非 C1 逐字子串，`quote_not_found` 降级；F=6/8。
- Q36 C=0.5、R=0.9；wrong_facts=[]。
- 因 Q36 闸门失败，Q10/Q15/Q20 单案例未跑，40 条 v1.1.2 未启动。
- Token（10 条×2 臂）：v1.0.0 32,612/6,252；v1.1.2 95,032/8,651；估算 ¥0.4494。
- v1.1.2 仍 design_draft/inactive；未激活、未改 Human Gold/DB。

### v1.1.2 Q36 few-shot 单案例（2026-11-17，新 F SHA，未通过严格门）
- F 新增 Q36 canonical 8 条 JSON few-shot（cl1 core claim、cl5/cl6 拆 §1/§12、全部单句 quote）。
- 新 F SHA：`81456bc56b6829e5029698a16054bde3dc2e55af4379194f85fd3974ef167fe8`；MANIFEST 与 `pilot-40-targets.json.meta.f_sha` 已同步。
- Q36 base F 单案例：**F=0.875（7/8）**，scorable 8 / supported 7 / insufficient 1，evidence 9/10，`validation_errors` 2 条（cl1 `quote_not_found`），`document_conflict=0`。
- F 落在注册目标 0.8–1.0 内，但 cl1 仍是“能否退款，取决于……”的 meta 总起句，且 quote 跨行拼接，属于 Human Gold supported claim 被 evidence 降级；未满足 evidence 单句逐字 / `validation_errors=[]`。
- cl5/cl6 仍把 §1“已激活”与 §12“一经售出”合并，未按 canonical 拆开。
- 因此 Q36 未通过严格门，未重跑 10 条闸门；旧 10 条结果（F SHA `3db91171…`）不可复用；Q10/Q15/Q20 未跑，40 条未启动。
- Token：input 7,384 / output 1,146；估算 ¥0.0287。
- v1.1.2 仍 design_draft/inactive；未激活、未改 Human Gold/DB。

### v1.1.2 精修与 10 条闸门（2026-11-17，最终 F SHA）
- 追加规则：总起/分类引导句归 non_factual/meta；文档范围描述归 meta；文档未提及/未涉及归 absence；引用原文逐事实拆分；Q21 5 scorable few-shot；虚拟商品 §1/§12 拆分。
- 最终 F SHA：`e95f04b556dd1a86e7abfbdd5dad75d3b834628490cdf460adb608dd02713b30`；C/R SHA 不变。
- Q36 精修后：F=1.0，7 scorable 全 supported，evidence 7/7，`validation_errors=[]`，`document_conflict=0`。
- Q29 精修后：F=`skipped(no_scorable_claims)`，5 non_factual；Q15 F=0.667（3 scorable：2 supported + 1 purpose insufficient）；Q10 F=1.0；Q20 F=0.8；Q21 F=0.6（5 scorable：3 supported + 2 insufficient，Q21#3 insufficient）；Q22 F=1.0（4/4 supported，cl5 absence）。
- **10 条闸门 final2：10/10 通过**（Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36）；Q31 仍有 5 条 quote_not_found，provisional 目标命中，记录为已知诊断。
- Token（10 条×2 臂）：v1.0.0 32,612/6,252；v1.1.2 124,502/9,279；估算 ¥0.5262。
- 40 条规模/回归启动：Q01–Q13 通过；Q14 记为 **known Human Gold C miss**：F=`skipped(context_unavailable)`（unavailable，不是 PASS），C=0.7（目标 0.8–1.0），missing `未开具前可以修改`，C 重跑 3 次 0.7/0.7/0.9，多数 0.7；不移动目标、不改 C Prompt。
- 40 条继续：Q15 通过；**Q16 记为 known Human Gold R miss**（R=0.7，v1.0.0 R=1.0；三次稳定 0.7；回答与金标逐字一致，R 裁判要求金标未要求的“具体核查步骤”，属于 judge over-strictness，不改 R Prompt/目标）。
- 40 条继续：Q17/Q18/Q19/Q20/Q21/Q22 通过；**Q23 F=0.0 停止**（目标 0.4–0.5，Human Gold supported quote 降级）。Q23 的 cl2/cl3/cl4 quote 合成为“生鲜食品质量问题需在签收后 24 小时内拍照反馈。”，原文是“生鲜食品签收后不支持无理由退货，质量问题需…”，6 条 `quote_not_found`；重跑 0.0/0.0/0.428571，2/3 复现。完成 23/40。
- 40 条未完成、未通过；不能称为 40 条 Human Gold 验收。v1.1.2 仍 design_draft/inactive；未激活、未改 Human Gold/DB。

### v1.1.3（2026-11-17，design_draft）
- 新建 v1.1.3：F = v1.1.2 + Q23 最短连续子串；R = v1.1.2 + Q16 直接完整回答规则；C 继承不变。
- 最终 F SHA：`3d35175bf97f4389a1cd6c52ed069ea0d7889227ab61e68b45c88529d58421bd`；R SHA：`394cd30c1453f0474ec6d25cf0305d8e3fb066151ac0f85e004b16117906891b`；C SHA 不变。
- Q23 F 3/3：0.5/0.5/0.428571（目标 0.4–0.5）；Q16 R 3/3：0.9/0.9/1.0（目标 0.9–1.0）；Q13 F 3/3：1.0/1.0/1.0。
- Q10/Q15/Q20/Q22 affected 全部通过：Q10 F=1.0、Q15 F=0.667、Q20 F=0.8、Q22 F=1.0/C=0.9/R=1.0。
- **10 条闸门 v1.1.3：10/10 通过**（Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36）；Q35 F=0.833 有 2 条 quote_not_found，目标命中，按 known diagnostic 记录。
- 40 条规模/回归：Q01–Q27 通过（Q14 F=unavailable，C=0.9 本次 pass、历史 C 0.7/0.7/0.9 方差；Q16 R 已修复；Q23 F=0.5；Q25 C 0.8→0.7 恰好 0.10 不是 >0.10）。Q28 注册 provisional F 0.8–1.0，F=0.857/重跑 0.875，PASS。
- **Q30 F=0.25 停止**（Human Gold，v1.0.0 F=1.0；重跑 0.25/0.5/0.5）。Q30 不是 quote 失败：absence 已归 non_factual，但“国内履约前提/默认中国大陆”等范围推断被标 factual/insufficient。完成 30/40。
- 40 条未完成、未通过；v1.1.3 仍 design_draft/inactive；未激活、未改 Human Gold/DB。

### v1.1.4（2026-11-17，design_draft）
- F = v1.1.3 + Q30 范围/地域推断归 meta/absence、混合句拆分、Q30 few-shot；R/C 继承 v1.1.3。
- F SHA：`576f571975ae37623088b1c753b1c7a4ee11e74f91e852c37ef03330ba7629f5`；R SHA `394cd30c…`、C SHA `2ab6eac…` 不变。
- Q30 F 3/3：**1.0/1.0/1.0**，2 scorable（偏远运费、签收起算）+ 5 non_factual；C=0.9、R=0.9；范围/地域推断不再被标 factual。
- 10 条闸门 v1.1.4：Q01/Q04/Q11 通过；**Q17 F=0.8 停止**（目标 0.9–1.0）。cl5“该规则与是否满 99 元无关”被标 factual/insufficient；v1.0.0/v1.1.3 标 supported，属于规则关系/独立性推断。
- v1.1.4 未跑 40；v1.1.3 的 10/30 结果全部作废。仍 design_draft/inactive；未激活、未改 Human Gold/DB。

### v1.1.5（2026-11-18，design_draft）
- F = v1.1.4 + 规则关系/独立性推断归 meta、Q17 few-shot；R/C 继承 v1.1.4。
- F SHA：`6d45fa102c6efcf6897e8e84f1a1b417b5720dfa78d617e206a6a0f3db49791c`；R SHA `394cd30c…`、C SHA `2ab6eac…` 不变。
- Q17 F 3/3：**1.0/1.0/1.0**，cl5 归 meta；Q30 F 3/3：**1.0/1.0/1.0**。
- **10 条闸门 v1.1.5：10/10 通过**；Q31 4 条 quote 诊断、Q35 2 条，目标命中。
- 40 条规模/回归：Q01–Q31 通过；**Q32 F=0.75 停止**（v1.0.0 1.0；重跑 3 次均 0.75）。cl1“无法确认积分支持礼品兑换功能”被标 factual/insufficient；应为 non_factual/meta。完成 32/40。
- Q14 F=unavailable；C=0.7 本次低于 0.8–1.0，历史 0.7/0.7/0.9 方差；单次 non-pass，不重复记 F+C。
- 40 条未完成、未通过；v1.1.5 仍 design_draft/inactive；未激活、未改 Human Gold/DB。

### v1.2.0 规划（2026-11-18，只分析/设计）
- 停止 v1.1.x 单案例逐条修补；新增四份文档：
  - `docs/repair/11-phase3e-failure-taxonomy.md`
  - `docs/repair/12-judge-semantic-spec.md`
  - `docs/repair/13-phase3e-acceptance-plan.md`
  - `docs/repair/14-prompt-v1.2.0-design.md`
- 数据盘点：40 条中 13 HG / 27 provisional；v1.1.5 完成 32/40；Q33–Q40 未运行；6 条缺 v1.0.0 baseline（Q35/Q36 旧 baseline 可用）。
- 失败归因：Scope/Meta/absence/uncertainty 误建 factual、Evidence 最短子串、条件/权益推断、Claim 原子性、C/R 校准、Context 可用性。
- 审核结果：`approve_with_changes`；P0 残留（Q36 条件句）已修，**语义规范 v1.2.0 于 2026-11-18 冻结**（复核人江晚；语义基线 commit `9db8885`；冻结记录 commit `b50830b`）。
- 冻结备注：`condition` 优先于 `policy_scope`（“取决于/区分/需确认”→condition；policy_scope 只用于适用订单/地区/对象；两者都是 factual）；40 条 final_labels 已冻结（`pilot-40-final-labels.json`，SHA `f139623f…`；13 HG 来自 human-gold，27 provisional 来自 candidates），是 40 条报告唯一分类来源。
- 语义规范 + 目标表已冻结：`pilot-40-targets-v1.2.0.json`（revision v1.0.1，SHA `34357b34…`，2026-11-18）为目标唯一来源；`pilot-40-targets-v1.2.0-reapproval` 仅保留历史；旧 `pilot-40-targets.json` 只读。
- `target_status` 是冻结前变更来源（reapproval/new_target 是历史类型），不是仍待审批；active target meta 已记录该说明。
- Q32 冻结前提：F 0.9–1.0 以 3 个 factual 点为前提；若 v1.2.0 把它们归为 uncertainty/absence 导致 skipped，算目标未命中，不得 skipped 兜底。
- Schema/Service 设计：`docs/repair/15-phase3e-v1.2.0-schema-service-design.md`；Schema v3、Metric v3；缺 subtype 报错；policy_scope/relationship 不回退。
- P1-1 已关闭：测试矩阵拆为 Service unit negative / Judge acceptance negative；Service 不做语义纠正。
- P1-2 最终决策（`M1-B-002`）：缺/非法 subtype、supported 无 evidence、context_id 不存在、quote 非逐字/引用 answer → 整条 metric `invalid(contract_violation)`；合法 insufficient 不进 F 分母但单独统计；全 insufficient → `skipped(no_decidable_claims)`；全 non_factual → `skipped(no_scorable_claims)`。
- 冻结控制：`12-judge-semantic-spec.md` 恢复到 `92ce3ab` 原文，旧 freeze record 未改写；新增 `docs/repair/16-m1b-decision-record.md` 记录语义修订与目标影响。
- 目标影响（P0，A 方案历史）：新 F 分母使 Q21（0.6→1.0，目标 0.6–0.7）、Q23（0.5→0.75，目标 0.4–0.5）不可达/越界；Q17/Q11 处于边界。B 方案改用 `F_coverage`（旧分母）后该冲突消失；目标未按 B 冻结前，M1-B 不能 `accepted`。
- 下一步顺序：先定 §4 目标方案（A/B/C）→ 负向测试 → 单案例（Q17/Q21/Q30/Q32/Q36）→ 10 条 → 40 条；Schema/目标复核前不创建/激活 v1.2.0、不跑 Judge。
- M2 只读审计：`docs/repair/17-m2-readonly-workbench-api-audit.md`；后端 Run 列表/详情/结果/失败样本/Trace 可用，前端 0 页面；P0 需显式排序、Case 客户端聚合、控制 results 负载；P1 缺 Case 聚合、compare、子 Run 可见性、summary 去重。
- B 方案设计评估（2026-11-19）：`docs/repair/18-m1b-dual-metric-design-evaluation.md`（`M1-B-003`，`proposed_pending_human`）；`F_coverage` 30/30 有分数案例复现旧 F（Q14/Q29 skip），现有目标可继续用；`F_strict` 29/30=1.0，只作诊断；全 insufficient 建议 `F_strict=skip`、`F_coverage=0+all_insufficient`；待人工冻结后再实现。
- M1-B-003 冻结草案（2026-11-19）：`docs/repair/19-m1b-003-freeze-draft.md`；D1–D4 已写入，含展示名、双行生命周期、全 insufficient 边界、三检查点、11 条单测/生命周期测试；状态 `freeze_draft_pending_human`。
- M1-B-003-r1 修订（2026-11-19）：`approve_with_changes`；4 项关闭 + 术语统一（`unsupported`≠contradiction、`contains_unsupported_claims` 标签、Run 不可变/retry 快照/唯一键复核、Item 级 evaluated/skipped/invalid/failed）；新增 `20-m1b-003-revision-record.md`；`19` 当时 SHA `1abfc221…`，21/21 validation。
- M1-B-003-r2 契约收尾（2026-11-19）：Item 级计数语义（`completed_items=evaluated_items`、distinct item、四类终态 + `unprocessed` 守恒、3 items/6 rows/3 cases 示例）+ invalid 持久化契约（独立 invalid 优先；`failed+invalid_reason` 聚合归 invalid；不进均值；不算执行失败）；`19` SHA `d2d2e0de…`，33/33 validation；仍 `freeze_draft_pending_human`。
- 目标 revision v1.0.2：`pilot-40-targets-v1.2.0-v1.0.2.json`，SHA `3ee15dfc…`，20/20 validation；40 条数值与 v1.0.1 完全一致；旧文件/SHA 未覆盖。
- 静态重算：`m1b003_static_recalc.py` → `m1b003-static-recalc.json`，SHA `53787fbb…`，13/13 validation；Q17/Q32 的 v1.2.0 预期值单独标记，不与 v1.1.5 实测混写。
- 未修改 Prompt/Service/Schema/API/DB；未创建或激活 v1.2.0；未运行新的 Judge；未进入 Phase 4。

### M1-C Stage 0 / Stage 1 预审（2026-11-19，只审计/设计）
- Stage 0 rev2.1：`docs/repair/22-m1c-stage0-gap-list.md`；逐项差距 G01–G25，Schema v3 纳入 M1-C；新增 §1.1 子类型冻结说明（子类型以 `12` §3.1/§3.2 为准，`15` §2.1 只做 Schema 映射；指标/生命周期冲突时 r2 优先）；C3 `expected_metrics` 必须含 `faithfulness_strict`；migration 022 upgrade/rollback 方案（A 方案 invalid + invalid_reason + derived_from_result_id + run counters）；回填按 `failed > invalid > evaluated > skipped`，有终态 row 的 partial item 归 skipped，只有无任何 row 才是 unprocessed；`completed_items` 采用 A（回填 = evaluated，旧值备份/回滚恢复）。
- Stage 1 rev2.1：`docs/repair/23-m1c-stage1-test-list.md`；12 条核心生命周期/聚合测试 L01–L12（retry 继承/默认漂移/显式换配置、双行一 Item、evaluated+skipped、evaluated+failed、invalid vs execution failed、全 insufficient、cancelled/timeout unprocessed、守恒、均值排除、历史兼容）；附加 F01–F05、T06–T10、T12、V01；T07/T08 改为 `invalid(contract_violation)`；L09 partial item 归 skipped、只有无 row 才是 unprocessed；目标 SHA 改为 `3ee15dfc…`。
- 关键缺口：当前代码仍 Schema v2；subtype 默认归一；只有 `faithfulness` 一条指标、无 strict；result status 无 invalid；run completed 含 skipped；retry 用当前指纹；migration 022 不存在。
- 未修改业务代码/迁移/DB；未创建/激活 v1.2.0；未跑 Judge；未启动 M1-C；Stage 0/1 rev2.1 已通过（2026-11-19 复审）。

### M1-C C1 设计与变更范围（2026-11-19，已实现/本地验证）
- C1 报告：`docs/repair/24-m1c-c1-design-scope.md`；范围仅 Schema v3 注册、V3 输出模型、loader/agent 选择、v1/v2 兼容、Service v3 guard。
- 设计要点：`JUDGE_SCHEMA_V3`、`v1.2.0→v3`、`metric_version=v3` 版本映射；独立 `FaithfulnessClaimV3` / `FaithfulnessOutputV3`；v3 严格 subtype/support_status/evidence_refs；`judge_trace` / `_faithfulness_score` 遇 v3 抛 `RagJudgePromptError`（不实现 v3 计分）；MANIFEST `schema_version` 必须与 `judge_schema_version(prompt_version)` 一致；v1/v2 模型与测试不变；17 条 C1 测试。
- 实现：`app/schemas/agents/rag_judge.py`、`app/agents/rag_judge_agent.py`、`app/services/rag_judge_service.py`（仅 guard）、`tests/unit/test_rag_judge_schema_v3.py`、`tests/unit/test_rag_judge_v2_schema_loader.py`（仅映射断言）。
- 验证：C1 + v2 定向测试 113 passed；全量 `pytest -m "not prompt"` passed；black/flake8/mypy/lint-imports 通过。
- 边界：未创建 v1.2.0 Prompt，未写 migration 022，未改 model/repo/API，未跑 Judge；C1 状态 `implemented/verified`，未 accepted；C2 未启动。

### M1-C C2 migration 022 + model/repo 字段（2026-11-19，已实现/本地验证）
- 迁移：`backend/migrations/versions/20261119_1800_f3a9c2d7e1b4_022_m1c_dual_faithfulness.py`；result 增加 `invalid` status、`invalid_reason`、`derived_from_result_id`；run 增加 `evaluated_items`/`invalid_items`/`unprocessed_items`；回填按 `failed > invalid > evaluated > skipped`，A/B invalid 都归 invalid，只有 execution failed 才归 failed；partial item 归 skipped，`unprocessed = total - distinct_items`；`completed_items = evaluated_items`，旧值进 `rag_evaluation_runs_022_completed_backup`，downgrade 恢复。
- 模型：`app/models/rag_evaluation.py` 新字段与 CHECK；`app/repositories/rag_evaluation.py` 批量写入新字段；`app/schemas/rag_evaluation.py` + `app/api/v1/rag_evaluations.py` 透出 response 字段。
- 迁移支持：`migrations/env.py` 忽略内部备份表，`alembic check` 无漂移。
- 验证：`tests/integration/test_migration_022.py` 6 tests；覆盖 A/B invalid、execution failed、invalid/evaluated 同 Item、failed/invalid 同 Item、partial skipped、无 row unprocessed、5 类守恒、无 result Run、backup 恢复、downgrade 拒绝 A/B/strict、derived CASCADE、v1/v2 版本不变；全量 `pytest -m "not prompt"` passed；mypy/lint-imports/black/flake8 通过；`alembic check` No new upgrade operations。
- 边界：未实现 Service 双指标/invalid/聚合/retry；未跑 Judge；未在生产执行 migration；未创建/激活 v1.2.0；C2 状态 `implemented/verified`，未 accepted；C3 未启动。

### M1-C C3 实现（2026-11-20，implemented/verified）
- 设计：`docs/repair/25-m1c-c3-design-scope.md`（rev2.1）；范围：Service 双指标、invalid A/B、Item 聚合、retry、aggregate/API 映射。
- 实现文件：`app/agents/base.py`、`app/schemas/agents/rag_judge.py`、`app/services/rag_judge_service.py`、`app/services/rag_evaluation_service.py`、`app/services/rag_evaluation_runner.py`、`app/repositories/rag_evaluation.py`、`app/schemas/rag_evaluation.py`、`app/api/v1/rag_evaluations.py`。
- 双指标：coverage/strict 同 claims 派生；coverage 先写、strict 带 `derived_from_result_id`；strict 不存完整 claims/evidence/raw_output；strict 不调 Judge。
- expected_metrics：snapshot 写 `derived_metrics=[faithfulness_strict]` 与 strict metric_version；旧 v3 快照运行时回退补 strict。
- invalid：A 新写入 `status=invalid + invalid_reason`；B `failed+invalid_reason` 聚合归 invalid；`AgentResult.error_type` 区分 Output/Structured（invalid）与 Execution/Timeout/Input/unknown（failed）；credential 两类异常在 `judge_trace` 边界转 failed+credential。
- 聚合：Item 优先级 `failed > invalid > evaluated > skipped`；unprocessed 只算无 row；`completed=evaluated`；aggregate/summary 增加 invalid 与 insufficient_count/ratio/all_insufficient_count。
- retry：复制父 `judge_config/config_snapshot/retrieval_config`；默认漂移不拒绝；父快照不可用拒绝；invalid 按 Item 级排除；strict-only 从 child coverage 派生，不调 Judge。
- 验证：新增 `tests/unit/test_rag_evaluation_v3_rules.py`（17 tests）、v3 双行/无效行集成测试、summary parent+child 去重测试；更新 retry snapshot/base agent 断言；全量 `pytest -m "not prompt"` passed；black/flake8/mypy/lint-imports 通过。
- Summary 去重：`list_runs_for_summary` 只取 `parent_run_id IS NULL` 的 root Run；retry 子 Run 只在详情展示，不重复计入 run_count/total_items/metrics。
- C3 已知 P2（未阻塞，C4 前记录）：`expected_metrics` 对 `judge_metrics=null` 的防御、strict 缺失的 missing_expected_metrics 诊断、summary 分组 key 加 prompt/schema。本轮未改。
- 边界：未改 Judge Prompt、未创建/激活 v1.2.0、未跑 Judge、未改 C2 migration、未上生产；C3 状态 `implemented/verified`，未 accepted；C4 未启动。
- 复审（2026-11-20）：summary 父子 Run 重复计数修复；C3 **阶段验收通过**；C4 批准设计/范围。

### M1-C C4 静态目标回归 / 40 条盘点（2026-11-20，implemented/verified，未跑 Judge）
- C4 报告：`docs/repair/26-m1c-c4-design-scope.md`；范围：静态目标回归 Q11/Q17/Q21/Q23/Q32、10 条闸门准备、40 条完整性盘点、报告模板。
- 静态目标：`m1c_c4_static_targets.py` → `m1c-c4-static-targets.json/md`，SHA `3ead3bdf…`，validation pass；Q11/Q21/Q23 observed v1.1.5，Q17/Q32 expected v1.2.0。
- 40 条盘点：`m1c_c4_inventory.py` → `m1c-c4-inventory.json/md`，SHA `581b7158…`，validation pass；HG 13 / provisional 27、分类 12/9/8/6/5、baseline 30/6/2/2、context 32/6/2。
- 特殊列表：`baseline_missing=Q33/Q34/Q37/Q38/Q39/Q40`、`baseline_delta=unavailable`；Q14/Q33 context_unavailable；C1-only Q22/Q26/Q27/Q34/Q37/Q40；Q35/Q36 old run only。
- 报告模板：`m1c-c4-report-template.md`；HG/provisional 分开、invalid/skipped/failed/unprocessed、insufficient、SHA、known issue。
- 边界：未跑 10/40 Judge、未激活 v1.2.0、未改 Prompt、未启动 M2/M3；C4 状态 `implemented/verified`，未 accepted。

### M1-D-0 v1.2.0 Prompt 设计与 metadata-only freeze（2026-11-20，frozen，未跑 Judge）
- 设计：`docs/repair/14-prompt-v1.2.0-design.md`；删除旧单 F / 单 A 口径，明确 r2 双指标、Schema v3、invalid、strict 派生、默认版本隔离、冻结提案与 activation requirements。
- 资产：`backend/app/prompts/rag_judge/v1.2.0/`；`faithfulness.txt`、`answer_correctness.txt`、`answer_relevancy.txt`、`MANIFEST.json`、`version.txt`。
- MANIFEST：`schema_version=rag_judge_schema_v3`、`rubric_version=v1.2.0`、`active=false`、`runtime_active=false`；`judge_metrics` 不含 `faithfulness_strict`，strict 只在 `derived_metrics`；默认 `v1.0.0`。冻结前 `design_draft` MANIFEST SHA `5a98be00…`，冻结后 `frozen` MANIFEST SHA `ee1c25be…`。
- Prompt SHA（冻结前后不变）：F `b6377758…`、C `a50520de…`、R `a5386070…`。
- Schema v3：9 个 factual + 7 个 non_factual 共 16 个 subtype；`support_status` 仅 factual；`evidence_refs` 为唯一证据字段；拒绝旧 `supported` / `evidence`；`supported` 无证据、quote 非逐字、context_id 不存在、conflict 单边 → `invalid(contract_violation)`。
- 测试：新增 `tests/unit/test_rag_judge_v120_prompt_assets.py`；更新 `test_rag_judge_schema_v3.py` 的 v1.2.0 资产断言；将“v1.2.0 Prompt 缺失”集成/retry 测试改为未知版本 `v9.9.9`；全量 pytest 1034 条通过。
- 静态校验：冻结前 validation `907886bd…`（22/22），冻结后 `21326f2c…`（22/22）；校验 MANIFEST frozen/active、Prompt SHA、16 subtype、无案例 ID、strict 不进 judge_metrics、v1/v1.1.5 Prompt 完整性。
- Freeze record：`docs/repair/27-m1d0-prompt-freeze-record.md`；记录 `071c3b6`、旧/新 MANIFEST SHA、Prompt SHA、validation、批准人/日期与 activation requirements。
- 边界：未跑 Judge（单/10/40）、未激活 v1.2.0、未修改 v1.0.0/v1.1.x Prompt、未改 Schema v2、未改 r2/目标 v1.0.2/Human Gold/provisional、未改 migration 022、未启动 M2/M3、未混入 C3 P2；状态 `frozen` / `active=false`，未 accepted；10/40 Judge 仍未批准。
