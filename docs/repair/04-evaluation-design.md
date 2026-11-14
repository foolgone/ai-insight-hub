# 评测引擎设计（Phase 3）

> 范围：Phase 3A 确定性检索指标（已实现）、3B LLM Judge（已实现）、3C 持久化与批量任务（已实现）、3D 真实 WeKnora 联调（本地 VM 已完成）。
> 前置：Phase 1 数据集（`qa_dataset_items.gold_evidence`）、Phase 2 Trace（`rag_traces.context_source/retrieved_contexts`）。

---

## 1. 设计约束

| 约束 | 落地 |
|---|---|
| 指标纯函数 | `app/application/metrics.py` 只依赖标准库；不碰 DB / LLM / 网络 |
| 不引入 ragas / langchain | 自研指标 + 复用 `BaseAgent` |
| skipped ≠ 0 | 无 Gold Evidence / 无上下文 → `status=skipped`，聚合不计入均值 |
| 文档级与 Chunk 级不混 | 匹配严格按 Gold 的粒度；gold 有 `chunk_id` 时只比 `chunk_id` |
| 两种执行模式分开统计 | `hit_rate` 等只在 `mode=retrieve` 有意义；回答指标只在 `mode=query` |
| 历史结果不覆盖 | 每条结果记录 `metric_version` + `judge_config`；重新评测产生新行 |

---

## 2. Phase 3A：确定性指标

### 2.1 输入结构

```python
@dataclass(frozen=True)
class EvidenceRef:          # Gold Evidence（来自 qa_dataset_items.gold_evidence）
    document_id: str | None
    chunk_id: str | None
    text: str | None

@dataclass(frozen=True)
class RetrievedItem:        # 来自 rag_traces.retrieved_contexts
    document_id: str | None
    chunk_id: str | None
    content: str
    rank: int | None = None  # 缺省用列表下标 +1
```

### 2.2 输出结构（统一）

```python
@dataclass(frozen=True)
class MetricResult:
    metric_name: str          # hit_rate / mrr / context_recall / context_precision_at_k / context_precision_ap_at_k
    value: float | None       # skipped 时为 None（不是 0）
    status: str               # evaluated / skipped / failed
    n_evaluated: int          # 0 或 1（单样本）
    n_skipped: int
    skipped_reason: str | None
    details: dict             # k、命中依据、逐条证据、rank 等
```

### 2.3 Evidence 匹配规则

Gold 证据的粒度由字段决定，**优先级不可混用**：

| Gold 粒度 | 判定 | 依据字段 |
|---|---|---|
| chunk 级（有 `chunk_id`） | 仅比较 `chunk_id` 相等 | `chunk_id` |
| 文档级（无 `chunk_id`、有 `document_id`） | 比较 `document_id` 相等（该文档任意 chunk 都算命中） | `document_id` |
| 文本级（只有 `evidence_text`） | 规范化后**完全相等** | `text` |

- 有 `chunk_id` 的 Gold **不会**因为同文档其它 chunk 命中而算命中（避免把文档级命中冒充 chunk 级）；
- 文本规范化：`NFKC` → `casefold` → 去空白 → 去中英文标点；**不做包含/相似度匹配**（宁缺毋滥）；
- 不采用 embedding 相似度判定（外部无稳定分数，且相似≠证据）。

### 2.4 指标公式

记：`R` = 去重后的检索结果（保持首次出现顺序，按 `chunk_id → document_id → 规范化文本` 取身份）；`G` = 去重后的 Gold Evidence；`K` = Top-K。

| 指标 | 公式 | 分母/边界 |
|---|---|---|
| **HitRate@K** | `1` if 存在 `g∈G, r∈R[:K]` 匹配，否则 `0` | `G=∅` → skipped(`gold_evidence_missing`)；`R=∅` → evaluated 0 |
| **MRR@K** | `1 / rank(first match)`；无命中 → `0` | 同上；rank 从 1 开始 |
| **Context Recall** | `|{g ∈ G : ∃r ∈ R 匹配}| / |G|` | `G=∅` → skipped；`R=∅` → evaluated 0 |
| **Context Precision@K** | `|{r ∈ R[:K] : r 匹配任一 g}| / |R[:K]|` | `R=∅` → skipped(`no_retrieved_contexts`)；`G=∅` → skipped |
| **Context Precision (AP@K)** | `(1/min(|G|,K)) · Σ_{i=1..K} P@i · rel_i` | 同上；`rel_i` 指第 i 条是否相关 |

