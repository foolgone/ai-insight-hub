# M1-C C4：目标回归 / 10 条闸门准备 / 40 条盘点与报告模板

> 状态：C4 设计/范围报告，待人工审核；**不跑 Judge、不激活 v1.2.0、不改 Prompt、不启动 M2/M3**。
> 实现状态：C4 静态目标回归/40 条盘点/报告模板已完成并本地验证（2026-11-20，`implemented/verified`）；10/40 Judge 未运行。
> 依据：`19-m1b-003-freeze-draft.md`（r2）、`23-m1c-stage1-test-list.md`（rev2.1）、`25-m1c-c3-design-scope.md`（rev2.1）、`pilot-40-targets-v1.2.0-v1.0.2.json`、`pilot-40-final-labels.json`、`m1b003-static-recalc.json/md`。
> 范围：**仅 C4 设计与范围**；C4 测试/脚本需审核通过后编写；10/40 Judge 运行需单独批准。

## 0. 结论与边界

1. C4 先做**静态目标回归**：Q11/Q17/Q21/Q23/Q32，使用现有静态 claim/重算数据，不调用 Judge。
2. C4 做**10 条闸门准备**：Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36 的前置条件、expected status、known issue、通过口径；不执行。
3. C4 做**40 条完整性盘点**：分类/目标/context/baseline 对齐；6 条缺失 baseline、Q14/Q33 context_unavailable、6 条 C1-only 单列。
4. C4 产出**报告模板**：HG 13 / provisional 27 分开；invalid/skipped/failed/unprocessed、insufficient 口径、SHA 追溯、known issue 决策。
5. C4 **不跑 Judge、不激活 v1.2.0、不改 Prompt、不启动 M2/M3**；10/40 Judge 运行需单独批准。

## 1. 输入资产与冻结 SHA

| 资产 | SHA256 / 状态 |
|---|---|
| `pilot-40-targets-v1.2.0-v1.0.2.json` | `3ee15dfc…`；`freeze_draft_pending_human`；40 行；数值与 v1.0.1 相同 |
| `pilot-40-final-labels.json` | `f139623f…`；`frozen`；40 行 |
| `pilot-40-targets-v1.2.0.json`（v1.0.1） | `34357b34…`；只读，不作为 v1.0.2 来源 |
| `m1b003-static-recalc.json` | `53787fbb…`；`static_recalculation_not_judge_run` |
| `m1b003-static-recalc.md` | 静态重算说明；Q17/Q32 expected 转换 |
| `19-m1b-003-freeze-draft.md`（r2） | 指标/生命周期/invalid 契约 |
| `25-m1c-c3-design-scope.md`（rev2.1） | C3 实现契约 |

引用规则：

- 目标值只读 `pilot-40-targets-v1.2.0-v1.0.2.json`；
- 分类只读 `pilot-40-final-labels.json`；
- Q17/Q32 的 v1.2.0 预期值只来自 `m1b003-static-recalc`，不是 Judge 实测；
- 任何报告必须写 target SHA + labels SHA + prompt/schema/metric version。

## 2. 静态目标回归（Q11/Q17/Q21/Q23/Q32）

不跑 Judge；用现有静态 claim/重算数据验证公式、分母、目标映射。

| Case | target F | F_coverage | F_strict | 来源 | 预期 |
|---|---:|---:|---:|---|---|
| Q11 | 0.6–0.9 | **0.833333** | **1.0** | observed v1.1.5 | PASS |
| Q17 | 0.7–0.9 | **0.800000**（v1.2.0 预期） | **1.0** | expected v1.2.0（cl5 policy_relationship factual/insufficient） | PASS（标记 expected） |
| Q21 | 0.6–0.7 | **0.600000** | **1.0** | observed v1.1.5 | PASS |
| Q23 | 0.4–0.5 | **0.500000** | **0.750000** | observed v1.1.5 | PASS |
| Q32 | 0.9–1.0 | **1.000000**（v1.2.0 预期） | **1.0** | expected v1.2.0（cl1 uncertainty non_factual） | PASS（标记 expected） |

硬规则：

- Q17/Q32 不得写成“Judge 已实测”；
- 目标回归只验证公式/分母/目标映射，不验证 Judge 语义；
- F_strict 只记录，不作为目标通过率；
- 未跑 Judge；不生成新的 Judge 结果。

## 3. 10 条闸门准备（不执行）

