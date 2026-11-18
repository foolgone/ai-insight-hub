# Judge 语义规范草案（v1.2.0 依据）

> 状态：草案，等待人工审核。本文是 v1.2.0 Prompt 与 Service 的共同依据，不是运行时实现。
>
> 适用指标：Faithfulness（F）、Answer Correctness（C）、Answer Relevancy（R）。三指标共享 Claim 语义，但分母和判定边界不同。

## 1. 规范目标

1. **可复现**：同一输入、同一版本、同一模型配置，输出应能按同一规则解释。
2. **可审计**：每个分数都能追溯到 claim、support_status、evidence、分母。
3. **可版本化**：语义规则变化必须换 Prompt 版本；不允许在同一版本内为单案例加特例。
4. **不把模型输出当绝对真值**：单次输出只是观测；高方差案例必须重复实验。

## 2. 基本术语

| 术语 | 定义 |
|---|---|
| claim | 回答中一个可独立判定真假或可独立归类的断言 |
| factual_claim | 对政策、事实、数字、条件、时间、流程、规范性要求的断言 |
| non_factual | 问候、共情、建议、absence、scope/meta、relationship、uncertainty 等非事实断言 |
| support_status | factual_claim 的支持状态：supported / unsupported / insufficient_evidence |
| evidence_ref | 指向 contexts 的逐字片段：`{context_id, quote}` |
| scorable claim | 进入 F 分母的 factual claim |
| context_unavailable | 上下文为空或不可用，F 无法评估 |
| no_scorable_claims | 全部 claim 都是 non_factual，F 无分母 |

## 3. Claim 分类

### 3.1 factual_claim

只有以下类型进入 F 分母：

| 子类型 | 定义 | 示例 |
|---|---|---|
| `policy` | 文档明确写出的政策、规则、数字、时限、费用、流程 | “订单签收后 7 天内可申请无理由退款” |
| `condition` | 文档明确写出的条件、例外、适用范围、前置条件 | “定制类商品不支持无理由退款” |
| `normative_requirement` | 文档明确写出的“需/必须/应/须提供/保留/提交”要求 | “质量问题需在签收后 24 小时内拍照反馈” |
| `conflict` | 文档两处规则不一致的 meta 陈述（只在回答披露冲突时） | “§1 与 §12 对虚拟商品范围表述不一致” |

### 3.2 non_factual

以下类型**不进入 F 分母**：

| 子类型 | 定义 | 示例 |
|---|---|---|
| `absence` | 文档未说明/未提及/未涉及某事实 | “文档未提及货到付款” |
| `scope` | 文档未明确写的适用范围/地域/对象推断 | “默认适用于中国大陆境内订单” |
| `relationship` | 规则之间的关系、独立性、依赖、优先级推断 | “该规则与是否满 99 元无关” |
| `uncertainty` | 无法确认/无法判断/信息不足的结论句 | “无法确认积分支持礼品兑换” |
| `meta` | 文档覆盖范围、章节内容、总起/分类引导句 | “文档详细说明了退款时效、换货、发票……” |
| `advice` | 纯建议、下一步操作 | “建议联系客服核实” |
| `greeting` | 问候、共情、礼貌语 | “您好，很高兴为您服务” |

### 3.3 判断顺序

1. 先判断是否 factual_claim；不是则归 non_factual，结束。
2. 是 factual_claim 才判断 support_status。
3. 判断 evidence 是否逐字、充分。
4. 判断 claim 之间/文档内部是否矛盾或冲突。
5. 最后由 Service 计算分母与状态。

**不得反向操作**：不能因为“找不到 evidence”就把 factual 改成 non_factual；也不能因为“看起来合理”就把 non_factual 改成 supported。

## 4. Claim 原子性

### 4.1 一条 claim 一个可判定事实

- 一条 claim 只表达一个可独立判定的事实、条件、数字或规范性要求。
- 同一句中的多个独立事实必须拆分；跨句的同一事实可以合并为一条。
- 不得把“事实 + 推断”“事实 + 建议”“事实 + absence”合成一条。

### 4.2 混合句拆分

示例：
> “所有政策节点以签收为起算，但未定义签收是否包含境外地址，亦未说明清关/国际运输。”

拆为：
- factual/policy：退款、换货、保修以签收为起算基准（有依据时 supported）
- absence：未定义签收是否包含境外地址（non_factual）
- absence：未说明清关/国际运输（non_factual）

### 4.3 主语与谓词

- 如果 claim 的主语在另一分句，quote 仍只引支持该 claim 的**最短连续子串**。
- 不得把前一分句的主语/限定语拼到后一分句的谓词上。
- 反例：claim“生鲜食品质量问题需在签收后 24 小时内拍照反馈”，quote 不能写成“生鲜食品质量问题需在签收后 24 小时内拍照反馈”；原文是“生鲜食品签收后不支持无理由退货，质量问题需在签收后 24 小时内拍照反馈”。