> **Precision@K 的分母是「实际返回且去重后」的条数，不是固定 K。**
> 即它表达的是「这次返回的结果里有多大比例相关」；当返回数 < K 时，分母取返回数。
> 因此不同查询之间若返回条数差异很大，该指标不宜直接横向比较（需要时用 AP@K，或后续新增固定 K 版本）。
> 代码与测试锁定：`test_context_precision_denominator_is_actual_returned_count`。

> 两个 Precision 变体使用**不同 metric_name**（`context_precision_at_k` / `context_precision_ap_at_k`），
> `details.mode` 再次标注，禁止只写 `context_precision`。

### 2.5 边界与状态

| 场景 | 行为 |
|---|---|
| Gold 为空 | hit/mrr/recall/precision 全部 `skipped`，reason=`gold_evidence_missing` |
| 检索为空 | hit/mrr/recall `evaluated=0`；precision `skipped`（分母 0） |
| 重复检索 | 按身份去重，保留首次 rank（避免用重复项抬高 Precision 分母） |
| 重复 Gold | 按粒度+值去重 |
| K ≤ 0 | `ValueError`（编程错误，不是数据问题） |
| 运行期异常 | 3C 捕获后写 `status=failed`，错误信息入结果 |

### 2.6 去重与截断顺序（审核补充）

- **去重身份**（优先级从高到低）：`chunk_id` → `document_id` → 规范化文本；
- 同一 `document_id` 下的**不同** `chunk_id` 是两条不同结果，**不得合并**；
  只有 `chunk_id` 相同（或都无 chunk 且 `document_id` 相同）才去重；
- 顺序：**先去重，再按 K 截断**（重复结果不占用 Top-K 名额）；
- 保留首次出现的排名（若传了 `rank` 则按 rank 排序后再处理）；
- 测试锁定：`test_same_document_different_chunks_are_not_merged`、
  `test_dedupe_happens_before_k_truncation`、`test_duplicate_retrieved_keeps_first_rank`。

---

## 3. Phase 3B：LLM Judge（已实现）

### 3.1 复用与边界

- 复用 `BaseAgent`（重试/超时/降级/结构化输出/一次修复/成本记账）与 `LLMClient`；
- 新增 `app/agents/rag_judge_agent.py`、`app/schemas/agents/rag_judge.py`、`app/prompts/rag_judge/`；
- **不引入** ragas / langchain / 新 Agent 框架；
- 3B **不新建表、不做批量调度**：Judge 结果以结构化对象返回（含全部追溯字段），
  持久化与聚合在 3C 落库；`llm_calls` 继续由 `BaseAgent` 自动记账。

### 3.2 Agent 设计

一个 `RagJudgeAgent`，按 `metric` 选择 Prompt 与输出 Schema（避免三套重复类）：

```python
class RagJudgeAgent(BaseAgent):
    def __init__(self, metric: Literal["faithfulness", "answer_correctness", "answer_relevancy"], *, llm=None): ...
    # output_schema = 该指标的 Pydantic 输出模型（实例上覆盖类属性）
    # _load_prompt() 读 app/prompts/rag_judge/{metric}.txt
    async def judge(self, input_data, **kwargs) -> AgentResult
```

输入（统一 `RagJudgeInput`）：

| 指标 | 必填字段 |
|---|---|
| faithfulness | `query`、`answer`、`contexts[]`（来自本次 Trace，`context_source="agent_chat"`） |
| answer_correctness | `query`、`answer`、`gold_answer` |
| answer_relevancy | `query`、`answer` |

输出（Pydantic，结构化校验，解析失败由 `BaseAgent` 修复轮处理，仍失败则 `success=False`）：

```json
// faithfulness
{"claims": [{"claim": "...", "supported": true, "evidence": ["片段…"], "reason": "..."}], "reason": "..."}
// answer_correctness
{"score": 0.0, "missing_points": ["..."], "wrong_facts": ["..."], "reason": "..."}
// answer_relevancy
{"score": 0.0, "reason": "..."}
```

> Faithfulness 的 `score` **由代码计算**（`supported / total`），不信任模型自报总分；
> 无 claims 时 score=`null` 且状态 skipped（`no_claims`），不计入均值。

### 3.3 跳过规则（调用 Judge 之前判定）