| Case | group / category | context | target | baseline | expected status | known issue |
|---|---|---|---|---|---|---|
| Q01 | provisional / direct | 2 | F 0.9–1.0, C 0.9–1.0, R 0.8–1.0 | reused | evaluated | — |
| Q04 | provisional / direct | 2 | F 1.0, C 0.8–1.0, R 0.9–1.0 | reused | evaluated | — |
| Q11 | provisional / multi | 2 | F 0.6–0.9, C 0.8–1.0, R 0.9–1.0 | reused | evaluated | normative_requirement |
| Q17 | provisional / multi | 2 | F 0.7–0.9, C 0.8–1.0, R 0.8–1.0 | reused | evaluated | policy_relationship_target_reapproval |
| Q21 | provisional / constraint | 2 | F 0.6–0.7 | reused | evaluated | Q21#3_insufficient |
| Q23 | human_gold / constraint | 2 | F 0.4–0.5, C 0.0–0.2, R 0.7–1.0 | reused | evaluated | quote_synthesis_history; internal_contradiction |
| Q29 | provisional / unanswerable | 2 | F skipped; C 0.9–1.0, R 0.9–1.0 | reused | skipped(no_scorable_claims) | correct_skip |
| Q31 | provisional / unanswerable | 2 | F 0.6–1.0, C 0.8–1.0, R 0.8–1.0 | reused | evaluated | quote_absence_diagnostic |
| Q35 | human_gold / ambiguous | 2 | F 0.8–1.0, C 0.7–1.0, R 0.8–1.0 | available_old_run | evaluated（待单独批准） | absence_quote_diagnostic |
| Q36 | human_gold / ambiguous | 2 | F 0.8–1.0, C 0.5–0.6, R 0.8–1.0 | available_old_run | evaluated（待单独批准） | condition_sentence; conflict_disclosure |

闸门口径（后续执行时）：

- Q29 的 F 必须是 `skipped(no_scorable_claims)`，不得 0.0、不得以 skipped 兜底其它案例；
- Q35/Q36 只使用 old run 作为参考，不把旧结果冒充 v1.2.0 实测；
- 其余 8 条 F 必须 evaluated；F_coverage/F_strict 按目标/诊断口径记录；
- C/R 只在对应 target 存在时判定；
- 10 条闸门执行需**单独批准**，C4 设计不执行。

## 4. 40 条完整性盘点

### 4.1 分组与分类

| 维度 | 计数 |
|---|---:|
| 总数 | 40 |
| `human_gold` | 13 |
| `provisional` | 27 |
| `direct` | 12 |
| `constraint` | 9 |
| `multi` | 8 |
| `unanswerable` | 6 |
| `ambiguous` | 5 |

### 4.2 Baseline 状态

| baseline_status | 数量 | 处理 |
|---|---:|---|
| `reused` | 30 | 可用于 baseline delta |
| `missing` | 6 | 标记 `baseline_missing`；不计算 delta；不跑 Judge |
| `new` | 2 | Q14/Q32；Q14 context_unavailable，Q32 v1.2.0 新目标 |
| `available_old_run` | 2 | Q35/Q36；只作参考，不冒充 v1.2.0 |

**6 条缺失 baseline**：Q33、Q34、Q37、Q38、Q39、Q40。

处理方案（C4 推荐 A）：

- **A（推荐）**：C4 只标记 `baseline_missing`，从 baseline delta/改进声明中排除，报告中单列；不跑 Judge。
- B：后续单独批准 v1.1.5 baseline Judge run 补齐；不在 C4 执行。

### 4.3 Context 与特殊案例

| 类别 | Case | 处理 |
|---|---|---|
| `context_unavailable` | Q14、Q33 | F unavailable/skipped；不进入 F 目标通过率；单列 |
| C1-only（单 context，6 条） | Q22、Q26、Q27、Q34、Q37、Q40 | 单列；F 可 evaluated，但不与双 context 混合解释 |
| `available_old_run` | Q35、Q36 | 旧 run 仅参考；v1.2.0 需单独批准再跑 |
| `category_changed` | Q40 | 使用 final_labels 的 `direct`；不沿用旧分类 |
| `known_non_pass` | Q14 | 保留 non-pass；不得用 skipped 洗成 pass |

### 4.4 40 条已知问题清单

报告必须保留 `final_labels.known_issue`，至少包含：

