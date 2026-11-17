# 10 条 Pilot：v1.0.0 vs v1.1.1（10/10 完成）

> 同一批 Pilot answer/contexts；v1.1.1 使用 F SHA 3519fd3b…、C SHA 2ab6eac…；只切换 Judge Prompt 版本。
> Faithfulness 只用 `query.contexts`（C1–C2），不使用 retrieval contexts。

## 执行状态

- 状态：**completed**
- 完成案例：**10/10**
- 模型：`qwen-max`；temperature=0.0；max_tokens=8192
- v1.0.0 复用案例：Q01, Q04, Q11, Q17
- Q23 7 scorable 拆分：**已接受**（F=0.4286 在 0.4–0.5）

## Arm 配置

| Arm | schema | rubric | metric | F SHA | C SHA | R SHA |
|---|---|---|---|---|---|---|
| v1.0.0 | rag_judge_schema_v1 | v1.0.0 | v1 | `287053e9e67ad29fd2de597d1052b8d418040097910462e4a0f176b14295bfed` | `106e11f2bc39806da5ecf090c6dbcd94d81ca5f53b968e5055d5a33833b30f94` | `27203126964ae0ca8f0bb8641cb3c2b145605cec706ef47c5432a0bbd6fad141` |
| v1.1.1 | rag_judge_schema_v2 | v1.1.1 | v2 | `3519fd3b1bbbab9b117abd04f69304609146c2d2a05c39699483dea1740eda19` | `2ab6eac2abe57dcfd647df328244ac3e5681fc93222938d6614e71037d49ae77` | `0f8576b7dbf2e7ea1a02752680b0afe8c66677fe2eda823f4bcd28371ae4da84` |

## 分指标汇总（10 条）

| Arm | F 均值 | C 均值 | R 均值 | F 有效 | C 有效 | R 有效 | 失败 |
|---|---|---|---|---|---|---|---|
| v1.0.0 | 0.944 | 0.880 | 0.900 | 10/10 | 10/10 | 10/10 | 0 |
| v1.1.1 | 0.821 | 0.770 | 0.910 | 9/10 | 10/10 | 10/10 | 0 |

> 均值不作为验收唯一依据；逐案例目标与分指标下限见下。

## 逐案例

### Q01 · direct

- 问题：退款申请期限是多久？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- 目标：`{"F": [0.9, 1.0], "C": [0.9, 1.0], "R": [0.8, 1.0]}`

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 1.000 | 1.000 | +0.000 |
| C | 0.900 | 0.900 | +0.000 |
| R | 0.800 | 0.900 | +0.100 |

- Correctness details：`{"missing_points": [], "wrong_facts": [], "reason": "回答包含了金标中的关键事实，并补充了正确且相关的例外情况，没有矛盾或错误。"}`

- Counts（v1.1.1）：scorable=5, supported=5, unsupported=0, insufficient=0, non_factual=0, document_conflict=0, contradiction=0
- evidence：5/5 ok；validation_errors=[]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 退款申请期限为订单签收后7天内 | factual_claim/policy | supported | False | 1 |
| cl2 | 定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款 | factual_claim/policy | supported | False | 1 |
| cl3 | 生鲜食品如存在质量问题，须在签收后24小时内拍照反馈 | factual_claim/policy | supported | False | 1 |
| cl4 | 虚拟商品（如充值、会员、课程）一经售出不支持退款 | factual_claim/policy | supported | False | 1 |
| cl5 | 定制商品仅支持因质量问题退换，不支持无理由退换 | factual_claim/policy | supported | False | 1 |

### Q04 · direct

- 问题：目前支持哪种发票？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- **Provisional：该案例不是 Human Gold。**
- 目标：`{"F": [1.0, 1.0], "C": [0.8, 1.0], "R": [0.9, 1.0]}`

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 1.000 | 1.000 | +0.000 |
| C | 0.800 | 0.900 | +0.100 |
| R | 1.000 | 0.900 | -0.100 |

- Correctness details：`{"missing_points": [], "wrong_facts": [], "reason": "回答准确且完整地说明了目前仅支持电子发票，并补充了相关细节，这些细节是正确且相关的。"}`