| 指标 | 条件 | 结果 |
|---|---|---|
| 全部 | `trace.status != "success"` | skipped(`trace_failed`) |
| faithfulness | `context_source != "agent_chat"` 或 `contexts=[]` | skipped(`context_unavailable`)，**不调用模型** |
| answer_correctness | `gold_answer` 为空 | skipped(`gold_answer_missing`) |
| answer_correctness | `answer` 为空 | skipped(`answer_missing`) |
| answer_relevancy | `answer` 为空 | skipped(`answer_missing`) |
| 任意 | 模型调用失败/超时/结构非法（修复后仍失败） | failed + `error_message` |

**硬约束**：Faithfulness 只用本次 Trace 的真实上下文；独立 `retrieve` 的上下文不参与，
`context_available=false` 的 Trace 一律 skip。

### 3.4 Prompt 与版本管理

```
app/prompts/rag_judge/
  version.txt                 # 例如 2026-11-14.1
  faithfulness.txt
  answer_correctness.txt
  answer_relevancy.txt
```

- `prompt_version` 读 `version.txt`；`prompt_sha256` 由实际 Prompt 文本计算（防止「改了文件但忘改版本号」）；
- `metric_version` 为代码常量（`RAG_JUDGE_METRIC_VERSION = {"faithfulness": "v1", ...}`）；
- 每条结果记录 `judge_config = {model, temperature, max_tokens, prompt_version, prompt_sha256, metric_version}`；
- 同一 Trace 可用不同版本重新评测：3C 以
  `unique(run_id, dataset_item_id, metric_name, metric_version)` + `judge_config` 保存多行，不覆盖历史。

### 3.5 结果结构（3B 返回，3C 落库）

```python
@dataclass(frozen=True)
class JudgeOutcome:
    metric_name: str
    metric_version: str
    status: Literal["evaluated", "skipped", "failed"]
    score: float | None
    skipped_reason: str | None
    details: dict          # claims / missing_points / wrong_facts / reason
    judge_config: dict     # 见 3.4
    raw_output: str | None # 模型原始文本（BaseAgent 增加可选 raw_text）
    latency_ms: int
    error_message: str | None
```

> 为保存「原始模型输出」，`AgentResult` 增加可选 `raw_text`（默认 `None`，其它 Agent 行为不变）。

### 3.6 服务编排

`app/services/rag_judge_service.py`：

```python
async def judge_trace(session, *, trace: RagTrace, item: QaDatasetItem | None,
                      metrics: Sequence[str], llm=None) -> list[JudgeOutcome]
```

- 逐指标：先走跳过规则（不调用模型）→ 再调 Agent；
- 单个指标失败不影响其它指标，也不修改 Trace / 检索指标；
- `session` 透传给 `BaseAgent` 以写 `llm_calls`（成本可查）；
- 不做数据库写入（3C 负责）。

### 3.8 实现落点（已完成）

| 组件 | 文件 |
|---|---|
| Schema | `app/schemas/agents/rag_judge.py` |
| Agent | `app/agents/rag_judge_agent.py` |
| Prompt | `app/prompts/rag_judge/{faithfulness,answer_correctness,answer_relevancy}.txt` + `version.txt` |
| 编排 | `app/services/rag_judge_service.py` |
| 基座改动 | `AgentResult.raw_text`（默认 None）+ `parse_with_repair(raw_sink=...)` |
| 测试 | `tests/unit/test_rag_judge_agent.py`（10）、`tests/unit/test_rag_judge_service.py`（12）、`tests/integration/test_rag_judge_integration.py`（2） |

保护阈值：上下文最多 20 条 / 每条 6,000 字符；原始输出 20,000 字符截断并标 `raw_truncated`。
### 3.7 测试计划（全部 Mock LLM，无真实 API）

| 指标 | 用例 |
|---|---|
| Faithfulness | 全支持 / 部分支持 / 无 claims（skipped）/ 无上下文（不调用模型）/ `context_available=false` / 非法 JSON / 超时 / 少字段 |
| Correctness | 全对 / 部分对 / 全错 / 缺 gold（skipped）/ 调用失败 |
| Relevancy | 高相关 / 低相关 / 空答案（skipped）/ 调用失败 |
| 追溯 | prompt_version 与 sha256、model 名称、原始输出、不同版本重复评测不覆盖（3C 断言） |

---
## 4. Phase 3C：持久化与批量执行（设计，待实施）

### 4.1 实施前审计结论（针对任务书 8 问）

