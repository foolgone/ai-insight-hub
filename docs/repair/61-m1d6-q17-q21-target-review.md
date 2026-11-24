# M1-D-6 Q17 / Q21 Target 复核（M1-A desk，不跑 Judge）

> 状态：`read_only_review`；**未跑 Judge、未改 target v1.0.2、未改 Prompt/Agent/fixture。**
> 日期：2026-11-24
> 证据：`docs/repair/phase3e/m1d6-q17-q21-target-review.json`（SHA `a7819032…`）
> 数据源：flash 对比结果 `efdfa729…`；qwen-max failure-mode `309fa9b8…`；target v1.0.2 `3ee15dfc…`；fixture `dc7be14b…`
> 资产：v1.2.5 frozen；F `9c80d4d5…`；freeze `e9e5f8e`；agent `318b302`。

## 0. 结论

| case | 旧 target | flash F | qwen-max F | 旧 target 是否成立 | M1-A 建议 |
|---|---|---:|---:|---|---|
| Q17 | `[0.7, 0.9]` | 0.5（4 claims） | 0.6（5 claims） | **否**：下界不可达 | `[0.4, 0.7]` |
| Q21 | `[0.6, 0.7]` | 0.75（4 scorable） | 0.8（5 scorable） | **否**：上界低于诚实分数 | `[0.7, 0.9]` |

两者都是 **valid**，问题是 target 校准，不是 Judge 稳定性。

以上只是提案；**写 target v1.0.3 前需要 M1-A 批准**，不得直接改 v1.0.2。

## 1. Q17

### 1.1 数据

| 项 | flash | qwen-max |
|---|---:|---:|
| F | **0.5** | 0.6 |
| claims | 4 | 5 |
| supported | 2 | 3 |
| insufficient | 2 | 2 |
| unsupported | 0 | 0 |

### 1.2 逐 claim 语义判定

| claim | 类型 | flash | qwen-max | 判定 |
|---|---|---|---|---|
| 满 99 元包邮适用于正向发货环节 | policy_scope | insufficient | insufficient | **insufficient 合理**：上下文只写“满 99 元包邮；未满收 10 元运费”，没有显式“正向发货”适用范围 |
| 退货时的运费承担方取决于退换货原因 | condition | 未拆出 | supported | **supported**：上下文并列了两条责任归属，可推出“取决于原因” |
| 质量问题退换货运费商家承担 | policy | supported | supported | supported（§7 原文） |
| 非质量问题退货运费买家承担 | policy | supported | supported | supported（§7 原文） |
| 退货运费责任与是否满 99 无关 | policy_relationship | insufficient | insufficient | **insufficient 合理**：上下文没有显式关系句，只是并列条款 |

### 1.3 为什么 `[0.7, 0.9]` 不成立

- 两条 insufficient（scope、relationship）在现行 v1.2.0 语义规范下是正确判定；
- 诚实分数上限是 3/5 = **0.6**（qwen-max 分解）或 2/4 = **0.5**（flash 分解）；
- `0.7` 下界要求至少 3.5/5 或 2.8/4 supported，只有当 scope 或 relationship 被判 supported 才可能；
- target 记录的 `semantic_reason` 假设 “policy_relationship factual; F may return to 0.8”，但两个模型都判 insufficient，这个假设未成立。

### 1.4 附带发现：claim 分解不稳定

flash 少拆了“取决于退换货原因”这条 supported claim，导致分母从 5 变 4、F 从 0.6 降到 0.5。这不是 target 问题，但说明 Q17 的 claim 粒度会直接影响 F；target 需要给分解差异留余量。

### 1.5 建议

| 项 | 值 |
|---|---|
| 建议 target | **`[0.4, 0.7]`** |
| 理由 | 覆盖 4-claim 0.5、5-claim 0.6，并为“是否拆出取决于原因”留 0.1 余量；上界 0.7 允许一条推断被判 supported |
| 风险 | 区间较宽（0.3）；若后续 claim 规则进一步细化，需要重新校准 |

## 2. Q21

### 2.1 数据

| 项 | flash | qwen-max |
|---|---:|---:|
| F | **0.75** | 0.8 |
| claims | 5 | 6 |
| scorable | 4 | 5 |
| supported | 3 | 4 |
| insufficient | 1 | 1 |
| non_factual | 1 | 1 |

### 2.2 逐 claim 语义判定

| claim | 类型 | flash | qwen-max | 判定 |
|---|---|---|---|---|
| 第 10 天不支持无理由退款 | derived | supported | supported | supported（7 天窗口推导） |
| 无理由退款仅限 7 天内 | policy | supported | supported | supported（§1 原文） |
| 限制适用于普通商品（非定制/生鲜/虚拟） | condition | supported | supported | **supported，但有判断成分**：上下文只列了特殊商品不支持，“普通商品适用”是补集推断 |
| 质量问题不受 7 天无理由限制 | condition | insufficient | insufficient | **insufficient 合理**：上下文没有该豁免条款；§12 只讲特殊商品质量问题的 24 小时反馈 |
| 建议联系客服 | advice | non_factual | non_factual | 不计入分母 |

### 2.3 为什么 `[0.6, 0.7]` 不成立

- 两个模型的诚实分数是 0.75 / 0.8，**高于上界 0.7**；
- 旧 target 很可能是在“豁免 claim 被误判 supported”或“claim 分解不同”的时期定的；v1.2.5 后豁免 claim 已正确判 insufficient，分数自然上升；
- 这不是回归，是语义修正后的正常结果。

### 2.4 建议

| 项 | 值 |
|---|---|
| 建议 target | **`[0.7, 0.9]`** |
| 理由 | 下界 0.7 覆盖 3/4；上界 0.9 覆盖 4/5 与 5/6，并能捕获“把豁免 claim 错判 supported”的回归 |
| 风险 / caveat | cl3“普通商品适用”是补集推断；若 M1-A 判定它应 insufficient，诚实分数会降到 0.5-0.6，target 需重新讨论 |

## 3. M1-A 决策项

| 项 | 当前 | 建议 |
|---|---|---|
| Q17 target | `[0.7, 0.9]`（`reapproval_required`） | `[0.4, 0.7]` |
| Q21 target | `[0.6, 0.7]`（`unchanged`） | `[0.7, 0.9]` |
| target 版本 | v1.0.2 | 新生成 **v1.0.3**，不原地改 |
| 生效条件 | — | M1-A 批准 + 新 target SHA + 重新基线 |
| Judge | v1.2.5 frozen | 不改 |

## 4. 边界

- 只做 desk review；0 Judge calls；
- target v1.0.2 未修改；
- 未改 Prompt/Agent/Service/validator/fixture；
- 未写 PASS、未激活、未跑正式 10/40；
- M1-D-6 仍 `blocked`；M1-C/M1-D 未 accepted。
