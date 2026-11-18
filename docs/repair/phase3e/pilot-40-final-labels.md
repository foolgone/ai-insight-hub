# Phase 3E 40 条 Final Labels（冻结）

> 文件：`pilot-40-final-labels.json`
> 状态：**frozen**
> 冻结日期：2026-11-18
> 冻结人：江晚
> SHA256：`f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb`
> 校验：`pilot-40-final-labels.validation.json`（19 项全部通过）

## 1. 用途

本文件是 **40 条报告的唯一分类来源**。

- 13 条 Human Gold 的 `final_category` 来自 `human-gold.json`；
- 27 条 provisional 的 `final_category` 使用 `candidates.json` 原始 category；
- 40 条报告不得再混用 `candidates.json` 的原始分类；
- 任何分类变更必须新开版本并重算 SHA，不得在原文件上覆盖。

## 2. 汇总

| 项 | 数量 |
|---|---:|
| 总行数 | 40 |
| human_gold | 13 |
| provisional | 27 |
| direct | 12 |
| multi | 8 |
| constraint | 9 |
| unanswerable | 6 |
| ambiguous | 5 |

### 分类变更

| Case | 原 candidates category | final_category | 来源 |
|---|---|---|---|
| Q15 | multi | **direct** | human-gold.json |
| Q16 | multi | **constraint** | human-gold.json |
| Q40 | ambiguous | **direct** | human-gold.json |

## 3. Context 可用性

| 状态 | 数量 | Cases |
|---|---:|---|
| 2 个上下文 | 32 | 其余 |
| 1 个上下文（C1-only） | 6 | Q22、Q26、Q27、Q34、Q37、Q40 |
| unavailable | 2 | Q14、Q33 |

## 4. Target 来源

| 来源 | 数量 |
|---|---:|
| matrix | 5 |
| pilot10 | 5 |
| additional | 6 |
| none | 24 |

- matrix：Q11、Q21、Q23、Q35、Q36
- pilot10：Q01、Q04、Q17、Q29、Q31
- additional：Q14、Q15、Q20、Q22、Q28、Q30

## 5. Baseline 状态

| 状态 | 数量 |
|---|---:|
| reused | 30 |
| new | 2（Q14、Q32） |
| available_old_run | 2（Q35、Q36） |
| missing | 6（Q33、Q34、Q37、Q38、Q39、Q40） |

`reused + new + available_old_run + missing = 40`。

## 6. Known issues

已记录：
- Q14：`context_unavailable;C_variance;known_non_pass`
- Q32：`uncertainty_misclass`
- Q35：`absence_quote_diagnostic`
- Q36：`condition_sentence;conflict_disclosure`
- Q10：`evidence_typo_history`
- Q17：`policy_relationship_target_reapproval`
- Q30：`policy_scope_target_reapproval`
- Q19/Q31：absence/meta 分类变化
- Q16：R over-strict 历史
- Q23：quote 合成/内部矛盾历史
- Q25：C 恰好 0.10
- Q29：正确 skip

完整字段见 JSON 的 `known_issue` / `notes`。

## 7. 校验

`pilot-40-final-labels.validation.json` 检查了 19 项，全部通过，包括：

- 40 行、ID Q01–Q40、无重复；
- 13 HG + 27 provisional；
- 分类 12/8/9/6/5；
- Q15→direct、Q16→constraint、Q40→direct，且来源为 `human-gold.json`；
- 13 条 HG 分类与 `human-gold.json` 一致；
- 27 条 provisional 分类与 `candidates.json` 一致；
- Q14/Q33 为 `context_unavailable`；
- C1-only 集合为 Q22/Q26/Q27/Q34/Q37/Q40；
- target_source 仅 `matrix/pilot10/additional/none`；
- baseline 30+2+2+6=40；
- Q14/Q32/Q35/Q36 known_issue 非空。

## 8. 冻结边界

- 本文件只冻结 **分类**，不冻结目标；
- Q17/Q30/Q32 等目标仍需按 `13-phase3e-acceptance-plan.md` 重新签字；
- 未创建/激活 v1.2.0；
- 未修改 Prompt/Service/Schema/API/DB；
- 未运行 10/40 条或其它 Judge 实验；
- 未进入 Phase 4。
