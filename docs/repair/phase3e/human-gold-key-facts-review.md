# Phase 3E-H · Human Gold key_facts 人工审核工作表

> **2026-11-16 复核完成**：45 条候选已逐条判断（38 accept / 3 modify / 4 delete），最终 41 条；结论见 `human-gold-key-facts-decisions.md`，逐条结果见三份表。以下“留空”为材料原貌。
> **性质（原始）**：AI 候选，不是 Human Gold。`human_*` 字段全部为空，`review_status=pending_human`。
> **未改** `human-gold.json`、pending 数据、Prompt、Agent、Schema、API、DB；**未运行 Judge**。
> **来源**：`source/phase3d_doc.md`（SHA-256 `737f6bd3…`）。

## 汇总

- 覆盖：13 条 human_reviewed 基础数据
- 候选 key_facts：45 条
- 证据状态：`supported` 42 / `evidence_insufficient` 2 / `ambiguous` 1
- 证据缺失项：Q30-F1（海外配送未提及）、Q35-F5（运输/送达时长未说明）
- 歧义项：Q36-F8（§1 与 §12 虚拟商品口径冲突）

> **重要**：当前 Correctness Prompt 只使用 `gold_answer`，不读取 `key_facts`；本工作表不会改变任何 Judge 分数。

---

## Q23

**Gold Answer**：不能按该条款反馈。生鲜食品质量问题需在签收后 24 小时内拍照反馈，超过 24 小时反馈不符合该条款。

**整体证据状态**：`supported`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q23-F1 | 生鲜食品的质量问题需在签收后 24 小时内反馈 | `supported` | phase3d_doc.md §12 特殊商品 | 原文直接规定 24 小时时限 |
| Q23-F2 | 反馈方式为拍照反馈 | `supported` | phase3d_doc.md §12 特殊商品 | 原文明确“拍照反馈” |
| Q23-F3 | 超过 24 小时反馈不符合该条款 | `supported` | phase3d_doc.md §12 特殊商品 | 由“需在 24 小时内”直接推出；属条件否定 |
| Q23-F4 | 该 24 小时时限适用于生鲜食品的质量问题 | `supported` | phase3d_doc.md §12 特殊商品 | 原文把时限限定在生鲜食品质量问题 |

**证据摘录**：

- `Q23-F1`：> 生鲜食品签收后不支持无理由退货，质量问题需在签收后 24 小时内拍照反馈。
- `Q23-F2`：> 生鲜食品签收后不支持无理由退货，质量问题需在签收后 24 小时内拍照反馈。
- `Q23-F3`：> 生鲜食品签收后不支持无理由退货，质量问题需在签收后 24 小时内拍照反馈。
- `Q23-F4`：> 生鲜食品签收后不支持无理由退货，质量问题需在签收后 24 小时内拍照反馈。

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## Q36

**Gold Answer**：需要确认商品类型、签收时间、是否已激活、是否存在质量问题。按文档：普通商品签收后 7 天内可申请无理由退款；定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款；生鲜食品质量问题需在签收后 24 小时内拍照反馈；虚拟商品（充值、会员、课程）一经售出不支持退款；定制商品支持质量问题退换，不支持无理由退换。注意：第 1 条对虚拟商品的限定是「已激活」，第 12 条则称虚拟商品一经售出不支持退款，两处范围不完全一致，具体商品需以对应条款/客服确认为准。

**整体证据状态**：`mixed`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q36-F1 | 普通商品签收后 7 天内可申请无理由退款 | `supported` | phase3d_doc.md §1 退款时效 | 原文直接支持 |
| Q36-F2 | 定制类商品不支持无理由退款 | `supported` | phase3d_doc.md §1 退款时效 | 原文直接支持 |
| Q36-F3 | 生鲜食品不支持无理由退款 | `supported` | phase3d_doc.md §1 退款时效 | 原文直接支持 |
| Q36-F4 | 已激活的虚拟商品不支持无理由退款 | `supported` | phase3d_doc.md §1 退款时效 | 原文直接支持，限定词是“已激活” |
| Q36-F5 | 生鲜食品质量问题需在签收后 24 小时内拍照反馈 | `supported` | phase3d_doc.md §12 特殊商品 | 原文直接支持 |
| Q36-F6 | 虚拟商品（充值、会员、课程）一经售出不支持退款 | `supported` | phase3d_doc.md §12 特殊商品 | 原文直接支持，未限定“已激活” |
| Q36-F7 | 定制商品支持质量问题退换，不支持无理由退换 | `supported` | phase3d_doc.md §12 特殊商品 | 原文直接支持 |
| Q36-F8 | §1 与 §12 对虚拟商品范围的表述不一致：§1 限定“已激活”，§12 称“一经售出” | `ambiguous` | phase3d_doc.md §1；§12 原文见 ai_reason | §1 原文为“定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。”；§12 原文为“虚拟商品（充值、会员、课程）一经售出不支持退款。”；两处范围不一致，需业务确认 canonical 口径 |

