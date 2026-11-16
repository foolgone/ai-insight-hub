# Phase 3E-H key_facts 人工复核结论（2026-11-16）

> **范围**：13 条 `human_reviewed` 基础数据的 45 条候选 key_facts。
> **结果**：**41 条最终事实**（`supported` 38 / `evidence_insufficient` 2 / `ambiguous` 1）。
> **复核人**：江晚（结论由 AI 起草，用户确认署名）。
> **未做**：未改 `human-gold.json`（key_facts 仍为 `[]`）、Prompt、Agent、Schema、API、DB；未运行 Judge。

---

## 1. 八个问题的决定

| # | 问题 | 决定 | 理由 |
|---|---|---|---|
| 1 | Q30-F1 是否保留“文档未说明海外配送” | **保留**，`evidence_insufficient` | unanswerable 题的唯一预期内容就是“文档未说明”；删掉会使 key_facts 为空，失去对“编造支持海外配送”的约束。标为 absence fact，不进入 supported 分母 |
| 2 | Q35-F5 是否保留“文档未说明运输/送达时长” | **保留**，`evidence_insufficient` | 它是“发货≠到货”的核心结论；删掉会让只答发货时效的回答看起来完整 |
| 3 | Q36-F8 冲突是否作为 key_fact | **保留**，`ambiguous`，定性为 meta/conflict fact | §1 限“已激活”、§12 称“一经售出”；gold answer 明确要求披露该冲突。删掉后“一律按 §12 不退”的单边回答会看起来完整。它不作为政策事实，不进入 supported 分母；业务口径仍待确认 |
| 4 | Q23-F3 条件否定推导是否接受 | **接受**，`supported` | 由“质量问题需在 24 小时内反馈”必然推出“超过 24 小时不符合该条款”，属条款适用结论，不是外部知识 |
| 5 | Q22-F4 算术推导是否接受 | **算术成立，但不作为 key_fact（删除）** | 89<99 为真，但 gold answer 未要求；且偏远地区 20 元/不包邮不受包邮门槛影响，保留会迫使简洁正确答案补算门槛 |
| 6 | Q37 是否补 absence fact（申请入口/填写步骤） | **不补** | gold answer 只说“信息不足：需明确…”，没有断言“文档未写步骤”；key_facts 不能超出 gold answer。若以后把该句写进 gold answer，再补 absence fact |
| 7 | 粒度是否继续拆/合 | **不再拆；删除 4 条、改写 3 条，45→41** | 一条 key_fact = 一个答案必须覆盖/蕴含的可判定点；条件式规则算一条，不把“条件”和“动作”拆开；重复、定义性上下文、问句已给条件、非必答推导不进入 key_facts |
| 8 | key_facts 的用途 | **本阶段不进入 Judge** | 当前 Correctness 只读 `gold_answer`。未来若启用，需另开 Schema：`fact_type`（policy/derived/absence/conflict）、`required`（bool）、`evidence_status`，并规定 absence/conflict 不进 supported 分母 |

---

## 2. 变更清单

### 2.1 删除（4 条）

| Fact | 原事实 | 删除理由 |
|---|---|---|
| Q23-F4 | 该 24 小时时限适用于生鲜食品的质量问题 | 与 F1 重复；F1 已限定“生鲜食品的质量问题” |
| Q15-F1 | 大件商品包括家具、家电 | 定义性上下文，gold answer 未要求；保留会要求答案补举例子 |
| Q16-F1 | 物流信息超过 24 小时未更新是联系客服核查的触发条件 | 条件已在问句中，且与 F2 重复；不把条件/动作拆成两条 |
| Q22-F4 | 订单实付 89 元未满 99 元包邮门槛 | 非必答推导；偏远地区规则不受包邮门槛影响 |

### 2.2 改写（3 条）

| Fact | 原事实 | 最终事实 | 理由 |
|---|---|---|---|
| Q23-F2 | 反馈方式为拍照反馈 | 质量问题需以拍照方式反馈 | 原句同义反复；改写后仍由 §12 直接支持 |
| Q36-F3 | 生鲜食品不支持无理由退货 | 生鲜食品不支持无理由退款 | 原证据 §1 写“退款”，原事实写“退货”与证据不一致；与 gold answer 对齐 |
| Q16-F2 | 触发后可联系客服协助核查 | 物流信息超过 24 小时未更新时，可联系客服协助核查 | 删除 F1 后“触发后”指代不明；改为完整条件句，逐字对应 §6 |

其余 38 条 `accept`，事实文本不变。

---

## 3. 最终分布

| 项目 | 条数 |
|---|---:|
| Q23 | 3 |
| Q36 | 8 |
| Q14 | 2 |
| Q15 | 1 |
| Q16 | 1 |
| Q19 | 2 |
| Q37 | 5 |
| Q40 | 3 |
| Q05 | 2 |
| Q13 | 3 |
| Q22 | 3 |
| Q30 | 1 |
| Q35 | 7 |
| **合计** | **41** |

证据状态：`supported` 38、`evidence_insufficient` 2（Q30-F1、Q35-F5）、`ambiguous` 1（Q36-F8）。

---

## 4. 采用的原则

1. key_facts 只收录 **gold answer 必须覆盖或必然蕴含** 的原子事实，不复述整段 evidence。
2. 条件式规则算一条（如“超过 24 小时未更新时，可联系客服”），不拆成“触发条件”+“动作”两条。
3. 重复表述、定义性上下文、问句已给条件、非必答推导不进入 key_facts。
4. absence fact 只在 gold answer 明确说“文档未说明”时保留（Q30、Q35）；冲突 fact 只在 gold answer 要求披露时保留（Q36）。
5. absence/conflict 不进入 `supported` 分母，避免把“无法提供肯定证据”算成支持率。

---

## 5. 未做与后续

- `human-gold.json` 未修改，13 条 key_facts 仍为 `[]` + `pending_human`；需按本结论另行生成。
- 未改 Prompt/Agent/Schema/API/DB，未运行 Judge、10 条对照或 40 条评测。
- Q36 的 §1/§12 口径仍需业务确认；不影响本条作为 ambiguous 使用。

---

## 6. 文件

- 逐条：`human-gold-key-facts-review-long.csv`（45 行，已填）
- 汇总：`human-gold-key-facts-review.csv`（13 行，已填）
- 机器可读：`human-gold-key-facts-review.json`（已填 human 字段）
- 材料：`human-gold-key-facts-review.md`
- 依据：`source/phase3d_doc.md`（SHA-256 `737f6bd3…`）、`annotation-spec.md`