| # | 问题 | 代码事实 | 结论 / 处理 |
|---|---|---|---|
| 1 | Faithfulness 的 evidence 是否对应真实输入上下文 | 3B 只把 contexts 传给模型，**服务层未校验** evidence 是否为上下文原文 | 3C 落库时计算 `details.evidence_verified`（规范化子串匹配），**不修改分数**；未命中计数用于复盘 |
| 2 | Judge 原始输出是否够复盘 | `AgentResult.raw_text` 存最终解析文本；服务层 20k 截断 + `raw_truncated` | 够用；超长输出只保留前 20k（可后续迁对象存储） |
| 3 | Run 配置能否完整重现 | 3B 的 `judge_config` 含 model/temperature/max_tokens/prompt_version/prompt_sha256/metric_version；Trace 存 retrieval/model/prompt 快照 | 可重现；**缺代码版本与随机种子**（LLM 客户端无 seed），文档标注为已知限制 |
| 4 | Celery 重复投递 / worker 崩溃 | `task_acks_late=False`（仅 clean 单任务开启）；`prefetch=1`；visibility 3600s；time_limit 1800s；concurrency=2 | 3C 任务单独 `acks_late=True`；用 **advisory lock + 唯一键 + 心跳** 防重复/识别崩溃 |
| 5 | 单条失败会不会回滚整批 | 当前 worker 每个任务一个 session | 3C 改为**每条样本 savepoint + 逐条 commit**，失败只回滚该条 |
| 6 | 数据集发布后会不会被改 | Phase 1 已实现发布后不可变（409）+ checksum | Run 固定 `dataset_version_id` 并保存 checksum；执行前比对，不一致 → failed(`dataset_modified`) |
| 7 | 每条样本是否要独立 Trace | `rag_traces` 有 `idempotency_key` 唯一键、`dataset_item_id`/`task_id` | 每次 Run 为每条样本创建独立 Trace；**重试复用父 Run 的成功 Trace**（键可推导） |
| 8 | WeKnora 最小联调验收 | 外部接口契约已在 Phase 2 实现（retrieve/query + SSE 解析） | 有凭据后：1 条 retrieve + 1 条 query，核对 contexts/context_source/延迟，并与外部文档级基线（MRR≈0.70）做 sanity check |

其他审计事实：

- 生产库 head = `9a4d2f8c6e15`（018），**尚无 rag 表**；开发库 head = `c9d2a4f7b1e6`（020）；
  上线时必须按 019 → 020 → 021 顺序执行。
- `tasks.task_type` CHECK 只有 6 种，**不含 `rag_eval`**；`tasks.status` CHECK 只有
  `pending/running/completed/failed/cancelled`（**无 partial_failed**）。
- 连接池 `pool_size=20 / max_overflow=40`；worker 与 API 共享数据库。

### 4.2 数据模型（迁移 021）

```
tasks 1─1 rag_evaluation_runs
qa_datasets 1─n runs        （保存 dataset_name 快照）
qa_dataset_versions 1─n runs（FK RESTRICT，历史可复现）
runs 1─n runs               （parent_run_id，重试血缘）
runs 1─n rag_evaluation_results
qa_dataset_items 1─n results（FK RESTRICT）
rag_traces 1─n results      （FK SET NULL）
```

#### `rag_evaluation_runs`

| 列 | 类型 | 约束/说明 |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK users CASCADE |
| task_id | uuid | FK tasks SET NULL, **UNIQUE**（1 run : 1 task） |
| parent_run_id | uuid | FK self SET NULL（重试来源） |
| attempt | int | 默认 1；子 Run = 父 + 1 |
| retry_scope | varchar(20) | CHECK `all` / `failed_only` |
| dataset_id | uuid | FK qa_datasets SET NULL |
| dataset_name | varchar(200) | 快照（防数据集改名影响历史阅读） |
| dataset_version_id | uuid | FK qa_dataset_versions **RESTRICT** |
| dataset_checksum | varchar(64) | 创建时快照，执行前校验 |
| execution_mode | varchar(20) | CHECK `retrieve` / `query` |
| adapter | varchar(50) | `mock` / `weknora` |
| retrieval_config | jsonb | top_k / thresholds / precision_mode |
| judge_config | jsonb | 模型、温度、Prompt 版本/SHA、metric_versions |
| config_snapshot | jsonb | 完整快照（含 metric 清单、split、limit） |
| item_selection | jsonb | `{mode, item_ids}`（failed_only 时记录实际选中项） |
| total_items / completed_items / skipped_items / failed_items | int | 条目级计数（不是指标级） |
| status | varchar(20) | CHECK 见 4.3 |
| aggregate | jsonb | 聚合结果（见 4.6） |
| error_message | text | |
| started_at / completed_at / last_heartbeat_at / created_at | timestamp | 心跳用于识别 worker 崩溃 |

