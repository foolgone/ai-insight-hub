# Phase 3E 人工 Gold 复核工作台

> **2026-11-16 复核完成**：8 条基础 + 1 条 Claim + 5 条抽查已完成判断，结论以 `human-gold-review-base.csv` / `human-gold-review-claim.csv` 为准，逐条说明见 `human-gold-decisions.md`。以下“请填写/保持空白”为材料原貌，不再代表当前状态。
> **性质（原始）**：材料整理，不是人工审核结论。所有 `human_*` 字段为空，等待用户本人判断。
> **来源文档**：`docs/repair/phase3e/source/phase3d_doc.md`（SHA-256 `737f6bd3…`，与本地 WeKnora KB 中 `phase3d_doc.md` 对应）。
> **机器可编辑表**：`human-gold-review-base.csv`（8 条）、`human-gold-review-claim.csv`（1 条）。

---

## 一、8 条基础数据

### Q23 · constraint

- **原始问题**：生鲜食品签收后第 2 天发现质量问题，还能按政策反馈吗？
- **当前参考答案**：不能按该条款反馈。生鲜质量问题需在签收后 24 小时内拍照反馈，第 2 天已超过时限。
- **当前 Gold Evidence**：`[{"section": "12. 特殊商品", "quote": "生鲜食品签收后不支持无理由退货，质量问题需在签收后 24 小时内拍照反馈。虚拟商品（充值、会员、课程）一经售出不支持退款。定制商品支持质量问题退换，不支持无理由退换。"}]`
- **原文位置**：phase3d_doc.md §12. 特殊商品
- **原文摘录**：

  > 生鲜食品签收后不支持无理由退货，质量问题需在签收后 24 小时内拍照反馈。

- **文档冲突/风险**：无文档冲突；但“第 2 天”跨午夜时可能未满 24 小时，属题干时间边界歧义。
- **Subagent 状态**：`needs_recheck`
- **Subagent 修正答案**：不能按该条款反馈。生鲜质量问题需在签收后 24 小时内拍照反馈，第 2 天已超过时限。
- **Subagent 理由**：按「签收后第 2 天」的通常理解（已超过 24 小时）答案正确；但若签收时间较晚，「第 2 天」跨午夜时可能仍未满 24 小时，存在边界歧义。建议题干改为「签收后超过 24 小时（如第 2 天）」或明确具体小时数后再定稿。
- **AI 建议方向（待选，不是结论）**：A（推荐干净约束题）：题干改为“生鲜食品签收后超过 24 小时（如第 2 天）发现质量问题，还能按政策反馈吗？”；B：保留题干，answerability 改 ambiguous，答案写“需先确认是否超过 24 小时”；不得默认“第 2 天”必满 24 小时。

**人工决策（请填写，保持空白）**：

- [ ] 接受当前答案 / [ ] 使用 Subagent 修正答案 / [ ] 自行改写 / [ ] 标 needs_recheck / [ ] 拒绝
- `human_decision`：________
- `human_corrected_answer`：________
- `human_corrected_evidence`：________
- `human_reason`：________
- `human_reviewer`：________
- `review_status`：`pending_human`（审核后改为 `human_reviewed` / `needs_recheck`）

---

### Q36 · ambiguous

- **原始问题**：能退吗？
- **当前参考答案**：信息不足：需要商品类型、签收时间、是否定制/生鲜/虚拟商品才能判断。
- **当前 Gold Evidence**：`[{"section": "1. 退款时效", "quote": "订单签收后 7 天内可申请无理由退款。审核通过后，款项将在 1-3 个工作日内原路退回。定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。"}, {"section": "12. 特殊商品", "quote": "生鲜食品签收后不支持无理由退货，质量问题需在签收后 24 小时内拍照反馈。虚拟商品（充值、会员、课程）一经售出不支持退款。定制商品支持质量问题退换，不支持无理由退换。"}]`
- **原文位置**：phase3d_doc.md §1. 退款时效；12. 特殊商品
- **原文摘录**：

  > §1：定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。
  > §12：虚拟商品（充值、会员、课程）一经售出不支持退款。

