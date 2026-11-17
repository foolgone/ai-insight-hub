# 10 条 Pilot 重跑：v1.0.0 vs v1.1.1（6/10，Q23 停止）

> 同一批 Pilot answer/contexts；v1.1.1 使用新 F/C SHA；只切换 Judge Prompt 版本。
> Faithfulness 只用 `query.contexts`（C1–C2），不使用 retrieval contexts。

## 执行状态

- 状态：**stopped**
- 停止原因：
  - `Q23 F scorable != 6`
- 已完成案例：**6/10**
- 未运行案例：Q29, Q31, Q35, Q36
- 模型：`qwen-max`；temperature=0.0；max_tokens=8192
- v1.0.0 复用案例：Q01, Q04, Q11, Q17

## Arm 配置

| Arm | schema | rubric | metric | F SHA | C SHA | R SHA |
|---|---|---|---|---|---|---|
| v1.0.0 | rag_judge_schema_v1 | v1.0.0 | v1 | `287053e9e67ad29fd2de597d1052b8d418040097910462e4a0f176b14295bfed` | `106e11f2bc39806da5ecf090c6dbcd94d81ca5f53b968e5055d5a33833b30f94` | `27203126964ae0ca8f0bb8641cb3c2b145605cec706ef47c5432a0bbd6fad141` |
| v1.1.1 | rag_judge_schema_v2 | v1.1.1 | v2 | `3519fd3b1bbbab9b117abd04f69304609146c2d2a05c39699483dea1740eda19` | `2ab6eac2abe57dcfd647df328244ac3e5681fc93222938d6614e71037d49ae77` | `0f8576b7dbf2e7ea1a02752680b0afe8c66677fe2eda823f4bcd28371ae4da84` |

## 分指标汇总（仅已完成案例，Q23 F=0 会计入均值）

| Arm | F 均值 | C 均值 | R 均值 | F 有效 | C 有效 | R 有效 | 失败 |
|---|---|---|---|---|---|---|---|
| v1.0.0 | 0.925 | 0.867 | 0.950 | 6/6 | 6/6 | 6/6 | 0 |
| v1.1.1 | 0.783 | 0.750 | 0.900 | 6/6 | 6/6 | 6/6 | 0 |

> 6 条均值，不能代表 10 条；Q23 F=0 直接拉低 v1.1.1 F 均值。

## 逐案例

### Q01 · direct

- 问题：退款申请期限是多久？
- Gold：ai_draft_pending_human（docs/repair/phase3e/candidates.json (AI draft, pending human)）
- 目标：`{"F": [0.9, 1.0], "C": [0.9, 1.0], "R": [0.8, 1.0]}`
- v1.0.0 复用：True

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
- 目标：`{"F": [1.0, 1.0], "C": [0.8, 1.0], "R": [0.9, 1.0]}`
- v1.0.0 复用：True

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
- v1.0.0 复用：True

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
- 目标：`{"F": [0.9, 1.0], "C": [0.8, 1.0], "R": [0.8, 1.0]}`
- v1.0.0 复用：True

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
- v1.0.0 复用：False

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
- v1.0.0 复用：False

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

## 发现

- **停止条件命中：Q23 v1.1.1 F=0.428571 落在目标 0.4–0.5，但 `scorable=7`，未满足关键校验“6 scorable / 3 supported / 3/3 evidence”。** 按 Q23 key 校验立即停止。
- Q23 F：7 scorable，3 supported / 1 unsupported / 3 insufficient / 3 non_factual；3/3 evidence；cl1 `is_contradictory=true`、`contradiction_with=["cl2"]`；`validation_errors=[]`。
- Q23 第 7 条 scorable 来自“若已超时，可尝试联系客服说明具体情况，但是否受理由商家个案判断，政策不保证支持”被归为 factual/policy/insufficient；矩阵期望该句作为 advice（non_factual），因此分母从 6 变 7。
- Q23 C=0.0（目标 0.0–0.2，命中），`wrong_facts=["是的，可以按政策反馈"]`；R=0.9。
- Q21 v1.1.1 F=0.6（目标 0.6–0.7，命中）；Q11 F=0.6667（目标 0.6–0.9，命中）；Q01/Q04/Q17 目标命中。
- 未运行 Q29/Q31/Q35/Q36；**Q36 disclosure 未验证**。

## Token / 成本（已完成 6 条 × 2 臂）

| Arm | input | output | 估算成本（CNY） |
|---|---|---|---|
| v1.0.0 | 17985 | 2943 | 0.0714 |
| v1.1.1 | 49641 | 5192 | 0.1690 |
| **合计** |  |  | **0.2404** |

> v1.0.0 的 Q01/Q04/Q11/Q17 为复用结果，其 token 是上一轮已发生成本。

## 边界

- v1.1.1 仍 `design_draft` / `active=false`；脚本退出前恢复 `RAG_JUDGE_PROMPT_VERSION=v1.0.0`。
- 未跑 40 条、未激活、未改 Human Gold/Prompt 正文/DB。
- 共享 `parse_with_repair` Schema fallback 已修复；Q01 C 额外信息规则已生效。