索引：`(user_id, created_at desc)`、`(dataset_version_id)`、`(status)`、`(parent_run_id)`、`task_id` 唯一。

#### `rag_evaluation_results`

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid | PK |
| run_id | uuid | FK runs CASCADE |
| dataset_item_id | uuid | FK items **RESTRICT** |
| trace_id | uuid | FK rag_traces SET NULL |
| metric_name | varchar(40) | `hit_rate` / `mrr` / `context_recall` / `context_precision_at_k` / `context_precision_ap_at_k` / `faithfulness` / `answer_correctness` / `answer_relevancy` |
| metric_version | varchar(20) | 与 metric_name 配套 |
| status | varchar(20) | CHECK `evaluated` / `skipped` / `failed` |
| score | double precision | 仅 evaluated 有值；skipped/failed 为 NULL |
| skipped_reason | varchar(60) | `gold_evidence_missing` / `context_unavailable` / `no_claims` / ... |
| details | jsonb | rank、claims、missing_points、`evidence_verified` 等 |
| judge_config | jsonb | 冗余快照（结果可独立追溯） |
| raw_output | text | 模型原始输出（≤20k） |
| raw_truncated | bool | |
| latency_ms | int | |
| error_message | text | |
| created_at | timestamp | |

**唯一键**：`unique(run_id, dataset_item_id, metric_name, metric_version)`。

> 成立前提：**一个 Run 的 Judge 配置固定**（同一模型 / Prompt 版本 / metric 版本）。
> API 创建 Run 时固化 config，执行时禁止逐条覆盖；不同配置必须新建 Run，因此不会出现
> 「同一 Run 同一指标同一样本两套配置」的冲突。

索引：`(run_id, metric_name, status)`、`(run_id, status)`、`(trace_id)`。

### 4.3 状态机

#### Run

```
pending ──启动──> running ──全部条目处理完──> completed
                    │                         └─> partial_failed（存在 failed 结果）
                    ├─全部条目失败─────────────> failed
                    ├─用户取消─────────────────> cancelled
                    └─心跳超时（recover 任务）──> failed(stale)
```

| 结束条件 | run.status |
|---|---|
| 无 failed 结果（skipped 不算失败） | completed |
| 至少一条 failed 结果，且存在非 failed | partial_failed |
| 所有预期结果都 failed（条目 × 指标全失败） | failed |
| 取消 | cancelled |
| 心跳超时 | failed（error=`stale_worker`） |

> 判定按**结果粒度**：`failed_results >= len(expected_metrics) × total_items` 才是 `failed`；
> 只要存在任一 `evaluated`/`skipped` 结果即为 `partial_failed`（与重试的指标粒度一致）。

`Task.status` 映射：`running` → run 运行中；run 结束（completed/partial_failed）→ task `completed`；
run failed → task `failed`；取消 → task `cancelled`。**不改 tasks 表状态枚举**。

#### Result

| 情况 | status |
|---|---|
| 正常算出分数 | evaluated |
| 输入缺失（无证据/无上下文/无 gold/无答案/无 claims） | skipped + reason |
| 外部调用失败 / Judge 失败 / 分数非法 | failed + error |

### 4.4 批量执行与恢复（Celery）

新增任务 `tasks.rag_evaluation`（`acks_late=True`、`reject_on_worker_lost=True`），
复用 `tasks` 表 + `composition/enqueue` + `executors`，不引入新框架。

```
API 创建：校验版本已发布 + 非空 + mode/metrics 匹配
  → 生成 run(pending) + task(pending)，入队
Worker：
  1. 读取 run；pg_try_advisory_lock(run_id) 失败 → 说明其它 worker 持有，直接返回
  2. run.status=running, task.status=running, heartbeat=now
  3. 逐条 item：
     a. 取消检查（task_control.is_cancelled）
     b. SAVEPOINT：执行 RAG（或复用父 Run trace）→ 写 trace → 算指标 → 写 results
     c. 成功：commit；失败：rollback savepoint，写 failed 结果（尽量）后 commit
     d. 更新 progress + heartbeat + commit（每 N 条或每条）
  4. 收尾：聚合 → run.status → task.status → commit
```

要点：

- **单条失败隔离**：每条一个 savepoint + 独立 commit；
- **时间上限**：Celery `task_time_limit=1800s` 不变；单 Run 默认 `limit=200`，
  超大数据集拆多个 Run（API 支持 `limit` 与 `item_ids`）；