- **文档冲突/风险**：存在文档口径冲突：§1 限定“已激活的虚拟商品”，§12 称“虚拟商品一经售出”均不支持退款；范围不一致。
- **Subagent 状态**：`needs_recheck`
- **Subagent 修正答案**：需要确认商品类型、签收时间、是否已激活、是否存在质量问题。按文档：普通商品签收后 7 天内可申请无理由退款；定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款；生鲜食品质量问题需在签收后 24 小时内拍照反馈；虚拟商品（充值、会员、课程）一经售出不支持退款；定制商品支持质量问题退换，不支持无理由退换。注意：第 1 条对虚拟商品的限定是「已激活」，第 12 条则称虚拟商品一经售出不支持退款，两处范围不完全一致，具体商品需以对应条款/客服确认为准。
- **Subagent 理由**：原答案只说「信息不足」，未给出任何条件分支，且「是否定制/生鲜/虚拟商品」与「商品类型」重复，漏掉「是否已激活」和「是否存在质量问题」。已补全条件分支。另文档自身对虚拟商品的口径不一致（第 1 条「已激活」vs 第 12 条「一经售出」），建议人工确认 canonical 口径后再定稿。
- **AI 建议方向（待选，不是结论）**：不得强行生成唯一 Gold。保留 ambiguous + 条件分支，并标记 needs_recheck；可选：由业务确认虚拟商品 canonical 口径，或把题干改为具体商品类型（如“已激活的会员充值能退吗？”）。

**人工决策（请填写，保持空白）**：

- [ ] 接受当前答案 / [ ] 使用 Subagent 修正答案 / [ ] 自行改写 / [ ] 标 needs_recheck / [ ] 拒绝
- `human_decision`：________
- `human_corrected_answer`：________
- `human_corrected_evidence`：________
- `human_reason`：________
- `human_reviewer`：________
- `review_status`：`pending_human`（审核后改为 `human_reviewed` / `needs_recheck`）

---

### Q14 · multi

- **原始问题**：发票抬头开错了可以改吗？
- **当前参考答案**：未开具前可以修改；已开具的发票需先申请红冲，再重新开具。
- **当前 Gold Evidence**：`[{"section": "4. 发票说明", "quote": "仅支持电子发票，提交申请后 24 小时内发送至下单邮箱。发票抬头可在开具前修改；已开具的发票需先申请红冲，再重新开具。暂不支持纸质发票和增值税专用发票。"}]`
- **原文位置**：phase3d_doc.md §4. 发票说明
- **原文摘录**：

  > 发票抬头可在开具前修改；已开具的发票需先申请红冲，再重新开具。

- **文档冲突/风险**：无文档冲突；问句缺少“是否已开具”，答案必须条件分支。
- **Subagent 状态**：`needs_recheck`
- **Subagent 修正答案**：未开具前可以修改；已开具的发票需先申请红冲，再重新开具。
- **Subagent 理由**：参考答案准确覆盖第 4 节的两个分支（开具前可改；已开具先红冲再重开），gold evidence 逐字匹配。但问句未说明发票是否已开具，无法给出单一 yes/no，按 annotation-spec 的 ambiguous 定义（缺少必要信息、需条件分支）应标 ambiguous 而非 answerable；参考答案已给条件分支，符合 ambiguous 的答案要求。category=multi 可保留为两分支题，建议人工确认 answerability。
- **AI 建议方向（待选，不是结论）**：答案有 §4 依据。A：按规范标 ambiguous（缺“是否已开具”）；B：改题干为“发票已开具，抬头开错了怎么办？”使其 answerable；C：保留 answerable 但答案必须条件分支。

**人工决策（请填写，保持空白）**：

- [ ] 接受当前答案 / [ ] 使用 Subagent 修正答案 / [ ] 自行改写 / [ ] 标 needs_recheck / [ ] 拒绝
- `human_decision`：________
- `human_corrected_answer`：________
- `human_corrected_evidence`：________
- `human_reason`：________
- `human_reviewer`：________
- `review_status`：`pending_human`（审核后改为 `human_reviewed` / `needs_recheck`）

---

### Q15 · multi

- **原始问题**：大件商品配送前会联系买家吗？
- **当前参考答案**：会，配送前会电话预约。
- **当前 Gold Evidence**：`[{"section": "5. 发货时效", "quote": "现货商品在付款后 48 小时内发出；预售商品以商品页标注的发货时间为准。大件商品（家具、家电）发货时间为 5 个工作日内，配送前会电话预约。"}]`
- **原文位置**：phase3d_doc.md §5. 发货时效
- **原文摘录**：

  > 大件商品（家具、家电）发货时间为 5 个工作日内，配送前会电话预约。

