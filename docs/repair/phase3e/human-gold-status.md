# Phase 3E Human Gold 状态（v1）

**日期**：2026-11-16
**复核人**：江晚
**范围**：13 条基础数据 + 1 条 Claim（Q21#3）
**来源**：`human-gold-review-base.csv`（13 行）、`human-gold-review-claim.csv`（1 行）、`human-gold-decisions.md`

---

## 1. 已固化

| 文件 | 内容 |
|---|---|
| `human-gold.json` | 13 条基础 + Q21#3，`provenance=human_gold`，含最终问题/类别/答案/Evidence/answerability |
| `human-gold.pending.json` | 27 条未复核基础数据；`human=null`，`pending_human` |
| `human-gold.claims-pending.json` | 34 条未复核 Pilot Claim；`human_label=null`，`pending_human` |
| `human-gold-decisions.md` | 用户签署的复核结论与变更记录 |
| `human-gold-review-base.csv` | 13 行人工原始填写（保留） |
| `human-gold-review-claim.csv` | Q21#3 人工原始填写（保留） |

已复核基础 ID：Q23、Q36、Q14、Q15、Q16、Q19、Q37、Q40、Q05、Q13、Q22、Q30、Q35。
已复核 Claim：Q21#3。

---

## 2. 分类覆盖（按人工决定）

| 类别 | 复核前 | 复核后 |
|---|---:|---:|
| direct | 10 | 12 |
| multi | 10 | 8 |
| constraint | 8 | 9 |
| unanswerable | 6 | 6 |
| ambiguous | 6 | 5 |
| **合计** | **40** | **40** |

变更：Q15 `multi→direct`；Q16 `multi→constraint`；Q40 `ambiguous→direct`。
Q23 保持 `constraint`，Q14/Q19 保持 `multi`，Q36/Q37/Q35 保持 `ambiguous`。

> 若验收要求严格的 10/10/8/6/6，应用“替换题目”恢复覆盖，而不是回改标签。

---

## 3. 题干改写

| ID | 原问题 | 最终问题 |
|---|---|---|
| Q23 | 生鲜食品签收后第 2 天发现质量问题，还能按政策反馈吗？ | 生鲜食品签收后超过 24 小时（如第 2 天）发现质量问题，还能按政策反馈吗？ |
| Q40 | 积分怎么用？ | 积分可以转让或提现吗？ |

原问题保留在 `human-gold.json` 的 `original_question`；`question_changed=true`。

---

## 4. 仍待处理

### 4.1 key_facts

13 条基础数据的 `key_facts` **尚未单独人工复核**，统一为 `[]` + `key_facts_status=pending_human`。

已准备审核表：`human-gold-key-facts-review.md` / `.json` / `.csv`（13 行）/ `-long.csv`（45 条事实）；所有 `human_*` 字段为空，仍待人工确认。
- 不得用 AI 草稿填充；
- 当前 Judge 的 Correctness 使用 `gold_answer`，不依赖 key_facts，因此 10 条 Pilot 对比可先跑；
- 完整 40 条 Gold 前建议补齐。

### 4.2 未复核数据

- 27 条基础数据（见 `human-gold.pending.json`）；
- 34 条 Pilot Claim（35 条中仅 Q21#3 已复核；见 `human-gold.claims-pending.json`）；
- Q21 基础题本身仍未复核，只有其 Claim 已复核。

### 4.3 文档冲突

- Q36：§1“已激活的虚拟商品”与 §12“虚拟商品一经售出”口径不一致；Human Gold 保留 `ambiguous`，答案内披露，不选边。
- 需业务确认 canonical 口径；不阻塞本条作为模糊题使用。

### 4.4 Q21#3

- 人工标签：`insufficient_evidence`；
- 理由：§1 只把 7 天限定在无理由退款，未规定普通商品质量问题退换期限；§3 换货仍限 7 天；
- 未判 `unsupported`，因为原文未直接矛盾。

### 4.5 旧表状态

`human-review-pilot.csv`、`human-review-remaining.csv`、`pilot-claims-review.csv` 仍保留为 AI 草稿/空白模板，**不是**本次 Human Gold 的同步副本。
下游以 `human-gold.json` / `human-gold.pending.json` 为准；如需旧表，另行回填并保留变更记录。

---

## 5. 下一步（未执行）

1. （可选）补齐 13 条 key_facts；
2. 复核剩余 27 条基础 + 34 条 Claim；
3. 按 subagent 复核意见修订 Prompt v1.1.1；
4. 用相同 10 条跑 v1.1.1 对比（需另行批准）；
5. 通过后再跑完整 40 条。

**当前未改 Prompt/Agent/Schema/API/DB，未运行 Judge；v1.1.0 仍 pending_review。**

---

## 6. 一致性审计（2026-11-16）

- 报告：`human-gold-audit.md`；机器结果：`human-gold-audit.json`
- **345 项检查全部通过**（0 失败、0 警告）
- 覆盖：40 条候选、13 条 Gold、27 条 pending、1 条 Gold Claim、34 条 pending Claim、
  来源 SHA、Evidence 逐字性、状态、分类/answerability、题目改写、Prompt 版本关系
- 未修改任何 Prompt/Agent/Schema/API/DB，未运行 Judge

---

## 7. key_facts 审核准备（2026-11-16）

- 覆盖 13 条 human_reviewed 基础数据；
- 候选 45 条原子事实；
- 证据状态：`supported` 42 / `evidence_insufficient` 2 / `ambiguous` 1；
- 证据缺失：Q30-F1（海外配送未提及）、Q35-F5（运输/送达时长未说明）；
- 歧义：Q36-F8（§1/§12 虚拟商品口径冲突）；
- 所有 `human_decision` / `human_corrected_key_facts` / `human_reason` 为空，`review_status=pending_human`；
- 当前 Correctness Prompt 只读取 `gold_answer`，不读取 key_facts，因此本表不会改变 Judge 分数；
- 未修改 `human-gold.json`、pending 数据、Prompt、Agent、Schema、API、DB，未运行 Judge。