**证据摘录**：

- `Q36-F1`：> 订单签收后 7 天内可申请无理由退款。审核通过后，款项将在 1-3 个工作日内原路退回。
- `Q36-F2`：> 定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。
- `Q36-F3`：> 定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。
- `Q36-F4`：> 定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。
- `Q36-F5`：> 生鲜食品签收后不支持无理由退货，质量问题需在签收后 24 小时内拍照反馈。
- `Q36-F6`：> 虚拟商品（充值、会员、课程）一经售出不支持退款。
- `Q36-F7`：> 定制商品支持质量问题退换，不支持无理由退换。
- `Q36-F8`：> 定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## Q14

**Gold Answer**：未开具前可以修改；已开具的发票需先申请红冲，再重新开具。

**整体证据状态**：`supported`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q14-F1 | 发票抬头可在开具前修改 | `supported` | phase3d_doc.md §4 发票说明 | 原文直接支持 |
| Q14-F2 | 已开具的发票需先申请红冲，再重新开具 | `supported` | phase3d_doc.md §4 发票说明 | 原文直接支持 |

**证据摘录**：

- `Q14-F1`：> 发票抬头可在开具前修改；已开具的发票需先申请红冲，再重新开具。
- `Q14-F2`：> 发票抬头可在开具前修改；已开具的发票需先申请红冲，再重新开具。

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## Q15

**Gold Answer**：会，配送前会电话预约。

**整体证据状态**：`supported`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q15-F1 | 大件商品包括家具、家电 | `supported` | phase3d_doc.md §5 发货时效 | 原文括号内列出家具、家电 |
| Q15-F2 | 大件商品配送前会电话预约 | `supported` | phase3d_doc.md §5 发货时效 | 原文直接支持 |

**证据摘录**：

- `Q15-F1`：> 大件商品（家具、家电）发货时间为 5 个工作日内，配送前会电话预约。
- `Q15-F2`：> 大件商品（家具、家电）发货时间为 5 个工作日内，配送前会电话预约。

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## Q16

**Gold Answer**：可联系客服协助核查。

**整体证据状态**：`supported`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q16-F1 | 物流信息超过 24 小时未更新是联系客服核查的触发条件 | `supported` | phase3d_doc.md §6 物流查询 | 原文直接规定条件 |
| Q16-F2 | 触发后可联系客服协助核查 | `supported` | phase3d_doc.md §6 物流查询 | 原文直接支持 |

**证据摘录**：

- `Q16-F1`：> 物流信息超过 24 小时未更新时，可联系客服协助核查。
- `Q16-F2`：> 物流信息超过 24 小时未更新时，可联系客服协助核查。

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## Q19

**Gold Answer**：优惠券若仍在有效期内会退回账户，已过期则不退回。

**整体证据状态**：`supported`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q19-F1 | 退款时优惠券仍在有效期内会退回账户 | `supported` | phase3d_doc.md §9 优惠券规则 | 原文直接支持 |
| Q19-F2 | 退款时优惠券已过期则不退回 | `supported` | phase3d_doc.md §9 优惠券规则 | 原文直接支持 |

**证据摘录**：

- `Q19-F1`：> 退款时优惠券若仍在有效期内会退回账户，已过期则不退回。
- `Q19-F2`：> 退款时优惠券若仍在有效期内会退回账户，已过期则不退回。

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## Q37

**Gold Answer**：信息不足：需明确是申请开票、修改抬头还是红冲重开。文档说明仅支持电子发票，提交申请后 24 小时内发送至下单邮箱；发票抬头可在开具前修改，已开具的发票需先申请红冲，再重新开具；暂不支持纸质发票和增值税专用发票。

**整体证据状态**：`supported`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q37-F1 | 仅支持电子发票 | `supported` | phase3d_doc.md §4 发票说明 | 原文直接支持 |
| Q37-F2 | 提交申请后 24 小时内发送至下单邮箱 | `supported` | phase3d_doc.md §4 发票说明 | 原文直接支持 |
| Q37-F3 | 发票抬头可在开具前修改 | `supported` | phase3d_doc.md §4 发票说明 | 原文直接支持 |
| Q37-F4 | 已开具的发票需先申请红冲，再重新开具 | `supported` | phase3d_doc.md §4 发票说明 | 原文直接支持 |
| Q37-F5 | 不支持纸质发票和增值税专用发票 | `supported` | phase3d_doc.md §4 发票说明 | 原文直接支持 |

**证据摘录**：