- **文档冲突/风险**：无文档冲突；仅 category=multi 与单事实问句不匹配。
- **Subagent 状态**：`needs_recheck`
- **Subagent 修正答案**：会，配送前会电话预约。
- **Subagent 理由**：答案“会，配送前会电话预约”由第 5 节直接支持（原文“配送前会电话预约”），answerable。问题本身清晰；仅 category=multi 不合适，建议改 direct。与 Q07 共享电话预约事实，但 Q07 问发货时长，本条问是否联系，问句不同。
- **AI 建议方向（待选，不是结论）**：A：改 category=direct（会影响 10/10/8/6/6 覆盖）；B：换成真正的 multi-hop 题；C：保留 multi 并记录分类偏差。

**人工决策（请填写，保持空白）**：

- [ ] 接受当前答案 / [ ] 使用 Subagent 修正答案 / [ ] 自行改写 / [ ] 标 needs_recheck / [ ] 拒绝
- `human_decision`：________
- `human_corrected_answer`：________
- `human_corrected_evidence`：________
- `human_reason`：________
- `human_reviewer`：________
- `review_status`：`pending_human`（审核后改为 `human_reviewed` / `needs_recheck`）

---

### Q16 · multi

- **原始问题**：物流信息超过 24 小时没更新怎么办？
- **当前参考答案**：可联系客服协助核查。
- **当前 Gold Evidence**：`[{"section": "6. 物流查询", "quote": "订单发货后可在「我的订单」查看物流单号与实时轨迹。物流信息超过 24 小时未更新时，可联系客服协助核查。"}]`
- **原文位置**：phase3d_doc.md §6. 物流查询
- **原文摘录**：

  > 物流信息超过 24 小时未更新时，可联系客服协助核查。

- **文档冲突/风险**：无文档冲突；条件已在问句中，category=multi 不合适。
- **Subagent 状态**：`needs_recheck`
- **Subagent 修正答案**：可联系客服协助核查。
- **Subagent 理由**：答案“可联系客服协助核查”由第 6 节直接支持，条件“超过 24 小时未更新”已在问句中给出，answerable。问题本身清晰；仅 category=multi 不合适，建议改 direct 或 constraint。
- **AI 建议方向（待选，不是结论）**：A：改 category=constraint 或 direct；B：换成 multi-hop；C：保留并记录分类偏差。

**人工决策（请填写，保持空白）**：

- [ ] 接受当前答案 / [ ] 使用 Subagent 修正答案 / [ ] 自行改写 / [ ] 标 needs_recheck / [ ] 拒绝
- `human_decision`：________
- `human_corrected_answer`：________
- `human_corrected_evidence`：________
- `human_reason`：________
- `human_reviewer`：________
- `review_status`：`pending_human`（审核后改为 `human_reviewed` / `needs_recheck`）

---

### Q19 · multi

- **原始问题**：退款后优惠券会退回吗？
- **当前参考答案**：优惠券若仍在有效期内会退回账户，已过期则不退回。
- **当前 Gold Evidence**：`[{"section": "9. 优惠券规则", "quote": "优惠券自领取之日起 30 天内有效，逾期自动失效。同一订单只能使用一张优惠券，不能与会员折扣叠加。退款时优惠券若仍在有效期内会退回账户，已过期则不退回。"}]`
- **原文位置**：phase3d_doc.md §9. 优惠券规则
- **原文摘录**：

  > 退款时优惠券若仍在有效期内会退回账户，已过期则不退回。

- **文档冲突/风险**：无文档冲突；问句缺少“优惠券是否过期”，答案必须条件分支。
- **Subagent 状态**：`needs_recheck`
- **Subagent 修正答案**：优惠券若仍在有效期内会退回账户，已过期则不退回。
- **Subagent 理由**：参考答案准确覆盖第 9 节的两个分支（有效期内退回账户；已过期不退），gold evidence 逐字匹配。但问句未说明优惠券是否仍在有效期，无法给出单一 yes/no，按 annotation-spec 的 ambiguous 定义（缺少必要信息、需条件分支）应标 ambiguous 而非 answerable；参考答案已给条件分支，符合 ambiguous 的答案要求。category=multi 可保留为两分支题，建议人工确认 answerability。
- **AI 建议方向（待选，不是结论）**：A：按规范标 ambiguous（缺“是否过期”）；B：改题干为“优惠券已过期，退款时还会退回吗？”；C：保留 answerable + 条件分支。

**人工决策（请填写，保持空白）**：

- [ ] 接受当前答案 / [ ] 使用 Subagent 修正答案 / [ ] 自行改写 / [ ] 标 needs_recheck / [ ] 拒绝
- `human_decision`：________
- `human_corrected_answer`：________
- `human_corrected_evidence`：________
- `human_reason`：________
- `human_reviewer`：________
- `review_status`：`pending_human`（审核后改为 `human_reviewed` / `needs_recheck`）