- **并发**：worker concurrency=2，Run 内**串行**执行；两个 Run 可并行（advisory lock 按 run 维度）；
- **取消**：每条前检查；正在执行的当前条允许完成并落库，剩余条不再处理；
- **心跳**：每处理完一条更新 `last_heartbeat_at`，供 stale 识别。

### 4.5 幂等 / 重试 / 并发

| 层 | 方案 |
|---|---|
| Trace | `idempotency_key = rag_eval:{run_id}:{item_id}`（Phase 2 唯一索引）；重复投递直接复用 |
| Result | `unique(run_id,item,metric,version)` + `INSERT ... ON CONFLICT DO NOTHING` |
| 任务重复投递 | advisory lock（run 级）+ 上述两个唯一键 → 不会重复写 |
| Worker 崩溃 | 心跳超过 15 分钟 → `tasks.recover_stale_rag_runs`（beat 每 10 分钟）把 run/task 置 failed(stale) |
| 失败重试 | **新建 Run**（`parent_run_id`、`attempt+1`、`retry_scope=failed_only`）：<br>· 选中父 Run 中「有 failed 结果」或「无结果」的条目<br>· 父 Run 已成功的 Trace 直接复用（按 idempotency key 查），不重复调外部<br>· 新结果写新 Run，历史不覆盖 |
| 重复重试 | 同一父 Run 已有子 Run 时，API 返回 409（防连点）；除非子 Run 也失败 |
| 事务 | 逐条 commit；run/task 最终状态单独 commit |

> 为什么重试用「新 Run」而不是「原地更新失败行」：
> 保留历史错误信息与当时的模型/Prompt 版本；唯一键不变；无需给结果表加 attempt 维度。

### 4.6 聚合定义

Run 结束时写入 `aggregate`：

```json
{
  "run_id": "...",
  "dataset_version_id": "...",
  "execution_mode": "retrieve",
  "adapter": "mock",
  "items": {"total": 100, "executed": 98, "reused_trace": 0, "failed": 2},
  "metrics": {
    "context_recall": {
      "metric_version": "v1",
      "mean": 0.51,
      "evaluated": 86,
      "skipped": 12,
      "failed": 2,
      "coverage": 0.86,
      "skip_reasons": {"gold_evidence_missing": 12}
    }
  }
}
```

定义：

- `mean = Σscore(evaluated) / evaluated`；**skipped / failed 不计入分子分母**；
- `coverage = evaluated / items.total`（有效评测覆盖率）；
- `skip_reasons` 统计 skipped 原因；
- 每个指标必须同时展示 `evaluated` 与 `mean`（API 强制）；
- **不同 metric_version 不混合**：Run 内版本固定，聚合带版本；
- **不同 Run 不默认混合**：跨 Run 汇总接口按
  `(dataset.source_type, execution_mode, adapter, metric_name, metric_version)` 分组，
  并明确返回组内 run 数；
- doc / conv 分属不同数据集（Phase 1 已拆），聚合天然不混。

### 4.7 API（8 个）

| # | 方法 | 路径 | 说明 |
|---|---|---|---|
| 1 | POST | `/rag/evaluations` | 创建 Run（202：`run_id` + `task_id`） |
| 2 | GET | `/rag/evaluations` | 列表（dataset / status / mode / adapter） |
| 3 | GET | `/rag/evaluations/{run_id}` | 详情 + 进度 + 配置快照 |
| 4 | GET | `/rag/evaluations/{run_id}/results` | 结果列表（metric / status / item） |
| 5 | GET | `/rag/evaluations/{run_id}/failures` | 失败样本（含 trace 摘要） |
| 6 | POST | `/rag/evaluations/{run_id}/retry` | 失败重试（新 Run，202） |
| 7 | POST | `/rag/evaluations/{run_id}/cancel` | 取消（委托任务取消） |
| 8 | GET | `/rag/evaluations/summary` | 跨 Run 分组汇总（只读聚合） |

创建请求：

```json
{
  "dataset_version_id": "...",
  "execution_mode": "retrieve | query",
  "adapter": "mock | weknora",
  "split": "test",
  "limit": 200,
  "top_k": 5,
  "precision_mode": "at_k | ap",
  "metrics": ["hit_rate", "mrr", "context_recall", "context_precision_at_k"],
  "judge_metrics": ["faithfulness", "answer_correctness", "answer_relevancy"]
}
```

校验：
- 版本必须 `published`（未发布 → 409）；
- `retrieve` 只允许检索指标，`query` 只允许 Judge 指标（混用 → 422）；
- 版本无条目 → 400；
- `limit` 上限 200（与 30 分钟任务上限匹配）。