- `Q37-F1`：> 仅支持电子发票，提交申请后 24 小时内发送至下单邮箱。
- `Q37-F2`：> 仅支持电子发票，提交申请后 24 小时内发送至下单邮箱。
- `Q37-F3`：> 发票抬头可在开具前修改；已开具的发票需先申请红冲，再重新开具。
- `Q37-F4`：> 发票抬头可在开具前修改；已开具的发票需先申请红冲，再重新开具。
- `Q37-F5`：> 暂不支持纸质发票和增值税专用发票。

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## Q40

**Gold Answer**：不可以。积分不可转让、不可提现，仅限本账户使用。

**整体证据状态**：`supported`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q40-F1 | 积分不可转让 | `supported` | phase3d_doc.md §10 会员积分 | 原文直接支持 |
| Q40-F2 | 积分不可提现 | `supported` | phase3d_doc.md §10 会员积分 | 原文直接支持 |
| Q40-F3 | 积分仅限本账户使用 | `supported` | phase3d_doc.md §10 会员积分 | 原文直接支持 |

**证据摘录**：

- `Q40-F1`：> 积分不可转让、不可提现，仅限本账户使用。
- `Q40-F2`：> 积分不可转让、不可提现，仅限本账户使用。
- `Q40-F3`：> 积分不可转让、不可提现，仅限本账户使用。

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## Q05

**Gold Answer**：提交申请后 24 小时内发送至下单邮箱。

**整体证据状态**：`supported`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q05-F1 | 发票提交申请后 24 小时内发送 | `supported` | phase3d_doc.md §4 发票说明 | 原文直接支持 |
| Q05-F2 | 发票发送至下单邮箱 | `supported` | phase3d_doc.md §4 发票说明 | 原文直接支持 |

**证据摘录**：

- `Q05-F1`：> 仅支持电子发票，提交申请后 24 小时内发送至下单邮箱。
- `Q05-F2`：> 仅支持电子发票，提交申请后 24 小时内发送至下单邮箱。

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## Q13

**Gold Answer**：需要先寄回原商品；商家收到并验收后 48 小时内寄出新品。

**整体证据状态**：`supported`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q13-F1 | 换货需先寄回原商品 | `supported` | phase3d_doc.md §3 换货政策 | 原文直接支持 |
| Q13-F2 | 商家需收到并验收原商品 | `supported` | phase3d_doc.md §3 换货政策 | 原文直接支持；是新品寄出的前提 |
| Q13-F3 | 验收后 48 小时内寄出新品 | `supported` | phase3d_doc.md §3 换货政策 | 原文直接支持 |

**证据摘录**：

- `Q13-F1`：> 换货需先寄回原商品，商家收到并验收后 48 小时内寄出新品；运费由责任方承担。
- `Q13-F2`：> 换货需先寄回原商品，商家收到并验收后 48 小时内寄出新品；运费由责任方承担。
- `Q13-F3`：> 换货需先寄回原商品，商家收到并验收后 48 小时内寄出新品；运费由责任方承担。

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## Q22

**Gold Answer**：20 元。新疆属于偏远地区，运费 20 元且不参与包邮。

**整体证据状态**：`supported`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q22-F1 | 新疆属于偏远地区 | `supported` | phase3d_doc.md §7 运费规则 | 原文将新疆列入偏远地区 |
| Q22-F2 | 偏远地区运费为 20 元 | `supported` | phase3d_doc.md §7 运费规则 | 原文直接支持 |
| Q22-F3 | 偏远地区不参与包邮活动 | `supported` | phase3d_doc.md §7 运费规则 | 原文直接支持 |
| Q22-F4 | 订单实付 89 元未满 99 元包邮门槛 | `supported` | phase3d_doc.md §7 运费规则 | 89 < 99，由包邮门槛直接推出；不是外部知识 |

**证据摘录**：

- `Q22-F1`：> 新疆、西藏、内蒙古等偏远地区运费为 20 元，不参与包邮活动。
- `Q22-F2`：> 新疆、西藏、内蒙古等偏远地区运费为 20 元，不参与包邮活动。
- `Q22-F3`：> 新疆、西藏、内蒙古等偏远地区运费为 20 元，不参与包邮活动。
- `Q22-F4`：> 单笔订单实付满 99 元包邮；未满 99 元收取 10 元运费。

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## Q30

**Gold Answer**：文档未说明是否支持海外配送，无法确认。

**整体证据状态**：`evidence_insufficient`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q30-F1 | 文档未说明是否支持海外配送 | `evidence_insufficient` | phase3d_doc.md 全文 §1–§13 | 全文没有海外/跨境配送表述；这是 absence 事实，无法提供肯定证据；按 unanswerable 处理 |

**证据摘录**：