---

### Q37 · ambiguous

- **原始问题**：发票怎么弄？
- **当前参考答案**：信息不足：需要订单信息和发票抬头；一般流程是在订单中申请电子发票并填写抬头。
- **当前 Gold Evidence**：`[{"section": "4. 发票说明", "quote": "仅支持电子发票，提交申请后 24 小时内发送至下单邮箱。发票抬头可在开具前修改；已开具的发票需先申请红冲，再重新开具。暂不支持纸质发票和增值税专用发票。"}]`
- **原文位置**：phase3d_doc.md §4. 发票说明
- **原文摘录**：

  > 仅支持电子发票，提交申请后 24 小时内发送至下单邮箱。
  > 发票抬头可在开具前修改；已开具的发票需先申请红冲，再重新开具。
  > 暂不支持纸质发票和增值税专用发票。
  > （文档未说明申请入口、填写抬头步骤）

- **文档冲突/风险**：无文档冲突；当前答案含文档外流程（订单中申请、填写抬头），文档未说明。
- **Subagent 状态**：`needs_recheck`
- **Subagent 修正答案**：信息不足：需明确是申请开票、修改抬头还是红冲重开。文档说明仅支持电子发票，提交申请后 24 小时内发送至下单邮箱；发票抬头可在开具前修改，已开具的发票需先申请红冲，再重新开具；暂不支持纸质发票和增值税专用发票。
- **Subagent 理由**：原文“一般流程是在订单中申请电子发票并填写抬头”属文档外知识：文档只说明仅支持电子发票、24 小时内发送至下单邮箱、抬头可在开具前修改，未写申请入口和填写抬头步骤。已改为仅使用文档事实，并按申请开票/修改抬头/红冲重开给出分支澄清。
- **AI 建议方向（待选，不是结论）**：删除“在订单中申请电子发票并填写抬头”（文档无依据）；保留 §4 事实 + 条件分支（申请开票/修改抬头/红冲重开）；是否标 ambiguous 由人工确认。

**人工决策（请填写，保持空白）**：

- [ ] 接受当前答案 / [ ] 使用 Subagent 修正答案 / [ ] 自行改写 / [ ] 标 needs_recheck / [ ] 拒绝
- `human_decision`：________
- `human_corrected_answer`：________
- `human_corrected_evidence`：________
- `human_reason`：________
- `human_reviewer`：________
- `review_status`：`pending_human`（审核后改为 `human_reviewed` / `needs_recheck`）

---

### Q40 · ambiguous

- **原始问题**：积分怎么用？
- **当前参考答案**：信息不足：需要账户和订单场景；积分 100 分可抵扣 1 元，仅限本账户使用。
- **当前 Gold Evidence**：`[{"section": "10. 会员积分", "quote": "消费 1 元积 1 分，100 积分可抵扣 1 元。积分自获得之日起 12 个月内有效，逾期清零。积分不可转让、不可提现，仅限本账户使用。"}]`
- **原文位置**：phase3d_doc.md §10. 会员积分
- **原文摘录**：

  > 消费 1 元积 1 分，100 积分可抵扣 1 元。
  > 积分自获得之日起 12 个月内有效，逾期清零。
  > 积分不可转让、不可提现，仅限本账户使用。

- **文档冲突/风险**：无文档冲突；与 Q20 知识点/答案高度重叠，属疑似重复。
- **Subagent 状态**：`needs_recheck`
- **Subagent 修正答案**：信息不足：需要账户和订单场景；积分 100 分可抵扣 1 元，仅限本账户使用。
- **Subagent 理由**：答案事实部分可由第 10 节支持，但问句与 Q20 重复，且“需要账户和订单场景”的缺失信息说明较弱；建议删除本条，或改成真正需要澄清的具体问题（如积分能否转赠/提现）。
- **AI 建议方向（待选，不是结论）**：A：删除并保留变更记录；B：改写为真正需要澄清的问题（如积分能否转赠/提现）；C：改写为 unanswerable（如积分过期能否恢复）。不得自行删除。

**人工决策（请填写，保持空白）**：

- [ ] 接受当前答案 / [ ] 使用 Subagent 修正答案 / [ ] 自行改写 / [ ] 标 needs_recheck / [ ] 拒绝
- `human_decision`：________
- `human_corrected_answer`：________
- `human_corrected_evidence`：________
- `human_reason`：________
- `human_reviewer`：________
- `review_status`：`pending_human`（审核后改为 `human_reviewed` / `needs_recheck`）

