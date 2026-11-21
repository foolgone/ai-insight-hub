# M1-C C4 报告模板

> 用途：C4 静态结果与后续经单独批准的 10/40 Judge 报告统一模板。
> 本模板不产生结果；不得用模板冒充实测。
> 固定规则：HG 13 / provisional 27 分开；invalid/skipped/failed/unprocessed 单列；F_strict 只作诊断；Q17/Q32 的 v1.2.0 预期值不得写成实测。

## 1. 资产与 SHA

| 项 | 值 |
|---|---|
| 报告类型 | `static_target_regression` / `inventory` / `judge_10` / `judge_40` |
| 生成日期 | `YYYY-MM-DD` |
| target | `pilot-40-targets-v1.2.0-v1.0.2.json` |
| target SHA256 | `3ee15dfc…` |
| final_labels | `pilot-40-final-labels.json` |
| final_labels SHA256 | `f139623f…` |
| prompt version | `v1.2.0`（未激活时写 `not_runtime`） |
| prompt SHA256 | `…` / `unavailable` |
| schema version | `rag_judge_schema_v3` / `not_runtime` |
| metric version | `v3` / `not_runtime` |
| dataset checksum | `…` / `unavailable` |
| 是否 Judge 运行 | `yes` / **`no`** |

## 2. 40 条分组

| 维度 | 计数 |
|---|---:|
| 总数 | 40 |
| human_gold | 13 |
| provisional | 27 |
| direct / constraint / multi / unanswerable / ambiguous | 12 / 9 / 8 / 6 / 5 |
| baseline reused / missing / new / available_old_run | 30 / 6 / 2 / 2 |
| context 2 / 1 / unavailable | 32 / 6 / 2 |

固定披露：

```text
baseline_missing: Q33/Q34/Q37/Q38/Q39/Q40
baseline_delta: unavailable
```

## 3. human_gold 13 明细

| Case | category | status | F_coverage | F_strict | C | R | invalid/skipped/failed | known issue |
|---|---|---|---|---|---|---|---|---|
| Q05 | … | … | … | … | … | … | … | … |
| Q13 | … | … | … | … | … | … | … | … |
| Q14 | multi | skipped(context_unavailable) | — | — | … | … | … | context_unavailable / C_variance / known_non_pass |
| Q15 | … | … | … | … | … | … | … | … |
| Q16 | … | … | … | … | … | … | … | … |
| Q19 | … | … | … | … | … | … | … | … |
| Q22 | … | … | … | … | … | … | … | C1-only |
| Q23 | … | … | … | … | … | … | … | … |
| Q30 | … | … | … | … | … | … | … | … |
| Q35 | … | … | … | … | … | … | … | old run only |
| Q36 | … | … | … | … | … | … | … | old run only |
| Q37 | … | … | … | … | … | … | … | C1-only / baseline_missing |
| Q40 | … | … | … | … | … | … | … | C1-only / baseline_missing / category_changed |

## 4. provisional 27 明细

同第 3 节列；不得与 HG 合并均值或通过率。

## 5. 目标回归

| Case | target F | F_coverage | F_strict | source | 结果 |
|---|---:|---:|---:|---|---|
| Q11 | 0.6–0.9 | … | … | observed v1.1.5 | PASS/FAIL |
| Q17 | 0.7–0.9 | … | … | **expected v1.2.0** | PASS/FAIL |
| Q21 | 0.6–0.7 | … | … | observed v1.1.5 | PASS/FAIL |
| Q23 | 0.4–0.5 | … | … | observed v1.1.5 | PASS/FAIL |
| Q32 | 0.9–1.0 | … | … | **expected v1.2.0** | PASS/FAIL |

## 6. 10 条闸门

| Case | expected status | F target | 结果 | 备注 |
|---|---|---|---|---|
| Q01 | evaluated | 0.9–1.0 | PASS/FAIL/BLOCKED | — |
| Q04 | evaluated | 1.0 | … | — |
| Q11 | evaluated | 0.6–0.9 | … | normative_requirement |
| Q17 | evaluated | 0.7–0.9 | … | policy_relationship |
| Q21 | evaluated | 0.6–0.7 | … | Q21#3_insufficient |
| Q23 | evaluated | 0.4–0.5 | … | internal_contradiction |
| Q29 | skipped(no_scorable_claims) | — | … | correct_skip |
| Q31 | evaluated | 0.6–1.0 | … | quote_absence |
| Q35 | evaluated（待批准） | 0.8–1.0 | … | old run only |
| Q36 | evaluated（待批准） | 0.8–1.0 | … | old run only |

## 7. 指标口径

| 指标 | 值 |
|---|---|
| F_coverage | … |
| F_strict | …（诊断，不作目标） |
| C | … |
| R | … |
| invalid | … |
| skipped | … |
| failed | … |
| unprocessed | … |
| insufficient_count | … |
| insufficient_ratio | … |
| all_insufficient_count | … |

规则：

- mean 只计 evaluated；
- invalid/failed/skipped 不进均值；
- Q14/Q33 context_unavailable 不进入 F 目标通过率；
- C1-only 6 条（Q22/Q26/Q27/Q34/Q37/Q40）单列；
- baseline_missing 不计算 delta。

## 8. Known issue 决策

| Case | issue | 决策（接受/修复/延期） | 理由 |
|---|---|---|---|
| … | … | … | … |

## 9. 结论

- 状态只能写 `implemented` / `verified` / `blocked`；
- 不得自行写 `accepted`；
- 10/40 Judge 运行需单独批准；
- 不激活 v1.2.0、不改 Prompt、不启动 M2/M3。