- `Q30-F1`：**无肯定证据**（absence fact；见 ai_reason）

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## Q35

**Gold Answer**：需要区分「发货」和「到货」：文档只规定发货时效——现货商品付款后 48 小时内发出，预售商品以商品页标注时间为准，大件商品 5 个工作日内发出且配送前电话预约；文档未说明快递运输/送达需要多久。发货后可在「我的订单」查看物流轨迹，超过 24 小时未更新可联系客服。若问的是到货时间，仅凭文档无法给出具体时间。

**整体证据状态**：`mixed`

| Fact ID | 候选 key_fact | 证据状态 | 证据位置 | AI 理由 |
|---|---|---|---|---|
| Q35-F1 | 现货商品付款后 48 小时内发出 | `supported` | phase3d_doc.md §5 发货时效 | 原文直接支持 |
| Q35-F2 | 预售商品以商品页标注的发货时间为准 | `supported` | phase3d_doc.md §5 发货时效 | 原文直接支持 |
| Q35-F3 | 大件商品发货时间为 5 个工作日内 | `supported` | phase3d_doc.md §5 发货时效 | 原文直接支持 |
| Q35-F4 | 大件商品配送前电话预约 | `supported` | phase3d_doc.md §5 发货时效 | 原文直接支持 |
| Q35-F5 | 文档未说明快递运输/送达需要多久 | `evidence_insufficient` | phase3d_doc.md 全文（§5 只有发货时效，§6 只有查询方式） | absence 事实；不能把“发货时效”当成“到货时效” |
| Q35-F6 | 发货后可在「我的订单」查看物流单号与实时轨迹 | `supported` | phase3d_doc.md §6 物流查询 | 原文直接支持 |
| Q35-F7 | 物流信息超过 24 小时未更新可联系客服核查 | `supported` | phase3d_doc.md §6 物流查询 | 原文直接支持 |

**证据摘录**：

- `Q35-F1`：> 现货商品在付款后 48 小时内发出；预售商品以商品页标注的发货时间为准。
- `Q35-F2`：> 现货商品在付款后 48 小时内发出；预售商品以商品页标注的发货时间为准。
- `Q35-F3`：> 大件商品（家具、家电）发货时间为 5 个工作日内，配送前会电话预约。
- `Q35-F4`：> 大件商品（家具、家电）发货时间为 5 个工作日内，配送前会电话预约。
- `Q35-F5`：**无肯定证据**（absence fact；见 ai_reason）
- `Q35-F6`：> 订单发货后可在「我的订单」查看物流单号与实时轨迹。
- `Q35-F7`：> 物流信息超过 24 小时未更新时，可联系客服协助核查。

**人工审核（留空）**：

- `human_decision`：________（accept / modify / delete / needs_recheck）
- `human_corrected_key_facts`：________（JSON 数组或逐条列出）
- `human_reason`：________
- `review_status`：`pending_human`

---

## 需要用户决定的问题

1. **Q30**：是否保留“文档未说明海外配送”这一 absence key_fact？若保留，`evidence_status=evidence_insufficient`；若不保留，则该题无 key_facts，仅靠 answerability=unanswerable。
2. **Q35-F5**：是否保留“文档未说明运输/送达时长”这一 absence key_fact？它与 Q35 区分“发货 vs 到货”的核心结论直接相关。
3. **Q36-F8**：是否把 §1/§12 虚拟商品口径冲突作为 key_fact？若保留，标 `ambiguous`；若只作为 notes，则删除该 fact。
4. **Q23-F3**：“超过 24 小时反馈不符合该条款”是由时限条件直接否定推出，是否接受为独立 key_fact？
5. **Q22-F4**：“89 元未满 99 元包邮门槛”是算术推导，是否接受为 key_fact？
6. **Q37**：文档未写申请入口/填写抬头步骤，是否需要在 key_facts 中显式保留一个 `evidence_insufficient` 的 absence fact？当前未列入。
7. **粒度**：当前按“时间/条件/例外/结论”拆成 45 条；是否还需要进一步拆分或合并？
8. **用途**：当前 Judge 不读取 key_facts；如果未来希望 Correctness 使用 key_facts，需要另开 Prompt/Schema 设计，不在本阶段。

## 文件

- 本页：`human-gold-key-facts-review.md`
- 逐条编辑（推荐）：`human-gold-key-facts-review-long.csv`（45 行）
- 按 item 汇总：`human-gold-key-facts-review.csv`（13 行）
- 机器可读：`human-gold-key-facts-review.json`

## 禁止事项

- 不得把本表候选直接写入 `human-gold.json`；
- 不得因 Judge 分数反向调整 key_facts；
- 不得修改 Prompt/Agent/Schema/API/DB；
- 不得运行 Judge 或 10 条/40 条评测。