---

## 二、1 条 Claim（Q21#3）

- **所属问题**：签收后第 10 天，普通商品还能无理由退款吗？
- **Claim**：质量问题不受 7 天无理由限制
- **当前 AI 标签**：`insufficient_evidence`
- **当前 evidence_reference**：``（空）
- **原文位置**：phase3d_doc.md §1 / §3 / §8
- **原文摘录**：

  > §1：订单签收后 7 天内可申请无理由退款。
  > §3：签收后 7 天内，商品未使用且包装完整可申请换货。
  > §8：电子产品自签收之日起保修 12 个月，配件保修 3 个月。

- **文档冲突/风险**：无直接冲突；文档未规定普通商品质量问题退换的期限，§3 换货仍写 7 天。
- **Subagent 状态**：`needs_recheck`
- **Subagent 结论**：`insufficient_evidence`
- **Subagent 理由**：上下文只把 7 天限定在“无理由退款”，未规定普通商品质量问题退换的期限；第 3 节换货仍写 7 天，无法确认“不受限制”。
- **AI 建议方向（待选，不是结论）**：在 supported / insufficient_evidence / needs_recheck 中人工决定。按字面范围“7 天仅约束无理由退款”可判 supported；但作为对用户承诺证据不足；不得把缺乏证据等同于事实错误。

**人工决策（请填写，保持空白）**：

- [ ] supported / [ ] unsupported / [ ] insufficient_evidence / [ ] needs_recheck
- `human_label`：________
- `human_evidence_reference`：________（chunk_id 或原文；没有就留空）
- `human_reason`：________
- `human_reviewer`：________
- `review_status`：`pending_human`（审核后改为 `human_reviewed` / `needs_recheck`）

---

## 三、其余 31 条抽查候选（待用户确认是否纳入）

> 这些只是候选，**尚未**写入人工抽查记录。用户确认后再补 `review_target=spot_check` 行。

| ID | 类型 | 问题 | 推荐理由 | 重点检查 |
|---|---|---|---|---|
| Q05 | direct | 发票提交申请后多久发送？ | 简单事实题，验证 Evidence 是否逐字对应 §4 | 24 小时、下单邮箱 |
| Q13 | multi | 换货需要先寄回原商品吗？新品多久寄出？ | 两个事实点，验证多段综合 | 先寄回、验收后 48 小时 |
| Q22 | constraint | 订单实付 89 元寄往新疆，运费多少？ | 金额 + 地区双条件 | 20 元、偏远地区不包邮 |
| Q30 | unanswerable | 支持海外配送吗？ | 无答案题，验证不编造 | 文档是否完全未提及 |
| Q35 | ambiguous | 多久能到？ | Subagent 已发现并修正“收货地区”误判 | 发货 vs 到货、文档无运输时长 |

备选：Q09（direct 保修）、Q18（multi 保修收费）、Q38（ambiguous 运费）。

---

## 四、填写字段说明

基础表（`human-gold-review-base.csv`）：

| 字段 | 填写要求 |
|---|---|
| `human_decision` | `accept_current` / `use_subagent_correction` / `rewrite` / `needs_recheck` / `reject` |
| `human_corrected_answer` | 人工最终答案；与 current 相同也要显式填写 |
| `human_corrected_evidence` | 原文逐字引用；没有证据就留空，不得编造 |
| `human_reason` | 为什么这样决定；引用章节 |
| `human_reviewer` | 审核人 |
| `review_status` | `human_reviewed` / `needs_recheck` / `pending_human` |

Claim 表（`human-gold-review-claim.csv`）：

| 字段 | 填写要求 |
|---|---|
| `human_decision` | `accept_current` / `change_label` / `needs_recheck` |
| `human_label` | `supported` / `unsupported` / `insufficient_evidence` / `needs_recheck` |
| `human_evidence_reference` | chunk_id 或原文；无证据留空 |
| `human_reason` | 说明证据或缺失证据 |
| `human_reviewer` | 审核人 |
| `review_status` | `human_reviewed` / `needs_recheck` / `pending_human` |

---

## 五、禁止事项

- 不得把 Subagent 的 `ai_reviewed` 直接改成 `human_reviewed`；
- 不得根据 Judge 分数反向修改参考答案；
- 不得在无原文依据时补造 Evidence；
- 不得自行删除/改写题目；如需变更，保留原记录和变更说明；
- 本工作台不改变 Prompt、Agent、Schema、Service、API 或数据库。
