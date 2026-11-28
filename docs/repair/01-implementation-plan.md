# RAG 评测与优化平台 · 实施计划（Phase 0）

> 依据：`docs/repair/00-baseline.md` + 现有代码实测
> 原则：最小改动 / 复用优先 / 薄壳 / 数据可信 / 功能闭环 / 可验证 / 渐进
> **本文件只描述方案，不含代码改动；等待人工确认后再进入 Phase 1。**

---

## 1. 目标与非目标

### 1.1 本次要做（In Scope）

```
数据集（版本化）→ 调外部 RAG → 存 Trace → 算指标 → 出结果 → 失败归因 → 实验对比
```

| 模块 | 交付 |
|---|---|
| 数据集 | 数据集 / 版本 / 条目 / Gold Evidence / 导入导出 / split / 统计 |
| RAG 接入 | `RAGPort` 协议 + WeKnora 适配器（检索 + 问答两条能力）+ 重试/超时 + 原始响应留存 |
| Trace | 每次查询一行，含检索片段、答案、配置快照、耗时、状态、错误 |
| 指标 | 检索 4 项（HitRate@K / MRR@K / Context Recall / Context Precision）+ 回答 3 项（Faithfulness / Correctness / Relevancy） |
| 实验 | 实验定义 + 运行记录 + 同数据集版本对比 + 配置快照 |
| 失败分析 | 规则化归因（召回/上下文/生成）+ 失败筛选 + Trace 回放 |
| 前端 | 数据集、实验、Trace 三个页面（复用现有组件） |

### 1.2 本次不做（Out of Scope，明确写清避免范围膨胀）

| 不做 | 原因 |
|---|---|
| 自研 PDF/Word/OCR 解析、切片、向量库、BM25、Reranker | 由外部知识库（WeKnora）负责，本平台只评测 |
| 引入 `ragas` / `langchain` / 新向量库 | 现有 LLM Judge + httpx 足够；避免新增依赖与部署复杂度 |
| 多租户 / SSO / 组织权限 | 当前单团队使用，收益低 |
| Prompt DB 版本管理（启用 `prompt_versions`） | 文件版 + 版本号已够；死结构继续冻结 |
| 在线实时评测 / 流量 A/B | 离线批量评测已能满足优化闭环 |
| 改造现有「对话质量评估」链路 | 保留原能力，新增独立链路 |

---

## 2. 关键设计决策（附理由）

| # | 决策 | 理由 |
|---|---|---|
| D1 | **新增独立表**，不复用 `analysis_results` | 后者语义绑定 `cleaned_data`（`data_id` 无 FK），混用会让「对话评测」与「RAG 评测」互相污染 |
| D2 | 数据集版本**发布后不可变**，修改 = 新版本（copy-on-write） | 保证历史实验可复现；这是「可信」的底线 |
| D3 | Gold Evidence 与 contexts 都存**快照文本**（JSONB），不只存 ID | 外部文档会变；只存 ID 无法复现历史评测 |
| D4 | Adapter 用 `Protocol`（`app/ports/rag.py`），实现放 services 层，构造注入 | 与现有 `LLMPort`/`CredentialPort` 同构；不破坏 import-linter 契约 |
| D5 | 检索指标为**纯函数**（无 DB/无框架），放 `app/application/metrics.py` | 可表驱动单测，指标正确性可证明 |
| D6 | 回答类指标复用 `BaseAgent`（新增 `rag_judge_agent`） | 重试/降级/成本/结构化输出白拿；Judge 输出原文入库 |
| D7 | WeKnora 凭据复用 `user_llm_credentials`（`provider='weknora'`） | 已有加密/审计/校验；不新增表 |
| D8 | 一次评测 = 一个 Celery 任务（`rag_eval`），逐条写 trace + 指标 | 复用取消/重试/进度；单条失败不拖垮整批 |

---

## 3. 数据模型变更（迁移 019 / 020）

### 3.1 新增表（7 张）

```text
qa_datasets 1─n qa_dataset_versions 1─n qa_dataset_items
                                            │
rag_traces n─1 qa_dataset_items             │
     │ 1─1                                  │
rag_eval_results                            │
                                            │
experiments 1─n experiment_runs n─1 tasks ──┘
```

#### `qa_datasets`

