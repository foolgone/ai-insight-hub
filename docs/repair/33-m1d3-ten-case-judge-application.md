# M1-D-3 v1.2.1 10 条 Judge 申请

> 状态：`pending_approval`。**新申请，不复用 v1.2.0 批准；未运行 Judge、未创建 Run、未激活。**
> application SHA：`7077477ef6108dcf7996b5ce17b2c492752cbbc85644856d91abdb3b5f45da28`
> validation SHA：`1f2fdb3a4eee6fd787d62b13efffdf0980faa108064dcc16a18e91fefea607aa`
> Prompt：`v1.2.1` / `frozen` / rubric `v1.2.0` / schema v3 / metric v3
> MANIFEST SHA：`8bdd673cd44ed772dfc1630280e571d4cdd8ed786066eb72eb553a9be8b0b278`
> fixture SHA：`dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70`
> target SHA：`3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846`

## 1. 冻结资产

| 项 | 值 |
|---|---|
| prompt_version | `v1.2.1` |
| F SHA | `9efdc64d…` |
| C SHA | `a50520de…` |
| R SHA | `a5386070…` |
| MANIFEST SHA | `8bdd673c…` |
| rubric_version | `v1.2.0` |
| Schema / Metric | `rag_judge_schema_v3` / `v3` |
| target | `pilot-40-targets-v1.2.0-v1.0.2.json` |
| 默认版本 | `v1.0.0` |

## 2. 10 个 Cases

| Case | group | category | context | baseline | F target | C target | R target | known issue |
|---|---|---|---:|---|---|---|---|---|
| Q01 | provisional | direct | 2 | reused | 0.9–1.0 | 0.9–1.0 | 0.8–1.0 | — |
| Q04 | provisional | direct | 2 | reused | 1.0 | 0.8–1.0 | 0.9–1.0 | — |
| Q11 | provisional | multi | 2 | reused | 0.6–0.9 | 0.8–1.0 | 0.9–1.0 | normative_requirement |
| Q17 | provisional | multi | 2 | reused | 0.7–0.9 | 0.8–1.0 | 0.8–1.0 | policy_relationship_target_reapproval |
| Q21 | provisional | constraint | 2 | reused | 0.6–0.7 | — | — | Q21#3_insufficient |
| Q23 | human_gold | constraint | 2 | reused | 0.4–0.5 | 0.0–0.2 | 0.7–1.0 | quote_synthesis_history;internal_contradiction |
| Q29 | provisional | unanswerable | 2 | reused | skipped | 0.9–1.0 | 0.9–1.0 | correct_skip |
| Q31 | provisional | unanswerable | 2 | reused | 0.6–1.0 | 0.8–1.0 | 0.8–1.0 | quote_absence_diagnostic |
| Q35 | human_gold | ambiguous | 2 | available_old_run | 0.8–1.0 | 0.7–1.0 | 0.8–1.0 | absence_quote_diagnostic |
| Q36 | human_gold | ambiguous | 2 | available_old_run | 0.8–1.0 | 0.5–0.6 | 0.8–1.0 | condition_sentence;conflict_disclosure |

固定口径：Q29 F 必须 `skipped(no_scorable_claims)`；Q35/Q36 用 fixture 固定旧 run 输入；Q36 C 双报不参与 PASS/FAIL。

## 3. 执行载体

| 项 | 值 |
|---|---|
| execution_mode | `judge_only_fixture` |
| Service entrypoint | `rag_judge_service.judge_trace` |
| session / DB | `None` / 不写 DB |
| adapter / top_k | 不适用 / 不适用 |
| model / temperature / max_tokens | `qwen-max` / `0.0` / `8192` |
| judge_prompt_version | `v1.2.1` |
| default_prompt_version | `v1.0.0` |
| synthetic trace | `adapter=fixture`、`mode=query`、`context_source=agent_chat`、`status=success`、`retrieved_contexts` 来自 fixture |
| driver | 只汇总 `JudgeOutcome`，不重写 F 计分、不创建 Run |

## 4. Q11 修复证据

| 项 | 结果 |
|---|---|
| bad 非连续 quote | `invalid(contract_violation)` + `quote_not_found` |
| good 精确 claim + 连续 quote | `evaluated 1.0` |
| tests | `test_v121_bad_noncontiguous_quote_is_invalid` / `test_v121_good_contiguous_quote_is_supported` |
| fixture | `dc7be14b…`；未改 fixture |

## 5. 预算 / 重复 / Q36