- Q10 evidence typo history；
- Q11 normative_requirement；
- Q12 conditional_inference；
- Q14 context_unavailable / C_variance / known_non_pass；
- Q16 R_overstrict_history；
- Q17 policy_relationship_target_reapproval；
- Q19 absence/meta classification；
- Q20 policy_scope_generalization；
- Q21 Q21#3_insufficient；
- Q22 cross_line_quote_history；
- Q23 quote_synthesis_history / internal_contradiction；
- Q25 C exact 0.10；
- Q26/Q27 C1_only；
- Q29 correct_skip；
- Q30 policy_scope_target_reapproval；
- Q31 quote_absence_diagnostic；
- Q32 uncertainty_misclass；
- Q33 context_unavailable / not_run；
- Q34/Q37/Q40 C1_only / not_run；
- Q35 absence_quote_diagnostic；
- Q36 condition_sentence / conflict_disclosure；
- Q40 category_changed。

## 5. 报告模板（C4 设计）

报告固定分节：

1. **资产与 SHA**：target v1.0.2 SHA `3ee15dfc…`、final_labels SHA `f139623f…`、prompt version/SHA、schema version、metric version、dataset checksum。
2. **40 条分组**：HG 13 / provisional 27；分类计数；baseline/context 分布。
3. **HG 13 明细**：逐条 status、F_coverage/F_strict、C/R、invalid/skipped/failed、known issue。
4. **Provisional 27 明细**：同上，不与 HG 混算。
5. **目标回归**：Q11/Q17/Q21/Q23/Q32；Q17/Q32 标记 expected。
6. **10 条闸门**：Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36；逐条 PASS/FAIL/BLOCKED。
7. **40 条完整性**：missing baseline、context_unavailable、C1-only 单列。
8. **指标口径**：
   - `F_coverage` 主指标；`F_strict` 诊断；
   - `invalid/skipped/failed/unprocessed` 单列；
   - `insufficient_count` / `insufficient_ratio` / `all_insufficient_count`；
   - mean 只计 evaluated。
9. **Known issue 决策**：接受 / 修复 / 延期；不得静默忽略。
10. **结论**：只写 `implemented/verified` 或 `blocked`，不自动写 `accepted`。

禁止：

- 合并 HG 与 provisional；
- 把 invalid/skipped/failed 混成“失败”；
- 把 Q17/Q32 expected 写成实测；
- 把 F_strict 当目标通过率；
- 缺 prompt/schema/metric SHA。

## 6. 计划文件与脚本（已按本设计实现）

| 文件 | 用途 |
|---|---|
| `docs/repair/26-m1c-c4-design-scope.md` | 本设计 |
| `docs/repair/phase3e/m1c_c4_static_targets.py` | 静态目标回归 Q11/Q17/Q21/Q23/Q32 |
| `docs/repair/phase3e/m1c-c4-static-targets.json` / `.md` / `.sha256` / `.validation.json` | 静态目标回归输出与校验 |
| `docs/repair/phase3e/m1c_c4_inventory.py` | 40 条分类/目标/context/baseline 盘点 |
| `docs/repair/phase3e/m1c-c4-inventory.json` / `.md` / `.sha256` / `.validation.json` | 40 条盘点输出与校验 |
| `docs/repair/phase3e/m1c-c4-report-template.md` | 报告模板 |

约束：

- 脚本只读现有 JSON/MD；不调用 Judge、不写 DB、不激活 v1.2.0；
- 输出必须带 SHA；
- 脚本失败时不得回退成“手工结论”。

## 7. 门禁

- C4 设计通过后，才允许写 C4 脚本/测试；
- 静态目标回归通过后，才允许准备 10 条闸门；
- 10/40 Judge 运行需**单独批准**；C4 本轮不执行；
- 不激活 v1.2.0、不改 Prompt、不启动 M2/M3；
- C4 完成后只能写 `implemented/verified`，不能自行 accepted。

## 8. 待人工确认

| # | 选择 | 建议 |
|---|---|---|
| 1 | 6 条 missing baseline | 方案 A：标记 baseline_missing、排除 delta、不跑 Judge |
| 2 | Q35/Q36 available_old_run | 仅参考；v1.2.0 实测另行批准 |
| 3 | Q14/Q33 context_unavailable | 单列，不计 F 目标通过率 |
| 4 | C1-only 6 条 | 单列；不与双 context 混合解释 |
| 5 | summary root-only | 保持 C3 A 方案；最新 attempt 汇总留 M2/后续 |
| 6 | P2 三项（null 防御、missing_expected_metrics、summary key） | C4 不改；单独小修 |
