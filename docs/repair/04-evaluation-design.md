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

---

## 3. Phase 3B：LLM Judge（设计，待实施）

### 3.1 复用

`BaseAgent` + `LLMClient` + 现有重试/降级/成本/结构化输出；新增 `app/agents/rag_judge_agent.py`
与 `app/prompts/rag_judge/{system.txt,version.txt,dimensions/*.txt}`。**不引入新依赖**。

### 3.2 三个指标

| 指标 | 输入 | 输出 |
|---|---|---|
| **Faithfulness** | `answer` + **本次 Trace 的真实上下文**（`context_source=agent_chat`） | `claims[{claim,supported,evidence[],reason}]` + `score=supported/total` |
| **Answer Correctness** | `question` + `answer` + `gold_answer` | `score`、`missing_points[]`、`wrong_facts[]`、`reason` |
| **Answer Relevancy** | `question` + `answer` | `score`、`reason` |

规则：
- `context_source != "agent_chat"` 或 contexts 为空 → Faithfulness `skipped(context_unavailable)`，**不调用 Judge**；
- `gold_answer` 为空 → Correctness `skipped(gold_answer_missing)`；
- 回答为空 → Relevancy `skipped(answer_missing)`；
- 不使用独立 `retrieve` 的上下文替代。

### 3.3 可追溯

每条结果保存：`judge_config={model, temperature, prompt_version, metric_version}`、`judge_raw`（原始 JSON）、`created_at`。
同一 trace 可用不同 `judge_config` 重新评测，产生新结果行（不覆盖）。

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
| 3A 确定性指标 | ✅ 已实现（`app/application/metrics.py` + 37 条单测） |
| 3B LLM Judge | 待审后实施 |
| 3C 持久化与批量 | 待审后实施 |
