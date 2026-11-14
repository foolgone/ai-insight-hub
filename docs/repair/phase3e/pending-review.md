# Phase 3E 待人工审核清单

> 所有条目 `pending_human`；AI 预标注不是 Human Gold。状态更新见 `annotation-spec.md`。

| ID | 类别 | 问题 | 审核范围 | 状态 |
|---|---|---|---|---|
| Q01 | direct | 退款申请期限是多久？ | 基础字段 + Claim | pending_human |
| Q02 | direct | 退款审核通过后多久能到账？ | 基础字段 | pending_human |
| Q03 | direct | 同一订单可以换货几次？ | 基础字段 | pending_human |
| Q04 | direct | 目前支持哪种发票？ | 基础字段 + Claim | pending_human |
| Q05 | direct | 发票提交申请后多久发送？ | 基础字段 | pending_human |
| Q06 | direct | 现货商品付款后多久发出？ | 基础字段 | pending_human |
| Q07 | direct | 大件商品发货时间是多久？ | 基础字段 | pending_human |
| Q08 | direct | 单笔订单满多少元包邮？ | 基础字段 | pending_human |
| Q09 | direct | 电子产品保修期多久？ | 基础字段 | pending_human |
| Q10 | direct | 优惠券有效期多久？ | 基础字段 | pending_human |
| Q11 | multi | 签收第 5 天的定制商品可以无理由退款吗？ | 基础字段 + Claim | pending_human |
| Q12 | multi | 退款审核通过后按什么渠道退回？多久到账？ | 基础字段 | pending_human |
| Q13 | multi | 换货需要先寄回原商品吗？新品多久寄出？ | 基础字段 | pending_human |
| Q14 | multi | 发票抬头开错了可以改吗？ | 基础字段 | pending_human |
| Q15 | multi | 大件商品配送前会联系买家吗？ | 基础字段 | pending_human |
| Q16 | multi | 物流信息超过 24 小时没更新怎么办？ | 基础字段 | pending_human |
| Q17 | multi | 订单满 99 元包邮，退货时运费谁承担？ | 基础字段 + Claim | pending_human |
| Q18 | multi | 保修期内和保修期外维修分别怎么收费？ | 基础字段 | pending_human |
| Q19 | multi | 退款后优惠券会退回吗？ | 基础字段 | pending_human |
| Q20 | multi | 会员积分怎么获得、怎么抵扣、有效期多久？ | 基础字段 | pending_human |
| Q21 | constraint | 签收后第 10 天，普通商品还能无理由退款吗？ | 基础字段 + Claim | pending_human |
| Q22 | constraint | 订单实付 89 元寄往新疆，运费多少？ | 基础字段 | pending_human |
| Q23 | constraint | 生鲜食品签收后第 2 天发现质量问题，还能按政策反馈吗？ | 基础字段 + Claim | pending_human |
| Q24 | constraint | 已发货订单还能修改收货地址吗？ | 基础字段 | pending_human |
| Q25 | constraint | 同一订单能同时使用两张优惠券吗？ | 基础字段 | pending_human |
| Q26 | constraint | 会员折扣和优惠券可以叠加吗？ | 基础字段 | pending_human |
| Q27 | constraint | 保修期内人为进水，能免费维修吗？ | 基础字段 | pending_human |
| Q28 | constraint | 预售商品付款后 48 小时未发货，是否算延迟？ | 基础字段 | pending_human |
| Q29 | unanswerable | 支持货到付款吗？ | 基础字段 + Claim | pending_human |
| Q30 | unanswerable | 支持海外配送吗？ | 基础字段 | pending_human |
| Q31 | unanswerable | 退货支持上门取件吗？ | 基础字段 + Claim | pending_human |
| Q32 | unanswerable | 积分可以兑换礼品吗？ | 基础字段 | pending_human |
| Q33 | unanswerable | 有生日双倍积分活动吗？ | 基础字段 | pending_human |
| Q34 | unanswerable | 可以指定快递公司吗？ | 基础字段 | pending_human |
| Q35 | ambiguous | 多久能到？ | 基础字段 + Claim | pending_human |
| Q36 | ambiguous | 能退吗？ | 基础字段 + Claim | pending_human |
| Q37 | ambiguous | 发票怎么弄？ | 基础字段 | pending_human |
| Q38 | ambiguous | 运费多少？ | 基础字段 | pending_human |
| Q39 | ambiguous | 保修多久？ | 基础字段 | pending_human |
| Q40 | ambiguous | 积分怎么用？ | 基础字段 | pending_human |
