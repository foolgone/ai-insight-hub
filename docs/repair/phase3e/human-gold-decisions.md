# Phase 3E 人工 Gold 复核结论（2026-11-16）

> **范围**：8 条基础数据（Q23/Q36/Q14/Q15/Q16/Q19/Q37/Q40）+ 1 条 Claim（Q21#3）+ 5 条抽查（Q05/Q13/Q22/Q30/Q35）。
> **签署说明**：复核人 **江晚**；结论由 AI 按委托起草，经用户确认后署名，对应 `human_reviewer=江晚`。
> **未做**：未改 Prompt/Agent/Schema/API/DB，未运行 Judge，未生成 `human-gold.json`，未修改 `human-gold.template.json`。

---

## 1. 结论总表

| ID | 范围 | 决定 | 最终标签 | 要点 |
|---|---|---|---|---|
| Q23 | 基础 | `rewrite`（题干） | constraint / answerable | 题干改“超过 24 小时（如第 2 天）”，不再默认第 2 天必满 24 小时 |
| Q36 | 基础 | `use_subagent_correction` | ambiguous | 补全四个条件分支；§1/§12 虚拟商品口径冲突不选边，答案内披露 |
| Q14 | 基础 | `accept_current` | multi / **ambiguous** | 答案两分支正确；问句缺“是否已开具” |
| Q15 | 基础 | `accept_current` | **direct** / answerable | §5 单事实，`multi` 改 `direct` |
| Q16 | 基础 | `accept_current` | **constraint** / answerable | 条件在问句中且答案只在条件下成立，`multi` 改 `constraint` |
| Q19 | 基础 | `accept_current` | multi / **ambiguous** | 答案两分支正确；问句缺“是否过期” |
| Q37 | 基础 | `use_subagent_correction` | ambiguous | 删除文档外“在订单中申请/填写抬头”，只保留 §4 事实 + 分支 |
| Q40 | 基础 | `rewrite`（题干） | **direct** / **answerable** | 改为“积分可以转让或提现吗？”，避开与 Q20 重复 |
| Q21#3 | Claim | `accept_current` | **insufficient_evidence** | 7 天只限定无理由退款，但文档未给质量问题退换期限，不能判 supported |
| Q05 | 抽查 | `accept_current` | direct / answerable | §4 逐字支持 24 小时、下单邮箱 |
| Q13 | 抽查 | `accept_current` | multi / answerable | §3 逐字支持先寄回、验收后 48 小时 |
| Q22 | 抽查 | `accept_current` | constraint / answerable | 89 元未包邮 + 新疆偏远地区 20 元 |
| Q30 | 抽查 | `accept_current` | unanswerable | 全文无海外配送表述，空证据合规 |
| Q35 | 抽查 | `use_subagent_correction` | ambiguous | 删除“收货地区”缺项，区分发货时效与到货时间 |

备选 Q09、Q18、Q38 本次未纳入。

---

## 2. 需要在生成 Gold 时同步的变更

| ID | 字段 | 原值 | 新值 |
|---|---|---|---|
| Q15 | `category` | multi | direct |
| Q16 | `category` | multi | constraint |
| Q14 | `answerability` | answerable | ambiguous |
| Q19 | `answerability` | answerable | ambiguous |
| Q23 | `question` | 生鲜食品签收后第 2 天发现质量问题，还能按政策反馈吗？ | 生鲜食品签收后超过 24 小时（如第 2 天）发现质量问题，还能按政策反馈吗？ |
| Q40 | `question` | 积分怎么用？ | 积分可以转让或提现吗？ |
| Q40 | `category` / `answerability` | ambiguous / ambiguous | direct / answerable |

说明：复核表没有 `human_question` / `human_category` / `human_answerability` 列，以上变更写在对应行的 `human_reason`（前缀 `STEM_CHANGE`，标签用 `category=` / `answerability=`）；生成 Gold 时必须同步，否则标签与答案会不一致。

---

## 3. 分类覆盖变化

