# 评测引擎设计（Phase 3）

> 范围：Phase 3A 确定性检索指标（本阶段实现）、3B LLM Judge（待审）、3C 持久化与批量任务（待审）。
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

## 3. Phase 3B：LLM Judge（设计，待审核）

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

### 3.7 测试计划（全部 Mock LLM，无真实 API）

| 指标 | 用例 |
|---|---|
| Faithfulness | 全支持 / 部分支持 / 无 claims（skipped）/ 无上下文（不调用模型）/ `context_available=false` / 非法 JSON / 超时 / 少字段 |
| Correctness | 全对 / 部分对 / 全错 / 缺 gold（skipped）/ 调用失败 |
| Relevancy | 高相关 / 低相关 / 空答案（skipped）/ 调用失败 |
| 追溯 | prompt_version 与 sha256、model 名称、原始输出、不同版本重复评测不覆盖（3C 断言） |

---
## 4. Phase 3C：持久化与批量任务（设计，待实施）

### 4.1 数据模型（迁移 021）

复用 `tasks` 作为任务主体（`task_type='rag_eval'`），新增两张表：

```
tasks 1─n rag_evaluation_runs 1─n rag_evaluation_results
rag_traces 1─n rag_evaluation_results
qa_dataset_items 1─n rag_evaluation_results
```

| 表 | 关键字段 |
|---|---|
| `rag_evaluation_runs` | id、task_id(FK)、dataset_version_id(FK)、execution_mode、adapter、judge_config(JSONB)、metrics(JSONB 启用清单)、total/success/failed/skipped、aggregate(JSONB)、status、started_at/completed_at |
| `rag_evaluation_results` | id、run_id(FK CASCADE)、task_id(FK)、dataset_item_id(FK SET NULL)、rag_trace_id(FK SET NULL)、metric_name、metric_version、value、status、details(JSONB)、judge_config(JSONB)、judge_raw(JSONB)、error_message、created_at |

索引：`(run_id, metric_name)`、`(run_id, status)`、`(task_id)`、`(rag_trace_id)`；
`unique(run_id, dataset_item_id, metric_name, metric_version)` 保证**同一次运行内指标幂等**，
不同 run（不同 Judge 版本）互不覆盖。

### 4.2 任务状态映射

复用现有 `Task.status`：
`pending → running → completed | failed`；**部分失败**映射为 `completed` + `run.status='partial_failed'`
（不改任务表语义，避免影响现有 UI/重试逻辑）。

### 4.3 批量流程

```
创建 task(rag_eval) + run 记录
→ 读取 dataset_version 的 items（只取 split=test，可配）
→ 逐条：调用 RAG 执行（retrieve 或 query）→ 写 trace（idempotency_key=task:{id}:item:{id}）
→ 计算指标（3A 纯函数 / 3B Judge）
→ 写入单条结果
→ 单条失败只记 failed，不中断
→ 聚合（按 metric_name + status）
→ 更新 run.aggregate、run.status、task.progress/status
```

幂等：
- trace 复用 `idempotency_key`（Phase 2 已建唯一索引）；
- 结果唯一键 `(run_id, dataset_item_id, metric_name, metric_version)`，重跑同一 run `ON CONFLICT DO NOTHING`；
- 重试失败样本 = 新 run（保留历史），不复用旧 run 的结果。

### 4.4 聚合

```json
{
  "dataset_version_id": "…",
  "execution_mode": "retrieve",
  "adapter": "mock",
  "metrics": {
    "hit_rate": {"k": 5, "mean": 0.62, "evaluated": 100, "skipped": 12, "failed": 0,
                 "skip_reasons": {"gold_evidence_missing": 12}},
    "context_recall": {"mean": 0.51, "...": "..."}
  }
}
```

- `skipped` 不进入 `mean`；
- `doc` / `conv` 分别建 run（数据集本身就分开），聚合结果带 `dataset_id/version`，**不合并**；
- 每个 `mean` 必须能反查到单条结果（结果表按 run 查询）。

---

## 5. 测试计划

| 层级 | 用例 |
|---|---|
| 3A 单测 | 表驱动：完全命中/完全未命中/部分命中/Top-K 边界/空检索/空 Gold/文档级/chunk 级/重复检索/重复 Gold/文本规范化/混合粒度 + 公式断言 |
| 3B 单测 | Judge 输出解析、claim 聚合、跳过规则、异常/超时/结构化失败（Mock LLM） |
| 3C 集成 | 建任务 → 执行（Mock 适配器）→ trace → 4 指标 → 结果 → 聚合 → 失败样本 → 重试 → 重复提交 |
| 回归 | 全量 `pytest -m "not prompt"`（基线 787 不得减少）、mypy、black、flake8、lint-imports、前端覆盖率 |

---

## 6. 与 Phase 0 方案的差异

| 项 | Phase 0 方案 | 本设计 | 原因 |
|---|---|---|---|
| 结果表 | 单表 `rag_eval_results`（trace 1-1） | `rag_evaluation_runs` + `rag_evaluation_results` | 一个 trace 有多个指标、可被多版本重复评测，1-1 表会覆盖历史 |
| 任务 | 新增 `rag_eval` 任务类型 | 同，但部分失败用 run 状态表达 | 不改变既有 task 状态机 |
| Context Precision | 单一指标 | 两个命名变体 | 避免口径混淆 |
| 文本匹配 | 未细化 | 规范化后**完全相等** | 防止包含匹配造成假命中 |

---

## 7. 子阶段状态

| 子阶段 | 状态 |
|---|---|
| 3A 确定性指标 | ✅ 已实现（`app/application/metrics.py` + **40 条**单测；含 Precision 分母与去重粒度补充） |
| 3B LLM Judge | 📄 设计完成，**待审核**（本文第 3 节） |
| 3C 持久化与批量 | 待 3B 审核后实施 |