| 列 | 类型 | 约束 |
|---|---|---|
| id | uuid | PK, `gen_random_uuid()` |
| user_id | uuid | FK `users.id` ON DELETE CASCADE |
| name | varchar(200) | NOT NULL |
| description | text | |
| source_type | varchar(20) | CHECK `in ('doc','conv','mixed')` |
| created_at / updated_at | timestamp | server default now() |

索引：`unique(user_id, name)`、`idx(user_id, created_at desc)`

#### `qa_dataset_versions`

| 列 | 类型 | 约束 |
|---|---|---|
| id | uuid | PK |
| dataset_id | uuid | FK CASCADE |
| version | int | NOT NULL |
| status | varchar(20) | CHECK `in ('draft','published','archived')` |
| item_count | int | default 0 |
| checksum | varchar(64) | 条目内容哈希（发布时计算，用于「是否被篡改」） |
| note | text | |
| published_at | timestamp | |
| created_at | timestamp | |

索引：`unique(dataset_id, version)`、`idx(dataset_id, status)`

#### `qa_dataset_items`

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK |
| version_id | uuid | FK CASCADE |
| item_key | varchar(80) | 稳定外部键（如 `CONV-10215`） |
| query | text | NOT NULL |
| gold_answer | text | 可为空（仅检索集） |
| gold_evidence | jsonb | `[{document_id, chunk_id, evidence_text, page_number, metadata}]`；**必须含 evidence_text** |
| category / difficulty / source | varchar | |
| split | varchar(10) | CHECK `in ('train','valid','test')`，默认 `test` |
| meta | jsonb | llm 评分、原始字段等 |
| created_at | timestamp | |

索引：`unique(version_id, item_key)`、`idx(version_id, split)`、`idx(version_id, category)`、GIN `idx(gold_evidence)`（可选）

#### `rag_traces`

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK users |
| dataset_item_id | uuid | FK `qa_dataset_items` ON DELETE SET NULL |
| task_id | uuid | FK tasks ON DELETE SET NULL |
| experiment_run_id | uuid | FK experiment_runs ON DELETE SET NULL |
| adapter | varchar(50) | `weknora` |
| external_session_id | varchar(100) | 外部会话/请求 ID |
| query / answer | text | |
| retrieved_contexts | jsonb | `[{document_id, chunk_id, content, score, rank, metadata, truncated}]` |
| raw_response | jsonb | 外部原始响应（排查用） |
| model_config / retrieval_config / prompt_snapshot | jsonb | 配置快照 |
| latency_ms | int | |
| token_usage | jsonb | 外部未提供则 `null` + `missing:["token_usage"]` |
| status | varchar(20) | `success` / `failed` |
| error_message | text | |
| created_at | timestamp | |

索引：`unique(task_id, dataset_item_id)`（幂等）、`idx(task_id, status)`、`idx(dataset_item_id)`

#### `rag_eval_results`

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK |
| trace_id | uuid | FK CASCADE, **unique** |
| task_id | uuid | FK tasks SET NULL |
| metrics | jsonb | `{hit_rate:{value,rank}, mrr:{value}, context_recall:{value,n_gold,n_hit}, context_precision:{value,mode}, faithfulness:{value,claims}, answer_correctness:{value,reason}, answer_relevancy:{value,reason}}` |
| judge_model / judge_prompt_version | varchar | |
| judge_raw | jsonb | Judge 原始输出（每个指标一条） |
| status | varchar(20) | `success` / `partial` / `failed` |
| error_message | text | |
| created_at | timestamp | |

索引：`idx(task_id)`、`idx(status)`

#### `experiments`

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK |
| name | varchar(200) | |
| hypothesis | text | 优化假设 |
| dataset_version_id | uuid | FK `qa_dataset_versions`（锁定版本） |
| adapter | varchar(50) | |
| config | jsonb | `{model_config, retrieval_config, prompt_snapshot, judge_config}` |
| metrics | text[] | 本次启用指标 |
| created_at | timestamp | |

#### `experiment_runs`

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK |
| experiment_id | uuid | FK CASCADE |
| task_id | uuid | FK tasks SET NULL |
| dataset_version_id | uuid | 冗余快照（防实验被改） |
| config_hash | varchar(64) | 配置 + 数据集版本哈希 |
| status | varchar(20) | `pending/running/completed/failed/cancelled` |
| aggregate | jsonb | 各指标均值 + n_evaluated + n_skipped |
| item_count | int | |
| started_at / completed_at | timestamp | |
| error_message | text | |

