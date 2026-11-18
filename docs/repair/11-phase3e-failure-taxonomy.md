# Phase 3E Judge 失败模式归因（v1.1.x 历史）

> 本文只做失败模式盘点与归因，不修改 Prompt、Service、Schema、Human Gold 或运行时代码，不运行新的 Judge。
>
> 结论先行：v1.1.x 的主要问题不是“每个案例缺一条 Prompt 特例”，而是缺少统一的 **Claim 语义层**。v1.2.0 应先冻结语义规范，再改 Prompt 与 Service。

## 1. 数据盘点

### 1.1 40 条候选

| 项目 | 数量 | 说明 |
|---|---:|---|
| 候选总数 | 40 | `docs/repair/phase3e/pilot-40-targets.json` |
| Human Gold 基础题 | 13 | 人工确认基础答案 |
| Human Gold Claim | 1 | Q21#3“质量问题不受 7 天无理由限制” |
| Provisional 基础题 | 27 | AI draft，pending human |
| Human Gold claims 总量 | 35 | 已确认 1，待确认 34 |
| key_facts | 41 | 人工确认：supported 38 / evidence_insufficient 2 / ambiguous 1 |

**Human Gold 13 条**：Q05、Q13、Q14、Q15、Q16、Q19、Q22、Q23、Q30、Q35、Q36、Q37、Q40。

**Provisional 27 条**：Q01、Q02、Q03、Q04、Q06、Q07、Q08、Q09、Q10、Q11、Q12、Q17、Q18、Q20、Q21、Q24、Q25、Q26、Q27、Q28、Q29、Q31、Q32、Q33、Q34、Q38、Q39。

**不得把 provisional 结果当作人工 Gold。** 40 条报告只能写作“规模/回归运行”，不能写作“40 条 Human Gold 验收”。

### 1.2 实验完成度

| 运行 | 完成 | 停止点 | 目标通过 | 说明 |
|---|---:|---|---:|---|
| v1.1.1 40 条 | 27/40 | Q22 | 24/27 | 旧 F SHA，已作废 |
| v1.1.3 40 条 | 30/40 | Q30 | 28/30 | 旧 F SHA，已作废 |
| v1.1.5 40 条 | **32/40** | Q32 | **30/32** | 最新，仍未完成 |

- v1.1.5 的 32 条中，Q14 为唯一 non-pass（F unavailable；C=0.7 本次低于目标，历史 0.7/0.7/0.9 方差）；Q32 为停止点。
- 用户提到的“30/40”对应 v1.1.3 的已完成切片；当前最大完成度是 **v1.1.5 的 32/40**。两者都不能当作 40 条完成。

### 1.3 未完成的 8 条与 baseline

| Case | 组 | 状态 | v1.0.0 baseline | 备注 |
|---|---|---|---|---|
| Q33 | PROV | not run | missing | `context_unavailable` |
| Q34 | PROV | not run | missing | only C1 |
| Q35 | HG | not run | old report available | absence/quote 诊断历史 |
| Q36 | HG | not run | old report available | §1/§12 冲突未业务选边 |
| Q37 | HG | not run | missing | only C1 |
| Q38 | PROV | not run | missing | — |
| Q39 | PROV | not run | missing | — |
| Q40 | HG | not run | missing | only C1 |

准确口径：
- **8 条尚未运行**：Q33–Q40。
- **6 条缺 v1.0.0 baseline**：Q33、Q34、Q37、Q38、Q39、Q40。
- Q35、Q36 的 v1.0.0 baseline 在旧 40 条报告中有记录，可复用；但 v1.1.5 尚未跑到它们。
- 因此“补 8 条 baseline”应修正为“跑 8 条 v1.1.5 + 补 6 条 baseline，Q35/Q36 复用旧 baseline”。

### 1.4 非 Judge 质量问题