### 4.8 迁移安全（021）

| 项 | 方案 |
|---|---|
| 新表 | `rag_evaluation_runs`、`rag_evaluation_results`（只新增） |
| 旧表 | 仅调整 `tasks.task_type` CHECK：先 drop `task_type_valid`，再 create（含 `rag_eval`）；**不改数据** |
| 锁 | CHECK 约束重建需要短暂 ACCESS EXCLUSIVE；`tasks` 表小，放维护窗口执行 |
| 执行顺序 | 生产 018 → 019 → 020 → 021；发布前 `ops/backup/backup.sh` |
| 回滚 | drop 两表 → 删除 `task_type='rag_eval'` 的任务 → 恢复旧 CHECK；文档注明「回滚会丢弃 Run 历史」 |
| 验证 | `alembic check` 无漂移；`upgrade head → downgrade 020 → upgrade head` 往返 |

### 4.9 3C 测试计划

| 层级 | 用例 |
|---|---|
| 单元 | 状态机（completed/partial_failed/failed/cancelled/空集）；聚合（skip/failed 不计 0、coverage、skip_reasons）；重试选中集（failed / 无结果）；mode-metric 校验；config 快照哈希 |
| 集成 | Mock 适配器 + Mock Judge 全链路；单条失败不中断；全部失败 → failed；取消；重试新 Run 复用成功 Trace；重复投递幂等；checksum 不一致；未发布版本 409；空版本 400 |
| 回归 | 全量 851 不得减少；mypy/black/flake8/lint-imports/CI |

---

### 4.10 审核补充约束（实施前锁定）

#### 1. Advisory Lock 生命周期

- 用**专用连接**（`engine.connect()`）执行 `pg_try_advisory_lock(key)`（会话级）；
- 该连接在 Run 全程保持打开，**不归还连接池**；
- 每条样本使用独立 `SessionLocal()` 事务提交，**不影响锁连接**；
- 释放必须使用**同一连接** `pg_advisory_unlock(key)`，随后关闭连接；
- Worker 崩溃 → 进程退出 → 连接关闭 → PG 自动释放会话锁；
- key 由 `run_id` 稳定派生（UUID 前 8 字节 mod 2^63），保证同一 Run 唯一、不同 Run 不冲突；
- **stale 回收必须先抢同一把锁**：抢不到说明 Worker 仍存活，跳过（不标记失败）；
- Worker 在每条样本前后与收尾前刷新 Run 状态，发现被回收/取消则回滚未提交结果并停止。

集成测试：同一 Run 第二次获取失败；正常结束/异常退出后锁可再次获取；不同 Run 可同时持锁；
锁被持有时 stale 回收不生效；释放后才标记 `failed(stale_worker)`。

#### 2. 执行时间预算

| 项 | 值 |
|---|---|
| Celery 软超时 | 1700s（全局） |
| Celery 硬超时 | 1800s（全局） |
| Run 预算 | `RAG_EVAL_SOFT_BUDGET_SECONDS=1500`（可在 .env 覆盖） |
| 单 Run 上限 | 200 条 |

- 每条处理前检查 `elapsed > budget`：**停止领取新样本**，已提交结果保留；
- 未处理样本不写结果（保持「无结果」），Run 结束为 `partial_failed`，`error_message=time_budget_exhausted`；
- 重试 Run 的选中集包含「无结果」条目，可续跑；
- 每条样本耗时写入该条每个结果的 `details.item_latency_ms`（无需新表）。

#### 3. Trace 复用规则（仅重试 Run）

复用父 Run 的成功 Trace 前，逐项比较：

| 条件 | 要求 |
|---|---|
| `trace.status` | 必须 `success`（失败 Trace 不复用） |
| `trace.adapter` | 与当前 Run 相同 |
| `trace.mode` | 与当前 Run 的 `execution_mode` 相同 |
| `trace.retrieval_config._request_config` | 与当前 Run 的 retrieval_config **逐字相等**（含 KB / Agent / top_k / precision_mode / split） |
| `trace.dataset_item_id` | 等于当前条目 |
| 数据集 | 版本 id 相同且 checksum 一致 |

适配器返回的 `match_count/vector_threshold` 等回显字段不能直接与请求配置比较；
评测 Run 执行时把请求配置写入 trace 的 `retrieval_config._request_config`，复用只认这一份指纹。
旧 Trace（无 `_request_config`）一律不复用。

不一致 → 重新执行 RAG。复用时在结果 `details` 写
`{"trace_reused": true, "trace_reused_from_run_id": "...", "source_trace_id": "..."}`。