| 类别 | 复核前 | 复核后 |
|---|---:|---:|
| direct | 10 | 12 |
| multi | 10 | 8 |
| constraint | 8 | 9 |
| unanswerable | 6 | 6 |
| ambiguous | 6 | 5 |
| **合计** | **40** | **40** |

判断原则是标签服从内容，不为保持 10/10/8/6/6 而保留错误分类。若验收要求覆盖比例，建议替换 2 条 direct 为真正 multi-hop、1 条 direct 为 ambiguous，而不是回改标签。

---

## 4. 未关闭事项

1. **Q36 知识库口径**：§1“已激活的虚拟商品”vs §12“虚拟商品一经售出”需业务确认 canonical 口径；本条 Gold 已按 ambiguous 保留两处原文，不阻塞使用。
2. **Human Gold 签核**：复核人已署名“江晚”；结论由 AI 起草、用户确认署名。如需更严格的审计，可补充逐条签核时间。
3. **未生成 `human-gold.json`**：`human-gold.template.json` 未改，40 条候选未合并人工结论。
4. **Judge 未运行**：v1.1.0 仍为 `pending_review`，10 条对照与 40 条评测均未执行。
5. **Q23 / Q40 题干变更**：目前只记录在复核表 `human_reason`，需在候选集/最终 Gold 中落地。
6. **范围未覆盖**：40 条基础中仍有 27 条未复核；35 条 Pilot Claim 中只复核了 Q21#3。`pending-review.md` 其余状态未变。
7. **旧表未同步**：早前的 `human-review-pilot.csv`、`human-review-remaining.csv`、`pilot-claims-review.csv` 仍为空；若下游仍以这些表为准，需回填或改为只读归档。

---

## 5. 复核依据

- 原文：`docs/repair/phase3e/source/phase3d_doc.md`，SHA-256 `737f6bd3ef412d41d14ada4d2000bd01e851355f0d95cd0d321ac84416f9002d`
- 规范：`docs/repair/phase3e/annotation-spec.md`
- 工作台：`docs/repair/phase3e/human-gold-review-workbench.md`
- 结论表：`human-gold-review-base.csv`（13 行：8 基础 + 5 抽查）、`human-gold-review-claim.csv`（1 行）
- 所有 `human_corrected_evidence` 已用脚本逐字校验，均可在原文中找到；Q30 按 unanswerable 规则留空。

---

## 6. 已固化（2026-11-16）

- `human-gold.json`：13 条基础 + Q21#3，`provenance=human_gold`，含最终题干/类别/答案/Evidence/answerability；
- `human-gold.pending.json`：27 条未复核基础，`human=null` / `pending_human`；
- `human-gold-status.md`：覆盖变化、题干改写、key_facts 缺口与下一步；
- 旧 `human-review-*.csv` / `pilot-claims-review.csv` 保留为 AI 草稿/模板，下游以 `human-gold.json` 为准。

未改 Prompt/Agent/Schema/API/DB，未运行 Judge；v1.1.0 仍 `pending_review`。

---

## 7. key_facts 已写入 Human Gold（2026-11-16）

- `human-gold.json` 的 13 条基础数据已写入 key_facts：
  - 最终 **41 条**；`supported` 38 / `evidence_insufficient` 2 / `ambiguous` 1；
  - 45 条候选 → accept 38 / modify 3 / delete 4；
  - `key_facts_status=human_reviewed`，reviewer=江晚，reviewed_at=2026-11-16；
  - 逐条证据保留在 `key_fact_details`。
- 删除：Q23-F4、Q15-F1、Q16-F1、Q22-F4；改写：Q23-F2、Q36-F3、Q16-F2。
- absence：Q30-F1、Q35-F5；conflict：Q36-F8。
- 决策记录：`human-gold-key-facts-decisions.md`；审核表：`human-gold-key-facts-review*.csv/json`。
- Human Gold 一致性审计复跑：**424/424 通过**。
- 未改 Prompt/Agent/Schema/API/DB，未运行 Judge。