| 类型 | Case | 说明 |
|---|---|---|
| `context_unavailable` | Q14、Q33 | F 无法评估；不是 F=0，也不是 PASS |
| 只有 C1 | Q22、Q26、Q27、Q34、Q37、Q40 | Faithfulness 可用上下文受限，报告必须注明 |
| 回答内部矛盾（有意） | Q23 | 首句“可以按政策反馈”与后文“已超 24 小时不符合”冲突；C 应低分 |
| 文档冲突未选边 | Q36 | §1/§12 对虚拟商品范围表述不一致；只验证披露，不选 canonical |
| 目标外推/答案缺口 | Q14 | C 缺“未开具前可以修改”，用“未打印/未报销/24 小时”替代 |
| 精确 0.10 边界 | Q25 | C 0.8→0.7 恰好 0.10；按 `>0.10` 不停止 |

### 1.5 40 条状态总表

| ID | 组 | Target | v1.1.5 结果 | v1.0.0 baseline | 备注 |
|---|---|---|---|---|---|
| Q01 | PROV | explicit | PASS 1.0/0.9/0.9 | reused | — |
| Q02 | PROV | — | PASS 1.0/0.9/0.9 | reused | — |
| Q03 | PROV | — | PASS 1.0/0.9/1.0 | reused | — |
| Q04 | PROV | explicit | PASS 1.0/0.9/0.9 | reused | — |
| Q05 | HG | — | PASS 1.0/0.9/0.9 | reused | — |
| Q06 | PROV | — | PASS 1.0/0.9/0.9 | reused | — |
| Q07 | PROV | — | PASS 1.0/0.9/0.9 | reused | — |
| Q08 | PROV | — | PASS 1.0/0.9/0.9 | reused | — |
| Q09 | PROV | — | PASS 1.0/0.9/0.9 | reused | — |
| Q10 | PROV | — | PASS 1.0/0.9/0.9 | reused | 历史 evidence typo |
| Q11 | PROV | explicit | PASS 0.833/0.9/0.9 | reused | 规范性要求 insufficient |
| Q12 | PROV | — | PASS 0.667/0.9/1.0 | reused | 条件外推 |
| Q13 | HG | — | PASS 1.0/0.9/0.9 | reused | 曾 quote 截断 |
| Q14 | HG | explicit | NON-PASS skipped/0.7/1.0 | new | F unavailable；C 方差 |
| Q15 | HG | explicit | PASS 0.75/0.9/1.0 | reused | purpose inference |
| Q16 | HG | — | PASS 1.0/0.9/0.9 | reused | 历史 R over-strict |
| Q17 | PROV | explicit | PASS 1.0/0.9/0.9 | reused | 规则关系已归 meta |
| Q18 | PROV | — | PASS 1.0/0.9/0.9 | reused | — |
| Q19 | HG | — | PASS 0.714/0.9/0.9 | reused | absence/示例推断 |
| Q20 | PROV | explicit | PASS 0.8/0.9/0.9 | reused | generalization |
| Q21 | PROV | explicit | PASS 0.6/0.9/0.9 | reused | Q21#3 insufficient |
| Q22 | HG | explicit | PASS 1.0/0.9/1.0 | reused | 历史 cross-line quote |
| Q23 | HG | explicit | PASS 0.5/0.0/0.9 | reused | 历史 quote 合成 |
| Q24 | PROV | — | PASS 0.667/0.9/1.0 | reused | 额外条件推断 |
| Q25 | PROV | — | PASS 1.0/0.7/0.9 | reused | C 恰好 0.10 |
| Q26 | PROV | — | PASS 1.0/0.9/0.9 | reused | only C1 |
| Q27 | PROV | — | PASS 1.0/0.9/1.0 | reused | only C1 |
| Q28 | PROV | explicit | PASS 0.857/0.9/0.9 | reused | 目标已注册 |
| Q29 | PROV | explicit | PASS skipped/0.9/1.0 | reused | 正确 skip |
| Q30 | HG | explicit | PASS 1.0/0.9/0.9 | reused | scope/region 已归 meta |
| Q31 | PROV | explicit | PASS 0.833/0.9/0.9 | reused | quote/absence 诊断 |
| Q32 | PROV | — | **STOP 0.75/0.9/0.9** | new | “无法确认”误标 factual |
| Q33 | PROV | — | not run | missing | context_unavailable |
| Q34 | PROV | — | not run | missing | only C1 |
| Q35 | HG | explicit | not run | old report | absence/quote |
| Q36 | HG | explicit | not run | old report | 冲突披露 |
| Q37 | HG | — | not run | missing | only C1 |
| Q38 | PROV | — | not run | missing | — |
| Q39 | PROV | — | not run | missing | — |
| Q40 | HG | — | not run | missing | only C1 |