索引：`idx(experiment_id, created_at desc)`

### 3.2 迁移策略

- **只新增**，不改旧表（零停机风险）；
- 迁移 019：`qa_datasets / qa_dataset_versions / qa_dataset_items`；
- 迁移 020：`rag_traces / rag_eval_results / experiments / experiment_runs`；
- 全部 `create_table` + `create_index`；`downgrade` 按依赖反序 drop；
- 迁移前执行 `ops/backup/backup.sh`（发布流程已有）；
- `tests/integration/test_migrations.py` 已有迁移校验，扩展 `upgrade head → downgrade -1 → upgrade head`。

---

## 4. API 设计（17 个端点，前缀 `/api/v1`）

### 4.1 数据集

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/qa-datasets` | 新建数据集 |
| GET | `/qa-datasets` | 分页 + 关键词 |
| GET | `/qa-datasets/{id}` | 详情（含版本列表与统计） |
| PATCH | `/qa-datasets/{id}` | 改名/描述（不影响已发布版本） |
| POST | `/qa-datasets/{id}/versions` | 创建 draft 版本（可 `from_version_id` 复制） |
| POST | `/qa-datasets/{id}/versions/{vid}/import` | 导入条目（JSON 数组或 CSV），整批事务 + 逐条错误报告 |
| POST | `/qa-datasets/{id}/versions/{vid}/publish` | 发布（校验 → 计算 checksum → 置 published） |
| GET | `/qa-datasets/{id}/versions/{vid}/items` | 条目列表（split/category/关键词） |
| PATCH | `/qa-datasets/{id}/versions/{vid}/items/{iid}` | 仅 draft 可改 |
| DELETE | `/qa-datasets/{id}/versions/{vid}/items/{iid}` | 仅 draft 可删 |
| GET | `/qa-datasets/{id}/stats` | 条目数、split 分布、类型分布、证据覆盖率 |

**导入契约**（JSON）：

```json
{
  "items": [
    {
      "item_key": "CONV-10215",
      "query": "我有针对SKU配置的话术，为什么没有触发？",
      "gold_answer": "……",
      "gold_evidence": [
        {"document_id": "M5ZT…", "chunk_id": "6364b00f…", "evidence_text": "……", "page_number": null, "metadata": {}}
      ],
      "category": "关键词/话术配置",
      "difficulty": "medium",
      "source": "conv:knowledge",
      "split": "test",
      "meta": {"session_id": "10215"}
    }
  ]
}
```

导入规则：
- `item_key` 必填且批内唯一；
- `query` 必填；
- `gold_evidence` 每项**必须**有 `evidence_text`（≥10 字）；仅有 `document_id` 的记录**拒收**并列入 `errors[]`；
- `split` 缺省 `test`；非法值 → 400；
- 整批事务：**全部成功或全部回滚**（`errors[]` 返回行号+原因）。

### 4.2 评测与 Trace

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/rag/evaluations` | 创建评测（`dataset_version_id`、`adapter`、`config`、`metrics[]`、`limit`）→ 202 `task_id` |
| GET | `/rag/evaluations/{task_id}` | 任务状态 + 聚合指标 + 跳过统计 |
| GET | `/rag/evaluations/{task_id}/failures` | 按指标阈值筛失败（`metric=context_recall&below=0.5`） |
| GET | `/rag/traces` | 列表（task_id/status/only_failed/page） |
| GET | `/rag/traces/{trace_id}` | 详情（检索上下文、答案、Gold、指标、Judge 原文） |

### 4.3 实验

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/rag/experiments` | 创建实验（锁数据集版本 + 配置） |
| GET | `/rag/experiments` | 列表 |
| GET | `/rag/experiments/{id}` | 详情 + 运行记录 |
| POST | `/rag/experiments/{id}/runs` | 触发一次运行 → 202 `task_id` |
| GET | `/rag/experiments/{id}/compare?base_run=&target_run=` | 对比（指标差值 + 兼容性警告） |

对比接口必须返回 `comparable: true/false`：数据集版本、样本数、Judge 配置任一不同 → `false` + `reasons[]`。

---

## 5. 指标定义（必须精确到公式与边界）

> 所有指标返回统一结构：`{value, n_evaluated, n_skipped, skipped_reason}`；**禁止把「无法计算」静默成 0 分**。

### 5.1 证据匹配规则（先定义，再算指标）

```text
match(gold, retrieved) =
  1) chunk_id 双方都非空 → 比较 chunk_id（严格）
  2) 否则 document_id 双方都非空 → 比较 document_id
  3) 否则 evidence_text 归一化（去空白/标点、小写）后做包含判断（长度 ≥ 10）