### 4.4 引用原文是回答内容

- 回答中的 `>` 引用块、`<kb ...>` 前的原文、转述原文，都是回答内容。
- 引用中的每个独立事实都要建 claim；不得因为前文已概括而省略。
- 但 quote 必须来自 contexts，不能引用 answer 自身。

### 4.5 不得合成示例

- 回答中为说明而编造的具体日期、金额、订单号、案例，不应被当作 factual claim 的 evidence；如作为 claim，必须 insufficient 或 non_factual。
- 不得用“例如某订单……”等合成示例支持政策事实。

## 5. Evidence 规范

### 5.1 来源

- `quote` 必须来自 contexts（C1/C2/…），不得来自 answer、用户问题、模型知识。
- `context_id` 只能是输入中真实存在的编号；不是文档章节号。

### 5.2 逐字与最短子串

- `quote` 必须是 contexts 的逐字连续子串；不得改写、拼接、补主语。
- 优先使用支持该 claim 的**最短连续子串**。
- 跨行引用必须保留换行；更稳妥的是只引单行连续子串。
- `quote` 结尾一律不带标点（句号/分号/逗号/冒号）；只复制到最后一个汉字/数字/字母。
- 如果 claim 含主语，而主语在另一分句，仍只引谓词所在的最短子串，不要自造“主语+谓词”。

### 5.3 支持充分性

- `supported`：上下文有明确依据，且 quote 完整支持 claim。
- `unsupported`：上下文与 claim 矛盾，或 claim 与回答内其它 claim 冲突且无法同时成立。
- `insufficient_evidence`：上下文未提及、只沾边、需要外部知识，或只支持部分条件。
- `supported` 必须至少有一个有效 evidence_ref；没有 evidence 不得 supported。
- `insufficient_evidence` 的 evidence_refs 为空数组；不得用“找不到证据”的 quote 充数。
- `unsupported` 可以提供指向矛盾原文的 evidence_refs。

### 5.4 证据校验与降级

- `quote_not_found`：quote 不是逐字子串 → 该 evidence 无效。
- `supported` 但 evidence 无效 → 降级 `insufficient_evidence`，记 `evidence_validation_failed`。
- `supported_without_evidence` → 直接判为校验失败，不进入 supported。
- 冲突 claim 必须有两条 `(context_id, quote)` 去重且互不为子串的证据；否则记 `conflict_single_sided_evidence`。
- 重复 `claim_id`：保留首条，跳过后续，记 `duplicate_claim_id`。

## 6. Scope / Meta / absence / uncertainty

### 6.1 不进 F 分母

以下一律 non_factual，不进入 F 分母：
- “文档未提及/未说明/未涉及/未规定……”
- “默认适用于中国大陆境内订单”
- “以国内履约场景为前提”
- “该规则与是否满 99 元无关”
- “不因包邮资格改变责任归属”
- “无法确认/无法判断/信息不足”
- “文档详细说明了退款、换货、发票……”
- “建议联系客服/查看页面/提供订单号”

### 6.2 混合句

- 事实部分：factual；未定义/范围/关系部分：non_factual。
- 不得整句标 factual/insufficient。
- 不得因为 non_factual 部分存在，就把 factual 部分也标 non_factual。

### 6.3 全称与推断

- “所有/任何/一律/均/默认/不受……限制”等全称或排除性表述，必须有明确依据；否则 insufficient，不得 supported。
- 目的推断（“电话联系是为了确认收货时间”）、权益推断（“可申请催促/补偿/取消”）、外部条件（“不含节假日/银行延迟”）均按 insufficient，除非文档明确写出。

## 7. 矛盾与冲突

### 7.1 回答内部矛盾

- `is_contradictory=true`：claim 与同一回答内其它 claim 冲突，无法同时成立。
- `contradiction_with` 填 claim_id（不是 context_id）。
- 矛盾 claim 仍要判断 support_status，不得用 non_factual 排除。
- 示例 Q23：“可以按政策反馈” vs “已超过 24 小时不符合受理条件”。

### 7.2 文档冲突

- 文档两处规则不一致的 meta 陈述：`claim_type=factual_claim`、`claim_subtype=conflict`。
- 两处原文都能给出时 `support_status=supported`；`is_contradictory=false`（矛盾在文档，不在回答）。
- 两条 evidence 必须来自两处原文，去重且互不为子串。
- 回答没有披露冲突时，不输出 conflict claim；base 不因“文档有冲突”而扣分。
- Q36 的 §1/§12 口径未业务选边；只验证“是否披露”，不把某一口径写成 Gold。

### 7.3 冲突与 unsupported

- 回答 vs Context 矛盾：`support_status=unsupported`，不要用 `is_contradictory` 冒充。
- 回答内部矛盾：`is_contradictory=true`，但 support_status 仍按证据判断。
- 文档冲突：`claim_subtype=conflict`，不是 unsupported。

## 8. 条件分支与规则推导