## 2. 归因分类

统一使用五类：

| 代码 | 类别 | 定义 |
|---|---|---|
| A | Claim 原子性 | 合并/拆分/粒度错误，导致分母变化或事实被混合 |
| E | Evidence 定位与支持充分性 | quote 不逐字、跨行/标点/主语拼接、answer 引用、证据不足 |
| S | Scope / Meta / 额外信息 | 范围/地域/文档覆盖/absence/无法确认/规则关系/建议被误建为 factual |
| R | Relationship / Conflict / 条件推导 | 规则关系、条件分支、目的/权益推断、回答内部矛盾、文档冲突 |
| C | Answerability / Context 可用性 | context_unavailable、只有 C1、无有效 claim、skip/failed 边界 |

C/R 指标的校准问题不单独新增第六类，归入 S（额外信息期望）或 R（条件/完整性）并在报告中单列“指标校准”。

## 3. 失败案例逐条记录

> 只记录已观察到的问题；未运行的 Q33–Q40 不推测。`Repeat` 表示同类模式是否重复出现。

| Case | Metric | 现象 | 根因 | 类 | 数据? | Prompt? | Service/Schema? | 业务确认? | Repeat | 规则级修复 |
|---|---|---|---|---|---|---|---|---|---|---|
| Q10 | F | “30 夅内” vs “30 天内”，F 0.5 | 模型抄写单字错 | E | 否 | 是 | 否（校验正确） | 否 | 否 | quote 逐字；typo 作为诊断，不归一化数字 |
| Q11 | F | “需提供照片/视频凭证” insufficient，F 0.833 | 规范性要求无上下文依据 | E | 否 | 是 | 否 | 否 | 是（Q35 类） | 规范性要求 factual；无依据必须 insufficient |
| Q12 | F | “不含节假日/银行延迟” insufficient，F 0.667 | 条件外推 | R | 否 | 是 | 否 | 否 | 是（Q24/Q28） | 只支持文档明确写的条件；外部条件不进 supported |
| Q14 | F/C | F skipped；C=0.7/0.9 不稳 | context 不可用；回答缺“未开具前” | C | 是 | 部分 | 否 | 是 | 否 | F unavailable 独立；C 用 key_facts 而非单次 judge |
| Q15 | F | purpose inference insufficient，F 0.5–1.0 | 目的/后续安排推断无依据 | A/R | 否 | 是 | 否 | 否 | 是（Q28） | 目的/权益推断单独 claim；无依据 insufficient |
| Q16 | R | 直接完整回答 R=0.7 | R 裁判要求额外步骤 | S | 否 | 是（R） | 否 | 否 | 可能 | 单一部分直接回答不因缺建议降 0.9–1.0 |
| Q17 | F | 规则关系“与满 99 无关” factual/insufficient，F 0.8 | 规则关系推断被建 factual | S | 否 | 是 | 否 | 否 | 是（Q19/Q31/Q32/Q35） | 规则关系/独立性归 meta，不进分母 |
| Q19 | F | “未区分退款原因” factual/insufficient；示例日期推断 | absence/meta + 合成示例 | S/R | 否 | 是 | 否 | 否 | 是（Q31/Q32） | absence/meta 不进分母；禁止合成示例 |
| Q20 | F | “适用于所有订单” insufficient，F 0.8 | 全称 generalization 无依据 | R | 否 | 是 | 否 | 否 | 是（Q28） | 全称量词需明确依据；无依据 insufficient |
| Q21 | F | Q21#3 insufficient，F 0.6 | 条件/期限推断 | R | 部分（HG claim 已复核） | 是 | 否 | 否（已复核） | 是（Q28） | 只支持文档明确条件；Q21#3 保持 insufficient |
| Q22 | F | cl1/cl4 cross-line quote，F 0.4 | 删除换行拼接 | E | 否 | 是 | 否（校验正确） | 否 | 是（Q23/Q31/Q35/Q36） | 最短单行连续子串；跨行保换行 |
| Q23 | F | “生鲜食品质量问题需…” quote 合成，F 0.0 | 主语+谓词拼接 | E | 否 | 是 | 否（校验正确） | 否 | 是（Q13/Q22） | 最短子串；不得拼主语+谓词 |
| Q24 | F | “改派可能产生额外运费/不保证成功” insufficient | 额外条件推断 | R | 否 | 是 | 否 | 否 | 是（Q12/Q28） | 额外条件/概率不进 supported |
| Q25 | C | C 0.8→0.7，恰好 0.10 | C 对额外正确信息偏严 | S | 否 | 是（C） | 否（阈值比较需容差） | 否 | 可能 | 正确额外信息不记 wrong_fact；`>0.10` 用容差 |
| Q28 | F | “可申请催促/补偿/取消” insufficient，F 0.857 | 权益推断无依据 | R | 否 | 是 | 否 | 否 | 是（Q15/Q21） | 补偿/取消等权益需明确写；否则 insufficient |
| Q29 | F | F skipped | 全部 absence/meta，正确 | S | 否 | 否 | 否 | 否 | 是（Q33） | 全部 non_factual → skip；不是 1.0 |
| Q30 | F | 范围/地域推断 factual/insufficient，F 0.25→1.0 | scope/region 误建 factual | S | 否 | 是 | 否 | 否 | 是（Q31/Q32/Q35） | scope/region 归 meta/absence；混合句拆分 |
| Q31 | F | “未规定上门取件”“未涉及取件方式” factual/insufficient；quote 诊断 | absence/meta + quote | S/E | 否 | 是 | 否 | 否 | 是（Q32/Q35） | absence/meta 不进分母；quote 最短子串 |
| Q32 | F | “无法确认积分支持礼品兑换” factual/insufficient，F 0.75 | 不确定结论被建 factual | S | 否 | 是 | 否 | 否 | 是（Q31/Q35） | 无法确认/信息不足 → meta/absence |
| Q35 | F | “物流时效未明确说明” factual/insufficient；2 条 quote 诊断 | absence + quote | S/E | 否 | 是 | 否 | 否 | 是（Q31/Q32） | absence 归 non_factual；quote 最短子串 |
| Q36 | F | cl1 meta 总起 + cl6 合并 §1/§12，F 0.75→1.0 | 原子性 + 冲突合并 | A/E | 否 | 是 | 否 | 部分（冲突口径未选边） | 是（Q22/Q23） | 总起句 meta；§1/§12 拆两条；冲突仅 variant |
| Q33 | F | F skipped | context_unavailable | C | 是 | 否 | 否 | 否 | 是（Q14） | F unavailable；C/R 独立 |
| Q34/Q37/Q40 | F | 只有 C1 | 上下文受限 | C | 是 | 否 | 否 | 否 | 是 | 报告注明；不据此判 F 退化 |
| Q38/Q39 | — | 未运行 | — | — | — | — | — | — | — | 不推测 |