#### 4. 失败重试粒度（按指标，不整条重跑）

对父 Run 的每个条目、每个预期指标：

| 父结果状态 | 子 Run 行为 |
|---|---|
| `evaluated`（检索指标） | **复制**结果（新 run_id，`details.reused_from_run_id`） |
| `evaluated`（Judge 指标） | 仅当 `model / temperature / max_tokens / prompt_sha256` 与**当前**指纹一致才复制 |
| `skipped` | **复制**结果（保留 skipped_reason；不依赖模型） |
| `failed` | 重新执行 |
| 无结果 | 执行该指标 |

重试 Run 的 `judge_config.metric_fingerprints` 在**创建重试时按当前 Prompt/模型重新计算**，
不直接照抄父 Run；Prompt 或模型参数变化会导致指纹失配 → 重新执行（安全方向）。

只有当存在「failed / 无结果」指标时才执行 RAG；若全部可复用，则不调用适配器。
RAG 执行失败且无有效 Trace → 该条全部指标记 failed(`trace_failed`)，下次重试会重新执行 RAG。
父 Run 结果永远不改动。

#### 5. Run 状态边界

| 场景 | run.status |
|---|---|
| 全部 evaluated | `completed` |
| evaluated + skipped，无 failed | `completed` |
| 部分 failed | `partial_failed` |
| 全部 failed | `failed` |
| 全部 skipped | `completed` |
| 空数据集 | **创建时 400**（不创建 Run） |
| 用户取消 | `cancelled` |
| 时间预算耗尽（有未处理条目） | `partial_failed` + `time_budget_exhausted` |

`task.status` 与 `run.status` **分别返回**：run=partial_failed 时 task=completed（任务执行完毕），
API 文档与前端都不得只显示其中一个。

---

## 5. 测试计划

| 层级 | 用例 |
|---|---|
| 3A 单测 | 表驱动：完全命中/完全未命中/部分命中/Top-K 边界/空检索/空 Gold/文档级/chunk 级/重复检索/重复 Gold/文本规范化/混合粒度 + 公式断言 |
| 3B 单测 | Judge 输出解析、claim 聚合、跳过规则、异常/超时/结构化失败（Mock LLM） |
| 3C 集成 | 建任务 → 执行（Mock 适配器）→ trace → 4 指标 → 结果 → 聚合 → 失败样本 → 重试 → 重复提交 |
| 回归 | 全量 `pytest -m "not prompt"`（Phase 3B 基线 851，3C 后 **884** 不得减少）、mypy、black、flake8、lint-imports、前端覆盖率 |

---

## 6. 与 Phase 0 方案的差异

| 项 | Phase 0 方案 | 本设计 | 原因 |
|---|---|---|---|
| 结果表 | 单表 `rag_eval_results`（trace 1-1） | `rag_evaluation_runs` + `rag_evaluation_results` | 一个 trace 有多个指标、可被多版本重复评测，1-1 表会覆盖历史 |
| 任务 | 新增 `rag_eval` 任务类型 | 同，但部分失败用 run 状态表达 | 不改变既有 task 状态机 |
| Context Precision | 单一指标 | 两个命名变体 | 避免口径混淆 |
| 文本匹配 | 未细化 | 规范化后**完全相等** | 防止包含匹配造成假命中 |
| 失败重试 | 未定义 | **新建 Run**（parent_run_id + failed_only），复用成功 Trace | 保留历史、不覆盖、避免重复调用外部 |
| 任务类型 | 新增 `rag_eval` | 同，需要迁移 021 调整 `tasks.task_type` CHECK | 旧约束只允许 6 种类型 |
| 结果唯一键 | `(run,item,metric)` | `(run,item,metric,metric_version)` | 指标版本可追溯且不覆盖历史 |

---

## 7. 子阶段状态

| 子阶段 | 状态 |
|---|---|
| 3A 确定性指标 | ✅ 已实现（`app/application/metrics.py` + **40 条**单测；含 Precision 分母与去重粒度补充） |
| 3B LLM Judge | ✅ 已实现（Agent + 3 Prompt + 编排服务 + 24 条测试） |
| 3C 持久化与批量 | ✅ 已实现（迁移 021 + 2 表 + 8 API + Celery 执行/恢复/重试 + 聚合 + 28 条新增测试）；真实 WeKnora 联调未完成 |
| 3D 真实 WeKnora 联调 | ✅ 本地 VM 完成（retrieve/query/Trace/批量 Run，详见 `07-phase3d-weknora.md`） |