命中模式写进结果：mode = chunk | document | text
```

不使用相似度分数判命中（外部不返回分数，且「相似 ≠ 证据」）。

### 5.2 检索指标

| 指标 | 公式 | 分母 | 边界 |
|---|---|---|---|
| **HitRate@K** | `命中至少 1 条 gold 的样本数 / 有 gold_evidence 的样本数` | 仅「有证据」样本 | 无证据样本计入 `skipped` |
| **MRR@K** | `mean(1 / rank_first_hit)`，未命中 = 0 | 同上 | K 缺省 5 |
| **Context Recall** | `|retrieved_gold| / |gold|`（按 gold 条目去重） | 同上 | 无 gold → null |
| **Context Precision** | 默认 `|retrieved_gold| / |retrieved|`（id 模式，不看位置） | 检索片段数 > 0 的样本 | 另提供 `ap@k` 模式（rank-aware），报告必须标注 `mode` |

### 5.3 回答指标（LLM Judge，复用 BaseAgent）

| 指标 | 输出结构 | 说明 |
|---|---|---|
| **Faithfulness** | `{claims:[{claim, supported, evidence[], reason}], score=supported/total}` | claim 拆分；无 claims → `null` + skip |
| **Answer Correctness** | `{score 0-1, missing[], wrong[], reason}` | 对齐 gold_answer |
| **Answer Relevancy** | `{score 0-1, reason}` | 是否切题（不评事实） |

Judge 落库三件套：`judge_model`、`judge_prompt_version`（读 `app/prompts/rag_judge/version.txt`）、`judge_raw`（原始 JSON）。

### 5.4 归因规则（只作线索，不自动改配置）

| 条件 | 归因 | 建议动作 |
|---|---|---|
| `context_recall < 0.5` 且 `faithfulness ≥ 0.7` | 检索漏召回 | 调 top_k / 切片 / query |
| `context_recall ≥ 0.5` 且 `faithfulness < 0.5` | 生成幻觉 | 检查 prompt / 模型 |
| `recall ≥ 0.5` 且 `correctness < 0.5` | 证据冲突或推理错误 | 人工复核证据 |
| `context_precision < 0.5` 且 `recall ≥ 0.5` | 上下文噪声 | 调阈值 / rerank |
| 检索指标正常、回答指标低 | 生成阶段 | 优先查生成 |

---

## 6. 任务与幂等设计

| 项 | 设计 |
|---|---|
| 新任务类型 | `rag_eval`（一次评测 / 一次实验运行共用） |
| 入队 | 只在 `app/composition/enqueue.py: enqueue_rag_eval`；`executors` 注册 `rag_eval` |
| 幂等 | `rag_traces` 唯一 `(task_id, dataset_item_id)`；重复执行 `ON CONFLICT DO NOTHING` 后跳过已完成条目 |
| 断点续跑 | 任务失败重试时，已成功的 trace 不重复调用外部 RAG（省成本） |
| 进度 | 每 N 条 commit 一次（沿用 2026-11-13 的 `PROGRESS_COMMIT_EVERY` 经验） |
| 失败粒度 | 单条 trace 失败只标记该条 `failed`，不中断整批；聚合时计入 `n_skipped` |
| 取消 | 每条前检查 `task_control.is_cancelled`（复用现有实现） |
| 重试 | 复用 `task_service.retry`；`rag_eval` 注册到 `executors` 才能重试 |

---

## 7. 代码结构与文件清单

### 7.1 新增（后端）

```
app/models/qa_dataset.py          # QaDataset / QaDatasetVersion / QaDatasetItem
app/models/rag.py                 # RagTrace / RagEvalResult
app/models/experiment.py          # Experiment / ExperimentRun
app/repositories/qa_dataset.py
app/repositories/rag_trace.py
app/repositories/rag_eval.py
app/repositories/experiment.py
app/schemas/qa_dataset.py
app/schemas/rag.py
app/schemas/experiment.py
app/ports/rag.py                  # RAGPort Protocol（query / retrieve）
app/services/qa_dataset_service.py
app/services/rag/__init__.py
app/services/rag/weknora.py       # WeKnoraAdapter（httpx，SSE 解析，重试）
app/services/rag/execute.py       # 单条执行：调 adapter → 存 trace
app/services/rag/evaluation.py    # 编排：遍历条目 → trace → 指标 → 聚合
app/services/experiment_service.py
app/application/metrics.py        # 纯函数：hit_rate/mrr/context_recall/context_precision
app/agents/rag_judge_agent.py
app/prompts/rag_judge/{system.txt,version.txt,dimensions/{faithfulness,correctness,relevancy}.txt}
app/api/v1/qa_datasets.py
app/api/v1/rag.py
app/api/v1/experiments.py
app/tasks/rag.py
migrations/versions/019_qa_datasets.py
migrations/versions/020_rag_trace_experiment.py
```

### 7.2 修改（后端）

| 文件 | 改动 | 影响面 |
|---|---|---|
| `app/models/__init__.py` | 导出 7 个新模型 | 无 |
| `app/schemas/task.py` | `TaskType` 增加 `rag_eval` | 任务校验 |
| `app/composition/enqueue.py` | 新增 `enqueue_rag_eval` | 无 |
| `app/composition/executors.py` | 注册 `rag_eval` | 重试能力 |
| `app/tasks/__init__.py` | 注册 `tasks.rag_eval` | worker 需重启 |
| `app/api/v1/__init__.py` | include 3 个新 router | 无 |
| `app/core/config.py` | `WEKNORA_BASE_URL / DEFAULT_KB_ID / TENANT_ID / TIMEOUT / MAX_RETRIES` | 新增配置项 |
| `app/services/credential_service.py` | `PROVIDER_WEKNORA` + `_resource_type` 分支 + base_url SSRF 校验 | **改动现有文件，需回归** |
| `tests/unit/test_celery.py` | 任务名清单加 `tasks.rag_eval` | 防漏注册 |

### 7.3 新增（前端）

```
src/api/qaDatasets.js / rag.js / experiments.js
src/hooks/useQaDatasets.js / useRag.js / useExperiments.js
src/pages/QaDatasets/{index.jsx,Detail.jsx}
src/pages/RagEvaluation/{index.jsx,TraceDetail.jsx}
src/pages/Experiments/{index.jsx,Compare.jsx}
```

路由与侧边栏：在现有 8 个页面后追加 3 项（复用 `PageHeader`/`Table`/`Drawer`/`AsyncState`）。

---

## 8. 分阶段实施与验收

### Phase 1 · 数据基础（P0）

**改动**：迁移 019 + 3 个 model/repo/schema/service + 数据集 API + 导入校验 + 测试。

**验收**
1. 创建数据集 → 创建 draft → 导入 10 条（含证据）→ 查询详情；
2. 发布版本后 PATCH 条目返回 409（不可变）；
3. 导入缺 `evidence_text` 的记录 → 400 且整批回滚，`errors[]` 指出行号；
4. 从 v1 复制生成 v2，修改 v2 不影响 v1 的 item 内容与 checksum；
5. 单测覆盖：校验规则、checksum、copy-on-write、split 统计。

### Phase 2 · Adapter 与 Trace（P0）

**改动**：`RAGPort`、`WeKnoraAdapter`（`query` + `retrieve`）、trace 持久化、trace API、Mock 契约测试。

**验收**
1. Mock 服务：返回 JSON / SSE 两种响应，Adapter 均能解析出 `answer` + `contexts`；
2. 外部 500/429/超时 → 重试 ≤3 次 → trace `status=failed` + `error_message`；
3. 外部缺 `score`/`token_usage` → 入库 `null` 且 `missing[]` 标注，不伪造；
4. Trace 详情能回答：检索到哪些 chunk、Gold 是否召回、用了什么配置、耗时多少；
5. **真实联调**：有凭据则跑通 1 条并记录；无凭据则明确标注「未完成真实联调」。

### Phase 3 · 评测引擎（P0）

**改动**：`application/metrics.py`、`rag_judge_agent`、`rag_eval` 任务、评测 API、聚合。

**验收**
1. 表驱动单测：HitRate/MRR/ContextRecall/ContextPrecision 各 ≥6 个用例（含全命中/全不中/空证据/重复证据/K 截断）；
2. Faithfulness claim 级输出入库，可展开到「哪条主张无依据」；
3. 一次评测 20 条：聚合返回 `value/n_evaluated/n_skipped`，无证据样本计入 skipped 而非 0 分；
4. 单条失败不影响整批；重试不重复调用已成功条目；
5. 结果可追到 `trace_id → item_id → dataset_version_id`。

### Phase 4 · 实验与对比（P1）

**改动**：experiments/runs、配置快照、compare API。

**验收**
1. 同数据集版本创建两个实验（不同 top_k），各跑一次；
2. compare 返回指标差值 + `comparable=true`；
3. 数据集版本不同时 `comparable=false` + `reasons`；
4. 实验配置快照可回读，能复现同一次运行（同 config_hash）。

### Phase 5 · 失败分析与闭环（P1）

**改动**：归因规则、失败筛选 API、前端失败列表与 Trace 回放。

**验收**：完整走通「低分 → Trace → 证据是否召回 → 归因 → 改配置 → 新实验 → 对比」。

### Phase 6 · 前端与完善（P1/P2）

**验收**：3 个页面真实调 API（无假数据）；加载/空/错误态齐全；前端覆盖率不回退到阈值以下（80/70/80）；原有 8 个页面功能不回归。

---

## 9. 测试计划

| 层级 | 内容 | 命令 |
|---|---|---|
| 单元 | 指标纯函数（表驱动）、导入校验、checksum、Adapter 映射（含 SSE）、配置哈希 | `pytest tests/unit -q` |
| 集成 | 数据集 CRUD/发布/不可变、评测任务（fake adapter + fake judge）、实验对比 | `pytest tests/integration -q` |
| 迁移 | `upgrade head → downgrade 019 → upgrade head` | `pytest tests/integration/test_migrations.py` |
| 回归 | 全量（现有 711 条不得减少） | `pytest -m "not prompt"` |
| 分层 | import-linter 5 条契约 | `lint-imports` |
| 前端 | 组件测试 + 覆盖率阈值 | `npm run test:coverage` |
| E2E（可选） | 一条真实 WeKnora 查询（有凭据时） | 手工脚本，不纳入 CI |

---

## 10. 风险与回滚

| 风险 | 触发条件 | 回滚 |
|---|---|---|
| 新增表影响迁移 | `alembic upgrade head` 失败 | `alembic downgrade -1`（只删新表，不动旧表） |
| 信用凭据复用改动破坏 BYOK | `credential_service` 分支写错 | 该文件改动独立提交，可单独 revert；回归 `tests/unit/test_credential_encryption.py` |
| 新任务类型未注册 | worker 拒收 | 已加「任务名必须已注册」断言 |
| 外部 RAG 不稳定 | 429/超时 | 重试 + 单条失败隔离 + trace 记录错误 |
| 评测成本失控 | 459 条 × 2 次外部调用 | `limit` 参数 + 先跑 test split 抽样 + 成本表可查 |

---

## 11. 待人工确认（阻塞 Phase 1 之后）

| # | 问题 | 建议默认值 |
|---|---|---|
| Q1 | WeKnora 的 `BASE_URL / API_KEY / AGENT_ID / KB_ID / TENANT_ID` 由谁提供 | 走凭据表 + 环境变量，不入库明文 |
| Q2 | 评测走「纯检索」还是「智能体问答」 | 默认两者都支持：检索指标走 hybrid-search，回答指标走 agent-chat |
| Q3 | 459 条是否拆两个数据集 | 建议按 `doc`（222）/ `conv`（237）拆分，指标分开统计 |
| Q4 | Gold Evidence 粒度 | 文档类用 `document_id`（现有）；对话类先按 `evidence_text` 缺失处理为 skipped，后续补映射 |
| Q5 | 是否允许把 459 条 JSON 复制进仓库做 fixture | 建议只复制脱敏后的 20 条做测试 fixture，全量通过导入接口进库 |
| Q6 | 指标是否需要显著性检验 | Phase 4 先不给，只给差值与样本量 |

---

## 12. 实施顺序（确认后执行）

```
Phase 1 数据集（迁移 019）→ 验收
Phase 2 Adapter + Trace（迁移 020）→ Mock 验收（真实联调视 Q1）
Phase 3 指标 + 评测任务 → 验收
Phase 4 实验对比 → 验收
Phase 5 失败归因 + 回放 → 验收
Phase 6 前端三页 → 验收
```

每个 Phase 结束提交：改动文件、迁移版本、测试结果、遗留问题；**测试未过不标记完成**。