## 4. 跨案例模式

### P1 Evidence 定位（Q10/Q22/Q23/Q31/Q35/Q36/Q13）

- 跨行拼接、标点改变、主语+谓词合成、answer 自身引用。
- 这些失败都被 Service 正确降级；不是 Service 校验过严，而是 Prompt 没有稳定约束“最短连续子串”。
- v1.1.3 的“结尾一律不带标点 + 最短子串 + contexts-only”已显著降低，但仍会出现（Q31/Q35）。
- v1.2.0 应把 evidence 约束做成统一的输出契约和校验，不再靠案例 few-shot。

### P2 Scope / Meta / absence / uncertainty（Q19/Q29/Q30/Q31/Q32/Q35）

- “未提及/未涉及/未规定/无法确认/默认适用于/不依赖另一规则”被反复标成 factual/insufficient。
- 这是 F 分母污染的主要来源；Q30 从 0.25 修到 1.0 就是证据。
- v1.2.0 需要明确的 non_factual 子类型：`absence`、`scope`、`relationship`、`uncertainty`、`meta`、`advice`。
- 只有文档明确写出的规则、条件、范围才进 factual 分母。

### P3 Relationship / 条件推导（Q12/Q15/Q17/Q20/Q21/Q24/Q28）

- 规则关系、目的、补偿/取消权益、全称 generalization、外部条件，模型倾向“合理推断为 supported”。
- 这些不是事实错误，而是“推断强度”问题；应按 insufficient，而不是 supported。
- Q21#3 是人工确认的 insufficient，Q28 是后来注册的 provisional 目标；应统一规则，不再逐案例加目标。