- Counts（v1.1.1）：scorable=5, supported=5, unsupported=0, insufficient=0, non_factual=0, document_conflict=0, contradiction=0
- evidence：5/5 ok；validation_errors=[]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 目前仅支持电子发票 | factual_claim/policy | supported | False | 1 |
| cl2 | 电子发票在提交申请后 24 小时内发送至下单时填写的邮箱 | factual_claim/policy | supported | False | 1 |
| cl3 | 发票抬头可在开具前修改 | factual_claim/policy | supported | False | 1 |
| cl4 | 已开具的电子发票如需更正，须先申请红冲，再重新开具 | factual_claim/policy | supported | False | 1 |
| cl5 | 不支持纸质发票和增值税专用发票 | factual_claim/policy | supported | False | 1 |

### Q11 · multi

- 问题：签收第 5 天的定制商品可以无理由退款吗？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- **Provisional：该案例不是 Human Gold。**
- 目标：`{"F": [0.6, 0.9], "C": [0.8, 1.0], "R": [0.9, 1.0]}`

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 0.750 | 0.667 | -0.083 |
| C | 0.900 | 0.900 | +0.000 |
| R | 1.000 | 0.900 | -0.100 |

- Correctness details：`{"missing_points": [], "wrong_facts": [], "reason": "回答正确且完整，明确指出了定制商品不支持无理由退款，并补充了质量问题退换的相关政策。"}`

- Counts（v1.1.1）：scorable=6, supported=4, unsupported=0, insufficient=2, non_factual=0, document_conflict=0, contradiction=0
- evidence：4/5 ok；validation_errors=[{"claim_id": "cl1", "code": "quote_not_found", "message": "evidence quote is not a verbatim substring", "context_id": "C1"}, {"claim_id": "cl1", "code": "evidence_validation_failed", "message": "supported claim has invalid evidence; downgraded"}]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 签收第 5 天的定制商品不可以无理由退款 | factual_claim/policy | insufficient_evidence | False | 1 |
| cl2 | 订单签收后 7 天内可申请无理由退款 | factual_claim/policy | supported | False | 1 |
| cl3 | 定制类商品不支持无理由退款 | factual_claim/policy | supported | False | 1 |
| cl4 | 若该定制商品存在质量问题，仍可依据第12条“特殊商品”条款申请退换货 | factual_claim/policy | supported | False | 1 |
| cl5 | 用户当前仅可就质量问题发起售后申请 | factual_claim/policy | supported | False | 1 |
| cl6 | 需提供相应凭证（如照片、视频等），由商家审核认定后处理 | factual_claim/policy | insufficient_evidence | False | 0 |

### Q17 · multi

- 问题：订单满 99 元包邮，退货时运费谁承担？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- **Provisional：该案例不是 Human Gold。**
- 目标：`{"F": [0.9, 1.0], "C": [0.8, 1.0], "R": [0.8, 1.0]}`

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 1.000 | 1.000 | +0.000 |
| C | 0.900 | 0.900 | +0.000 |
| R | 1.000 | 0.900 | -0.100 |

- Correctness details：`{"missing_points": [], "wrong_facts": [], "reason": "回答涵盖了金标中的所有关键事实和条件，且没有矛盾或错误。"}`

- Counts（v1.1.1）：scorable=6, supported=6, unsupported=0, insufficient=0, non_factual=0, document_conflict=0, contradiction=0
- evidence：6/6 ok；validation_errors=[]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 订单满 99 元包邮适用于正向发货环节 | factual_claim/policy | supported | False | 1 |
| cl2 | 退货时的运费承担方取决于退换货原因 | factual_claim/policy | supported | False | 1 |
| cl3 | 若因质量问题退换货，运费由商家承担 | factual_claim/policy | supported | False | 1 |
| cl4 | 若为非质量问题（如无理由退货），运费由买家承担 | factual_claim/policy | supported | False | 1 |
| cl5 | 该规则与是否满 99 元无关 | factual_claim/policy | supported | False | 1 |
| cl6 | 不因包邮资格而改变退货运费责任归属 | factual_claim/policy | supported | False | 1 |

### Q21 · constraint

- 问题：签收后第 10 天，普通商品还能无理由退款吗？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- **Provisional：该案例不是 Human Gold。**
- 目标：`{"F": [0.6, 0.7]}`

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 0.800 | 0.600 | -0.200 |
| C | 0.900 | 0.900 | +0.000 |
| R | 1.000 | 0.900 | -0.100 |

- Correctness details：`{"missing_points": [], "wrong_facts": [], "reason": "回答准确地指出了无理由退款的期限是签收后7天内，并且补充了关于质量问题的正确且相关的信息。"}`

