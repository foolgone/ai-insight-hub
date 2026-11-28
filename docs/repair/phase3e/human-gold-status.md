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

### 4.1 key_facts（已完成）

13 条基础数据的 `key_facts` 已人工确认并写入 `human-gold.json`：
- **41 条**最终事实：`supported` 38 / `evidence_insufficient` 2（Q30-F1、Q35-F5）/ `ambiguous` 1（Q36-F8）；
- 45 条候选 → 38 accept / 3 modify / 4 delete；
- `key_facts_status=human_reviewed`，reviewer=江晚，reviewed_at=2026-11-16；
- 逐条证据保留在 `key_fact_details`；审核记录见 `human-gold-key-facts-review-long.csv`（45 行）与 `human-gold-key-facts-decisions.md`；
- 当前 Judge 的 Correctness 使用 `gold_answer`，不依赖 key_facts；未来启用需另开 Schema。

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

1. 复核剩余 27 条基础 + 34 条 Claim；
2. 按 subagent 复核意见修订 Prompt v1.1.1；
3. 用相同 10 条跑 v1.1.1 对比（需另行批准）；
4. 通过后再跑完整 40 条。

**当前未改 Prompt/Agent/Schema/API/DB，未运行 Judge；v1.1.0 仍 pending_review。**

---

## 6. 一致性审计（2026-11-16）

- 报告：`human-gold-audit.md`；机器结果：`human-gold-audit.json`
- **424 项检查全部通过**（0 失败、0 警告）
- 覆盖：40 条候选、13 条 Gold、27 条 pending、1 条 Gold Claim、34 条 pending Claim、
  来源 SHA、Evidence 逐字性、状态、分类/answerability、题目改写、Prompt 版本关系
- 未修改任何 Prompt/Agent/Schema/API/DB，未运行 Judge

---

## 7. key_facts 复核结论（2026-11-16）

- 覆盖 13 条 human_reviewed 基础数据，候选 45 条 → **最终 41 条**；
- 决定：`accept` 38 / `modify` 3 / `delete` 4；
- 证据状态：`supported` 38 / `evidence_insufficient` 2 / `ambiguous` 1；
- 删除：Q23-F4（重复）、Q15-F1（定义性上下文）、Q16-F1（条件重复）、Q22-F4（非必答推导）；
- 改写：Q23-F2、Q36-F3、Q16-F2；
- 保留 absence：Q30-F1、Q35-F5；保留 conflict：Q36-F8（均不进入 supported 分母）；
- 逐条结果：`human-gold-key-facts-review-long.csv`（45 行）、`human-gold-key-facts-review.csv`（13 行）、`human-gold-key-facts-review.json`；
- 结论与 8 个问题的决定：`human-gold-key-facts-decisions.md`；
- **已写入** `human-gold.json`：13 条 key_facts 全部 `human_reviewed`（41 条）；未改 Prompt/Agent/Schema/API/DB，未运行 Judge。