### P4 Claim 原子性（Q15/Q19/Q23/Q36/Q21）

- 合并导致分母减少（Q15 2 scorable），拆得过细导致分母膨胀（Q19 示例）。
- Q36 的 cl6 把 §1/§12 合并，直接影响冲突识别。
- v1.2.0 需要“事实/条件/关系/absence”四类原子，而不是只靠自然语言“一个事实”。

### P5 C/R 校准（Q14/Q16/Q25）

- Q14 C 0.7/0.9 不稳，且回答本身缺金标条件；应作为数据/答案问题，不应归因 F。
- Q16 R 0.7 是 judge over-strictness；直接完整回答不应要求额外步骤。
- Q25 C 0.8→0.7 恰好 0.10；`>0.10` 需浮点容差，且“正确额外信息”不应算 wrong_fact。
- C/R 需要独立校准集，不应只用 F 的 40 条。

### P6 Context 可用性（Q14/Q33 + C1-only）

- `context_unavailable` 是“不可评估”，不是 0 分，也不是 PASS。
- C1-only 案例应在报告中标注覆盖率；不能与双上下文案例混在一起计算 F 均值。

## 5. 不是 Judge 失败的项

- **Q14 F**：`context_unavailable`，F 不可评估。C=0.7/0.9 是答案与金标差异，不是 F Prompt 失败。
- **Q29 F**：全部 absence/meta，正确 `skipped(no_scorable_claims)`；不是 1.0。
- **Q23 C=0.0**：回答首句与后文矛盾，C 低分合理；F 的问题是 quote，不是“回答不 faithful”。
- **Q25 C=0.7**：恰好 0.10，不是 >0.10；且无误导性 wrong_fact。
- **Q35/Q36 的 quote 诊断**：目标内，属于已知诊断；不能因此把 provisional 目标抬高或降低。
- **Q36 canonical 冲突口径**：业务未选边；只验证“披露冲突”，不把某一口径写成 Gold。

## 6. 归因汇总

| 类别 | 主要案例 | 判断 |
|---|---|---|
| A Claim 原子性 | Q15、Q19、Q23、Q36、Q21 | 需要统一原子性规范，不能逐案例 few-shot |
| E Evidence | Q10、Q22、Q23、Q31、Q35、Q36、Q13 | Prompt 约束 + Service 校验共同问题；Service 目前正确 |
| S Scope/Meta/额外信息 | Q16、Q17、Q19、Q30、Q31、Q32、Q35、Q25 | 最大类；v1.2.0 的核心 |
| R Relationship/条件 | Q12、Q15、Q20、Q21、Q24、Q28 | 推断强度问题；统一 insufficient 规则 |
| C Context/Answerability | Q14、Q33、C1-only | 数据/报告边界，不是 Prompt 特例 |

## 7. 结论

1. v1.1.x 的修补方式已经证明会不断产生新的边界案例；继续加案例 few-shot 不可持续。
2. 失败主要集中在 **Scope/Meta/absence/uncertainty** 与 **Evidence 最短子串**，不是模型“不会回答”。
3. v1.2.0 应先冻结语义规范，再做 Prompt 与 Service 的通用改造。
4. 不允许把 provisional 结果、单次模型输出或 known miss 写成 Human Gold 通过。