- Counts（v1.1.1）：scorable=5, supported=3, unsupported=0, insufficient=2, non_factual=1, document_conflict=0, contradiction=0
- evidence：3/4 ok；validation_errors=[{"claim_id": "cl4", "code": "quote_not_found", "message": "evidence quote is not a verbatim substring", "context_id": "C1"}, {"claim_id": "cl4", "code": "evidence_validation_failed", "message": "supported claim has invalid evidence; downgraded"}]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 不可以无理由退款 | factual_claim/policy | supported | False | 1 |
| cl2 | 无理由退款仅限订单签收后 7 天内申请 | factual_claim/policy | supported | False | 1 |
| cl3 | 签收第 10 天已超出该时效窗口（7 天） | factual_claim/policy | supported | False | 1 |
| cl4 | 该限制适用于“普通商品”（即非定制、非生鲜、非已激活虚拟商品） | factual_claim/policy | insufficient_evidence | False | 1 |
| cl5 | 若商品存在质量问题，则不受 7 天无理由限制，仍可依据保修或退换货政策主张权益 | factual_claim/policy | insufficient_evidence | False | 0 |
| cl6 | 如需进一步协助，建议联系客服（9:00–21:00）核实具体订单情况 | non_factual/advice | None | False | 0 |

### Q23 · constraint

- 问题：生鲜食品签收后第 2 天发现质量问题，还能按政策反馈吗？
- Gold：human_reviewed（docs/repair/phase3e/human-gold.json）
- 目标：`{"F": [0.4, 0.5], "C": [0.0, 0.2], "R": [0.7, 1.0]}`
- 说明：7 scorable with mixed advice+caveat accepted; F=0.428571 in target 0.4-0.5

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 1.000 | 0.429 | -0.571 |
| C | 0.800 | 0.000 | -0.800 |
| R | 0.900 | 0.900 | +0.000 |

- Correctness details：`{"missing_points": ["不能按该条款反馈"], "wrong_facts": ["是的，可以按政策反馈"], "reason": "首句给出错误结论，与后文关键事实矛盾"}`

- Counts（v1.1.1）：scorable=7, supported=3, unsupported=1, insufficient=3, non_factual=3, document_conflict=0, contradiction=1
- evidence：3/3 ok；validation_errors=[]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 可以按政策反馈 | factual_claim/policy | unsupported | True | 0 |
| cl2 | 已超出政策规定的反馈时效，原则上不符合质量反馈受理条件 | factual_claim/policy | supported | False | 1 |
| cl3 | 生鲜食品质量问题需在签收后 24 小时内拍照反馈 | factual_claim/policy | supported | False | 1 |
| cl4 | 该时限是硬性要求 | factual_claim/policy | supported | False | 1 |
| cl5 | 文档未提及例外情形或宽限期 | non_factual/absence | None | False | 0 |
| cl6 | 24 小时起算点为签收完成时间（非签收日零点） | factual_claim/policy | insufficient_evidence | False | 0 |
| cl7 | 需保留问题实物及包装证据 | factual_claim/policy | insufficient_evidence | False | 0 |
| cl8 | 建议立即通过订单页面或联系在线客服提交带时间水印的照片凭证 | non_factual/advice | None | False | 0 |
| cl9 | 若已超时，可尝试联系客服说明具体情况，但是否受理由商家个案判断，政策不保证支持 | factual_claim/policy | insufficient_evidence | False | 0 |
| cl10 | 文档未说明超时后申诉渠道或人工复核机制 | non_factual/absence | None | False | 0 |

### Q29 · unanswerable

- 问题：支持货到付款吗？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- **Provisional：该案例不是 Human Gold。**
- 目标：`{"F": "skipped", "C": [0.9, 1.0], "R": [0.9, 1.0]}`

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 1.000 | skipped(no_scorable_claims) | n/a |
| C | 1.000 | 0.900 | -0.100 |
| R | 0.800 | 1.000 | +0.200 |

- Correctness details：`{"missing_points": [], "wrong_facts": [], "reason": "正确说明了文档未提及货到付款，并给出了可行的下一步建议。"}`

- Counts（v1.1.1）：scorable=0, supported=0, unsupported=0, insufficient=0, non_factual=4, document_conflict=0, contradiction=0
- evidence：0/0 ok；validation_errors=[]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 未提及“货到付款”这一支付方式 | non_factual/absence | None | False | 0 |
| cl2 | 在所有章节（包括第5条“发货时效”、第6条“物流查询”、第7条“运费规则”等）中均未涉及支付方式，也未说明是否支持... | non_factual/absence | None | False | 0 |
| cl3 | 无法确认是否支持货到付款 | non_factual/meta | None | False | 0 |
| cl4 | 建议查阅网站结算页的支付选项，或直接联系在线客服（9:00–21:00）/拨打客服热线 400-800-1234 ... | non_factual/advice | None | False | 0 |