| 项 | 值 |
|---|---:|
| 主运行 | 10 cases × 3 = 30 calls |
| HG 重复 | Q23/Q35/Q36 固定 3 次；Q23 3/3、Q35/Q36 ≥2/3 |
| 计划调用 | 48 |
| 执行重试 reserve | 3 |
| 最大调用 | 51 |
| 预计成本 / 上限 / ceiling | CNY 0.45 / 0.760 / **1.00** |
| Q36 C | base 0.5–0.6 与 variant 0.9–1.0 双报，只作诊断 |

## 6. 停止条件

| code | 条件 |
|---|---|
| `preflight_failure` | fixture SHA、10 个 case/answer/contexts/gold、LLM endpoint/model/credential、Prompt/MANIFEST SHA 或 22/22 validation 任一不满足 |
| `invalid_contract` | 任一 case/metric 出现 invalid(contract_violation)，包括 schema/subtype/evidence/quote/conflict 违约 |
| `failed_execution` | 任一 case/metric 出现 failed(execution) |
| `hg_supported_quote_invalid` | Q23/Q35/Q36 任一 supported claim 的 quote 非逐字、跨片段拼接或引用 answer |
| `q29_not_skipped` | Q29 的 F 不是 skipped(no_scorable_claims) |
| `unexplained_drop` | 有 baseline 的 case 出现 old - new > 0.10 + 1e-9 的未解释下降 |
| `second_typo_or_number_change` | 第二次出现 evidence typo、数字/日期/金额改动 |
| `missing_case_output` | 10 个 case 未全部产出 3 个指标结果，或任一 case 缺 F/C/R |
| `budget_ceiling` | 累计或预估成本超过 CNY 1.00，或 Judge 调用超过 51 次 |
| `fingerprint_mismatch` | prompt SHA / MANIFEST SHA / fixture SHA / schema / metric / model / temperature / max_tokens 与申请不一致 |
| `activation_drift` | v1.2.1 被设为默认、active=true 或 runtime_active=true |
| `q11_quote_continuity` | Q11 非连续 quote 未被 Service 判 invalid，或 good 连续 quote 未 evaluated |

## 7. 报告要求

- 使用 docs/repair/phase3e/m1c-c4-report-template.md
- 逐条报告 status、F_coverage、F_strict（仅诊断）、C、R、invalid/skipped/failed、insufficient_count/ratio、known issue
- 逐条写 PASS/FAIL/BLOCKED；Q29 只能按 skipped 语义判定
- HG 3 条（Q23/Q35/Q36）与 provisional 7 条分开，不混算均值
- Q17 标 policy_relationship_target_reapproval；Q35/Q36 标 old run only
- 报告写 prompt_version=v1.2.1、rubric_version=v1.2.0、F/C/R SHA、MANIFEST SHA、fixture SHA、target SHA
- 报告写 model/temperature/max_tokens 与 judge_trace production Service replay 方法
- Q23/Q35/Q36 报告 3 次全部结果、median/min/max，不报最好一次
- Q36 的 C 同时报 base 0.5–0.6 与 variant 0.9–1.0，只作诊断，不参与 PASS/FAIL
- 报告 Q11 bad/good 结果：invalid(contract_violation)+quote_not_found / evaluated 1.0
- 结论只能写 implemented/verified/blocked；不得自行写 accepted

## 8. 边界

- 本文件是 v1.2.1 新申请材料，不是 Judge 运行；未调用模型、未创建 Run
- 方法 A：Judge-only 固定 pilot answer/contexts/gold；不调用 WeKnora、不做检索、不生成新答案
- 执行载体：rag_judge_service.judge_trace(session=None, synthetic RagTrace, item, prompt_version=v1.2.1)
- 不复用 v1.2.0 的 10 条批准；本申请必须重新批准
- 不激活 v1.2.1；active 保持 false、runtime_active 保持 false；默认仍 v1.0.0
- 不修改 Prompt、MANIFEST、Schema、Service、API、DB、migration 022、r2、target v1.0.2、Q11 fixture
- 不运行 40 条；10 条通过后才可单独申请 40 条
- 不启动 M2/M3；不把 M1-C/M1-D 标 accepted

## 9. 批准清单

- [ ] 确认这是 v1.2.1 新申请，不复用 v1.2.0 批准
- [ ] 确认 prompt_version=v1.2.1、F 9efdc64d…、C a50520de…、R a5386070…、MANIFEST 8bdd673c…
- [ ] 确认 rubric_version=v1.2.0、Schema v3、Metric v3、target v1.0.2
- [ ] 确认 Q11 bad/good 证据与 Service invalid 契约
- [ ] 确认 Judge-only fixture、Q36 C 双报、HG 重复与 51 次预算
- [ ] 确认停止条件与失败处理
- [ ] 确认不会激活 v1.2.1、不会改默认版本、不会跑 40
- [ ] 批准后才执行 10 条；执行后停下报告

10 条未运行；40 条未批准；v1.2.1 未激活。
