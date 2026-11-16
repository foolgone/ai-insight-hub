# Phase 3E Human Gold v1 一致性审计报告

**日期**：2026-11-16
**审计范围**：Human Gold v1、27 条 pending 基础、34 条 pending Claim、来源文档、版本关系
**审计性质**：只读审计；未改 Prompt/Agent/Schema/API/DB，未运行 Judge
**结果**：**345 项检查全部通过（0 失败，0 警告）**

---

## 1. 数量与 ID 分区

| 项 | 数量 | 校验 |
|---|---:|---|
| 候选总数 | 40 | Q01–Q40，唯一、无缺失 |
| Human Gold 基础 | 13 | 全部 `human_reviewed` |
| Pending 基础 | 27 | 全部 `pending_human`、`human=null` |
| 基础合计 | 40 | 13 + 27，无交集、无重复 |
| Human Gold Claim | 1 | Q21#3 |
| Pending Claim | 34 | 全部 `pending_human`、`human_label=null` |
| Claim 合计 | 35 | 1 + 34，无交集、无重复 |

已复核基础 ID：
`Q23, Q36, Q14, Q15, Q16, Q19, Q37, Q40, Q05, Q13, Q22, Q30, Q35`

Pending 基础：其余 27 条，见 `human-gold.pending.json`。
Claim：仅 `Q21#3` 已复核；其余 34 条见 `human-gold.claims-pending.json`。

---

## 2. 状态与来源

| 检查 | 结果 |
|---|---|
| `human-gold.json` provenance | `human_gold` |
| Reviewer | 江晚 |
| Reviewed at | 2026-11-16 |
| 13 条基础 `review_status` | 全部 `human_reviewed` |
| Q21#3 `review_status` | `human_reviewed` |
| Pending 基础/Claim | 全部 `pending_human`，human 字段为空 |
| AI 草稿是否被冒充 Human Gold | 否 |
| 旧 `human-review-*.csv` / `pilot-claims-review.csv` | 仍为空模板，未被误当 Human Gold |
| `human-gold.template.json` | human 字段仍全空 |
| 工作台 CSV 与 Human Gold | 13 条答案、Evidence、reviewer、decision 全部一致 |
| Q21#3 工作台与 Gold | label、reason 一致 |

---

## 3. 文档来源与证据

| 检查 | 结果 |
|---|---|
| 来源文档 | `docs/repair/phase3e/source/phase3d_doc.md` |
| SHA-256 | `737f6bd3ef412d41d14ada4d2000bd01e851355f0d95cd0d321ac84416f9002d` |
| `human-gold.json` meta SHA | 与来源文档一致 |
| 13 条基础 Evidence | 全部逐字存在于来源文档 |
| Q30（unanswerable） | Evidence 为空，符合规范 |
| 其他 12 条 | Evidence 非空 |
| Q36 | 答案披露 §1/§12 虚拟商品口径冲突 |
| Q37 | 已移除“订单中申请/填写抬头”等文档外流程 |
| Q23/Q40 题干改写 | `final_question` 已更新，`original_question` 保留 |

---

## 4. 分类与答案性

复核后分类覆盖：

| 类别 | 数量 |
|---|---:|
| direct | 12 |
| multi | 8 |
| constraint | 9 |
| unanswerable | 6 |
| ambiguous | 5 |
| **合计** | **40** |

与 `human-gold-decisions.md` 的变更一致：
Q15 `multi→direct`、Q16 `multi→constraint`、Q40 `ambiguous→direct`；
Q14/Q19 `answerability=ambiguous`；Q23/Q40 题干改写。

---

## 5. 版本关系

| 项 | 状态 |
|---|---|
| Human Gold 版本 | `phase3e-human-gold-v1` |
| Prompt v1.0.0 | 归档 `active=true`，未修改 |
| Prompt v1.1.0 | `pending_review` / `active=false`，未运行 |
| v1.1.1 | 尚未创建 |
| Judge / 10 条对照 / 40 条 | 未执行 |

---

## 6. 仍然存在的差距（不是一致性错误）

1. **key_facts 未人工复核**：13 条全部 `[]` + `key_facts_status=pending_human`；未用 AI 草稿填充。
2. **27 条基础 + 34 条 Claim 未复核**：属于范围缺口，不是本次 13+1 的冲突。
3. **Q21 基础题未复核**：仅有其 Claim Q21#3 已复核；`human-gold.pending.json` 中 Q21 基础仍为 pending。
4. **Q36 文档口径冲突**：§1“已激活虚拟商品”vs §12“虚拟商品一经售出”；Human Gold 保留 ambiguous 并披露，需业务确认 canonical 口径。
5. **分类覆盖变化**：由 10/10/8/6/6 变为 12/8/9/6/5；如验收强制原比例，应替换题目而不是回改标签。
6. **旧表未同步**：`human-review-*.csv`、`pilot-claims-review.csv` 仍为 AI 草稿/模板；下游以 `human-gold.json` 为准。

---

## 7. 审计结论

- Human Gold v1 的 **数量、ID、状态、来源、证据、版本关系**均一致；
- 13 条基础 + Q21#3 可作为已确认的人工参照；
- **不是完整 40 条 Human Gold**，且 key_facts 仍未人工确认；
- 在这些差距关闭前，不应把结果称为“完整 40 条验收”；
- 未修改任何 Prompt、Agent、Schema、API、DB，未运行 Judge。

**建议下一步**：先补 key_facts / 继续复核 27+34；同时按 Subagent 复核意见设计 v1.1.1；在 v1.1.1 通过二次审核前，不跑 10 条对照。