### Q31 · unanswerable

- 问题：退货支持上门取件吗？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- **Provisional：该案例不是 Human Gold。**
- 目标：`{"F": [0.6, 1.0], "C": [0.8, 1.0], "R": [0.8, 1.0]}`

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 1.000 | 1.000 | +0.000 |
| C | 0.900 | 0.900 | +0.000 |
| R | 0.800 | 0.900 | +0.100 |

- Correctness details：`{"missing_points": [], "wrong_facts": [], "reason": "回答正确说明文档未提及上门取件服务，并建议了下一步操作。"}`

- Counts（v1.1.1）：scorable=3, supported=3, unsupported=0, insufficient=0, non_factual=3, document_conflict=0, contradiction=0
- evidence：3/3 ok；validation_errors=[]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 该政策文件未规定支持上门取件，也未禁止 | non_factual/absence | None | False | 0 |
| cl2 | 退款流程要求用户在「我的订单」中选择退款，填写原因并上传凭证 | factual_claim/policy | supported | False | 1 |
| cl3 | 换货需先寄回原商品，商家收到并验收后才寄出新品 | factual_claim/policy | supported | False | 1 |
| cl4 | 因质量问题产生的退换货运费由商家承担，非质量问题的退货运费由买家承担 | factual_claim/policy | supported | False | 1 |
| cl5 | 物流查询和客服时间条款未涉及退货物流的发起方式（如是否可预约上门取件） | non_factual/absence | None | False | 0 |
| cl6 | 建议拨打客服热线 400-800-1234 或在在线客服时段内咨询“退货是否支持快递上门取件” | non_factual/advice | None | False | 0 |

### Q35 · ambiguous

- 问题：多久能到？
- Gold：human_reviewed（docs/repair/phase3e/human-gold.json）
- 目标：`{"F": [0.8, 1.0], "C": [0.7, 1.0], "R": [0.8, 1.0]}`
- 说明：absence claim factual/policy insufficient, not supported; F=0.833333 in target 0.8-1.0

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 0.889 | 0.833 | -0.056 |
| C | 0.800 | 0.900 | +0.100 |
| R | 0.800 | 0.900 | +0.100 |

- Correctness details：`{"missing_points": [], "wrong_facts": [], "reason": "回答覆盖了金标中的所有关键事实和条件，且提供了正确的建议操作。"}`

- Counts（v1.1.1）：scorable=6, supported=5, unsupported=0, insufficient=1, non_factual=3, document_conflict=0, contradiction=0
- evidence：5/6 ok；validation_errors=[{"claim_id": "cl1", "code": "claim_subtype_type_mismatch", "message": "claim_subtype 'absence' is not valid for factual_claim", "value": "absence"}, {"claim_id": "cl1", "code": "quote_not_found", "message": "evidence quote is not a verbatim substring", "context_id": "C1"}, {"claim_id": "cl1", "code": "evidence_validation_failed", "message": "supported claim has invalid evidence; downgraded"}]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 发货后，物流时效未在文档中明确说明 | factual_claim/policy | insufficient_evidence | False | 1 |
| cl2 | 现货商品付款后 48 小时内发出 | factual_claim/policy | supported | False | 1 |
| cl3 | 预售商品以商品页标注的发货时间为准 | factual_claim/policy | supported | False | 1 |
| cl4 | 大件商品（如家具、家电）发货时间为 5 个工作日内，且配送前会电话预约 | factual_claim/policy | supported | False | 1 |
| cl5 | 您可在「我的订单」中查看物流单号与实时轨迹 | factual_claim/policy | supported | False | 1 |
| cl6 | 若物流信息超过 24 小时未更新，可联系客服协助核查 | factual_claim/policy | supported | False | 1 |
| cl7 | 建议登录账户，进入「我的订单」确认是否已发货 | non_factual/advice | None | False | 0 |
| cl8 | 建议查看物流单号并跟踪快递状态 | non_factual/advice | None | False | 0 |
| cl9 | 建议若已发货但长时间无更新，拨打客服热线 400-800-1234（9:00–21:00）或在线留言 | non_factual/advice | None | False | 0 |

### Q36 · ambiguous

- 问题：能退吗？
- Gold：human_reviewed（docs/repair/phase3e/human-gold.json）
- 目标：`{"F": [0.8, 1.0], "C": [0.5, 0.6], "R": [0.8, 1.0]}`
- 说明：answer does not disclose conflict; document_conflict=0; C=0.5 with missing conflict disclosure; wrong_facts=[]