- 只支持文档明确写出的条件、例外、时限、费用。
- 多步算术（如“第 10 天 > 7 天”）可以 supported，但每一步必须有明确规则。
- 目的、权益、补偿、取消、催单等推断：没有明确条款 → insufficient。
- 全称 generalization：没有明确条款 → insufficient。
- 规则关系/独立性：默认 non_factual/relationship；只有文档明确写出“无关/不依赖/优先”才 factual。
- Q21#3：保持 insufficient；不得因为“字面上可推出”就 supported。
- Q28：补偿/取消权益保持 insufficient；目标已注册，但语义不变。

## 9. Answerability 与 Context 可用性

| 场景 | F 状态 | 分数 | 报告 |
|---|---|---|---|
| contexts 为空/不可用 | `skipped(context_unavailable)` | 无 | F unavailable，不是 PASS，不是 0 |
| 全部 claim non_factual | `skipped(no_scorable_claims)` | 无 | 正确 skip；不是 1.0 |
| 全部 factual 都 insufficient | `evaluated` | 0.0 | 0 分，不是 skip |
| 全部 claims 无效/schema 失败 | `failed` | 无 | 不是 0，不进入均值 |
| 只有 C1 | `evaluated` | 正常 | 报告注明单上下文 |
| C/R 可评估但 F 不可评估 | F skip，C/R evaluated | C/R 正常 | 分组报告 |

## 10. Skip / Failed / Validation Error 边界

| 状态/错误 | 触发 | 是否进入均值 | 是否算 PASS |
|---|---|---|---|
| `evaluated` | 有 scorable claim | 是 | 按目标 |
| `skipped(no_scorable_claims)` | 全部 non_factual | 否 | 仅当目标为 skipped |
| `skipped(context_unavailable)` | 无上下文 | 否 | 否；F unavailable |
| `failed(schema)` | 结构化输出失败 | 否 | 否 |
| `failed(all_invalid)` | 全部 claims 校验失败 | 否 | 否 |
| `supported_without_evidence` | supported 无 evidence | 否 | 否 |
| `evidence_validation_failed` | quote 不逐字/降级 | 否（该 claim 降级） | 视降级后分数 |
| `duplicate_claim_id` | 重复 claim_id | 否（保留首条） | 需记录 |
| `conflict_single_sided_evidence` | 冲突证据单边/嵌套 | 否 | 需记录 |
| `context_unavailable` + C/R | 只有 F 不可用 | C/R 是 | Q14 不是 clean pass |

## 11. 三指标边界

### 11.1 Faithfulness

- 分母：scorable factual claims。
- 分子：supported。
- non_factual 不进分母。
- 不允许把 absence/meta/scope/relationship/uncertainty 作为 supported factual。
- 不允许因为回答“更长/更多建议”而提高 F。

### 11.2 Answer Correctness

- 只看 gold_answer 的关键事实、条件、结论。
- `missing_points`：金标有关键点未覆盖。
- `wrong_facts`：回答与金标/文档矛盾。
- 正确且相关的额外信息不扣分；不把“额外正确信息”记为 wrong_fact。
- 单一部分、直接完整的回答，不因缺少额外步骤/建议降分。
- 未来可选 key_facts 输入；当前不改变 Schema。

### 11.3 Answer Relevancy

- 只看是否围绕问题、是否覆盖子问题/条件分支。
- 不判断事实正确性。
- 单一部分、直接完整回答 → 0.9–1.0；不得因“没有下一步建议”降到 0.7–0.8。
- 多部分/条件分支问题：遗漏子问题才降分。
- 合理拒答 + 下一步 → 0.9–1.0；套话/回避 → 0.3–0.6。

## 12. 版本与变更

1. 任何语义变化（claim 类型、分母、evidence、skip 边界）→ 新 Prompt 版本。
2. 不允许在同一版本内为单案例增加 Prompt 特例；规则必须可复用。
3. 不允许混用不同 F/R/C SHA 的结果；报告必须写全 SHA。
4. v1.0.0 保持 `active_baseline`；v1.1.x 与 v1.2.0 默认 `active=false`，显式选择才加载。
5. 旧 Run 只读归档；新版本必须重新跑，不拼接旧结果。

## 13. 待业务确认

- Q36 §1/§12 虚拟商品冲突的 canonical 口径。
- Q14 金标是否保留“未开具前可以修改”；C 的 key_facts 是否启用。
- Q21#3 是否继续 insufficient。
- Q28 补偿/取消权益是否属于政策范围。
- Q30 海外配送 absence 的报告口径。
- Q32 “无法确认”类回答是否允许 0.75 目标，或必须 meta/1.0。
- Q35/Q36 quote 诊断是否接受为 known diagnostic。

## 14. 一句话总结

**先判“是不是事实”，再判“有没有逐字证据”，最后才判“支持不支持”；范围、关系、absence、无法确认不是事实，不能进 F 分母。**
