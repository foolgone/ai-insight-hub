# Phase 3E 人工标注规范

**适用范围**：`docs/repair/phase3e/candidates.json` 的 40 条候选（10 条 Pilot + 30 条待审）。
**核心原则**：AI 预标注只是草稿，**不得**直接视为 Human Gold；人工审核结果单独保存。

---

## 1. 文件与状态

| 文件 | 用途 | 是否可改 |
|---|---|---|
| `candidates.json` | 自动构造的候选与 AI 预标注 | 只读，保留 `provenance=auto_generated` |
| `pilot-labels.ai-draft.json` | 10 条 Pilot 的 AI Claim 预标注 | 只读 |
| `human-gold.template.json` | 人工 Gold 模板（当前全空） | 人工填写后另存为 `human-gold.json` |
| `human-review-pilot.csv` | 10 条 Pilot 基础字段审核表 | 填写 human 列 |
| `pilot-claims-review.csv` | 10 条 Pilot Claim 审核表 | 填写 human 列 |
| `human-review-remaining.csv` | 剩余 30 条基础字段审核表 | 填写 human 列 |
| `pending-review.md` | 待审清单与状态 | 更新状态 |

### 状态值

| 值 | 含义 |
|---|---|
| `pending_human` | 尚未审核 |
| `in_review` | 审核中 |
| `approved` | 人工确认，可作为 Gold |
| `needs_recheck` | 不确定/有争议，需复核 |
| `rejected` | 问题或标注不合格，需重做 |

---

## 2. 基础字段

| 字段 | 规则 |
|---|---|
| `question` | 必须能独立理解；模糊问题允许保留，但 `answerability=ambiguous` |
| `reference_answer` | 仅依据文档事实；不引入外部知识；模糊问题写成条件分支或明确“信息不足” |
| `gold_evidence` | 文档原文逐字摘录（可多条）；记录 `section`、`quote`；不得用改写句充当原文 |
| `key_facts` | 原子事实，一条只表达一个可判定事实；与 reference_answer 一致 |
| `answerability` | `answerable` / `unanswerable` / `ambiguous` 三选一 |
| 审核结论 | `approved` / `needs_recheck` / `rejected`，并填写 `reviewer`、`reviewed_at`、`notes` |

### answerability 判定

- `answerable`：文档有明确、唯一答案（允许多条件，但条件可从问题确定）。
- `unanswerable`：文档未提及，且不能由文档事实无歧义推出。
- `ambiguous`：问题缺少必要信息（商品类型、签收时间、金额、地区等），需要条件分支或追问。

---

## 3. Claim 级标注（Faithfulness）

**对象**：模型实际生成的回答（`pilot-judge-results.json` 中的 `answer`），不是 reference_answer。

### 标签

| 标签 | 含义 |
|---|---|
| `supported` | 检索上下文有明确原文依据，或可无歧义推出 |
| `unsupported` | 与上下文矛盾，或上下文没有依据且不能推出 |
| `insufficient_evidence` | 上下文不足以判断真假（未提及/只沾边/需外部知识），但不能判定为假 |
| `needs_recheck` | 标注者不确定，需复核 |

### 规则

1. 每条 claim 必须是**原子事实**；结论句单独一条。
2. 操作建议/下一步指引：若不含事实承诺，标 `non_factual`（不进入分母）；若含“我们会退款/系统自动处理”等事实承诺，按事实 claim 判断。
3. 回答内部矛盾（如先说可以、后说超时不可以）必须单独标记 `contradictory`，并记录 `contradiction_with`。
4. `evidence_reference` 必须是上下文中的 chunk_id 或原文；没有证据写 `null`。
5. `reason` 说明“支持/不支持/证据不足”的具体原因。
6. 不确定时用 `needs_recheck`，不得强行二选一。

---

## 4. 审核流程

1. 打开 `human-review-pilot.csv` / `human-review-remaining.csv`。
2. 逐条核对 `question`、`ai_reference_answer`、`ai_gold_evidence`、`ai_key_facts`、`ai_answerability`。
3. 在 `human_*` 列填写人工结论；不要把 AI 内容直接复制为人工结论，必须逐条核对原文。
4. Pilot 的 Claim 审核使用 `pilot-claims-review.csv`；剩余 30 条的 Claim 在生成答案后补充。
5. 所有不确定项标 `needs_recheck`，在 `notes` 写原因。
6. 审核完成后另存 `human-gold.json`，**不要覆盖** `candidates.json` 或 `pilot-labels.ai-draft.json`。
7. 只有 `approved` 的样本才能进入 v1.1.0 / 40 条正式评测。

---

## 5. 质量门槛

- Gold Evidence 必须能在 `phase3d_doc.md` 中找到逐字原文；
- 参考答案不得包含文档未提及的承诺；
- `unanswerable` 样本的参考答案必须是“文档未提及/无法确认”，不得编造；
- `ambiguous` 样本必须写明缺失信息或条件分支；
- Claim 标签与证据必须一致；`supported` 必须有 `evidence_reference`；
- 任一审核人不得同时把 AI 预标注直接标记为 `approved` 而不核对原文。