| 指标 | v1.0.0 | v1.1.1 | Δ |
|---|---|---|---|
| F | 1.000 | 0.857 | -0.143 |
| C | 0.900 | 0.500 | -0.400 |
| R | 0.900 | 0.900 | +0.000 |

- Correctness details：`{"missing_points": ["定制商品支持质量问题退换，不支持无理由退换", "第 1 条对虚拟商品的限定是「已激活」，第 12 条则称虚拟商品一经售出不支持退款，两处范围不完全一致，具体商品需以对应条款/客服确认为准"], "wrong_facts": [], "reason": "回答覆盖了大部分关键信息，但缺少关于定制商品的质量问题退换政策和文档中对虚拟商品退款规定的冲突披露。"}`

- Counts（v1.1.1）：scorable=7, supported=6, unsupported=0, insufficient=1, non_factual=2, document_conflict=0, contradiction=0
- evidence：6/7 ok；validation_errors=[{"claim_id": "cl5", "code": "quote_not_found", "message": "evidence quote is not a verbatim substring", "context_id": "C1"}, {"claim_id": "cl5", "code": "evidence_validation_failed", "message": "supported claim has invalid evidence; downgraded"}]

| claim_id | claim（截断） | type/subtype | status | contradictory | evidence |
|---|---|---|---|---|---|
| cl1 | 普通商品在签收后 7 天内可申请无理由退款 | factual_claim/policy | supported | False | 1 |
| cl2 | 审核通过后，款项将在 1–3 个工作日内原路退回 | factual_claim/policy | supported | False | 1 |
| cl3 | 定制类商品不支持无理由退款 | factual_claim/policy | supported | False | 1 |
| cl4 | 生鲜食品不支持无理由退货，质量问题需在签收后 24 小时内拍照反馈 | factual_claim/policy | supported | False | 1 |
| cl5 | 已激活的虚拟商品不支持退款 | factual_claim/policy | insufficient_evidence | False | 1 |
| cl6 | 若因商品质量问题退换货，运费由商家承担 | factual_claim/policy | supported | False | 1 |
| cl7 | 若为非质量问题退货，运费由买家承担 | factual_claim/policy | supported | False | 1 |
| cl8 | 请确认您的商品类型及是否仍在签收后 7 天内 | non_factual/advice | None | False | 0 |
| cl9 | 如需进一步协助，欢迎补充订单信息 | non_factual/advice | None | False | 0 |

## 关键结论

- **Q01/Q04/Q17/Q21/Q11 目标命中**；Q01 C=0.9，额外信息规则生效。
- **Q23 F=0.428571，7 scorable（3 supported / 1 unsupported / 3 insufficient / 3 non_factual），3/3 evidence，validation_errors=[]**；按已批准的 7 条拆分接受，F 在 0.4–0.5。
- **Q29 F skipped(no_scorable_claims)**，C=0.9、R=1.0，目标命中。
- **Q31 F=1.0，C=0.9，R=0.9**；absence 目标未触发 skipped。
- **Q35 F=0.8333、C=0.9、R=0.9**；cl1 absence 被归 factual/policy 但为 insufficient（不是 supported），F 在 0.8–1.0。
- **Q36 F=0.8571、C=0.5、R=0.9**；answer 未披露 §1/§12 冲突，`document_conflict=0`；C 的 `missing_points` 包含冲突披露，`wrong_facts=[]`；只验证披露，不选 canonical 口径。
- Q11/Q21/Q35/Q36 有 quote_not_found 诊断（证据降级），但最终 F 分数均在注册目标内；没有 schema failed、没有全 invalid。

## Token / 成本（10 条 × 2 臂）

| Arm | input | output | 估算成本（CNY） |
|---|---|---|---|
| v1.0.0 | 32612 | 6252 | 0.1383 |
| v1.1.1 | 85372 | 9008 | 0.2914 |
| **合计** |  |  | **0.4297** |

> v1.0.0 的 Q01/Q04/Q11/Q17 为复用结果；v1.1.1 input 约 v1.0.0 的 2.6×。

## 边界

- v1.1.1 仍 `design_draft` / `active=false`；脚本退出前恢复 `RAG_JUDGE_PROMPT_VERSION=v1.0.0`。
- 未跑 40 条、未激活、未改 Human Gold/Prompt 正文/DB。
- Q11/Q21/Q29 为 provisional；Q23/Q35/Q36 为 Human Gold v1。

