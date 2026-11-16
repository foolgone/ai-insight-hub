# Phase 3E Prompt v1.1.1 六案例 Dry-run 报告

> **这是 dry-run，不是 Judge 分数。** 未调用 LLM/Judge、未访问网络、未写数据库、未激活 v1.1.1。
>
> 输入：fixture `answer_contexts`（C1–C2）；`retrieval_contexts`（R1–R4）未混入。
> 合成输出：用矩阵 `expected_claims` 构造 v1.1.1 输出（不是 Judge 生成），只验证 Schema/计分/证据规则能否接受矩阵预期，不代表 Prompt 的真实模型表现。
> 生成：2026-11-16；脚本：`docs/repair/phase3e/dry_run_prompt_v1.1.1.py`。

## 结论

**PASS** — 6/6 案例通过；负向/边界测试 12/12 符合预期；未运行 Judge。

| # | Case | F（计算） | F target | C（模拟） | R（模拟） | 证据 | 结果 |
|---|---|---|---|---|---|---|---|
| 1 | Q23 | 0.500 | 0.4–0.5 | 0.10 | 0.75 | 3/3 | PASS |
| 2 | Q35 | 1.000 | 0.8–1.0 | 0.95 | 0.95 | 6/6 | PASS |
| 3 | Q36 | 1.000 | 0.8–1.0 | 0.55, 0.95 | 0.95 | 9/9 | PASS |
| 4 | Q21#3 | 0.600 | 0.6–0.7 | n/a | n/a | 3/3 | PASS |
| 5 | Q11 | 0.600 | 0.6–0.8 | 0.95 | 0.95 | 3/3 | PASS |
| 6 | Q29 | skipped | skipped | 0.95 | 0.95 | 0/0 | PASS |

> C/R 是矩阵区间内的模拟候选值，不是模型输出；F 由 claim `support_status` 计算。

## Q23

- Schema: PASS
- F: `3/6 = 0.500`；target `0.4–0.5` → PASS
- Counts: scorable=6, supported=3, unsupported=1, insufficient=2, non_factual=2, absence=1, document_conflict=0, contradiction=1

| claim_id | type/subtype | support_status | contradictory | evidence | required | variant |
|---|---|---|---|---|---|---|
| cl1 | factual_claim/policy | unsupported | yes | 0 | True | False |
| cl2 | factual_claim/policy | supported | no | 1 | True | False |
| cl3 | factual_claim/policy | supported | no | 1 | True | False |
| cl4 | factual_claim/policy | insufficient_evidence | no | 0 | True | False |
| cl5 | factual_claim/policy | supported | no | 1 | True | False |
| cl6 | factual_claim/policy | insufficient_evidence | no | 0 | True | False |
| cl7 | non_factual/absence | None | no | 0 | False | False |
| cl8 | non_factual/advice | None | no | 0 | False | False |

证据校验：3 条，失败 0 条。

| 检查 | 结果 | 说明 |
|---|---|---|
| cl1 remains factual | PASS |  |
| cl1 contradictory_with=['cl2'] | PASS |  |
| F != 1.0 | PASS | F=0.5 |
| C <= 0.3 (v1.0.0 regression) | PASS | C=0.1 |
| C not in 0.3-0.6 | PASS | C=0.1 |
| wrong_facts non-empty | manual | requires Judge output; not produced in dry-run |

- answer_correctness: base=0.10 (in 0.0–0.2)；negative probe 1.0 rejected
- answer_relevancy: base=0.75 (in 0.7–1.0)；negative probe 0.0 rejected

## Q35

- Schema: PASS
- F: `6/6 = 1.000`；target `0.8–1.0` → PASS
- Counts: scorable=6, supported=6, unsupported=0, insufficient=0, non_factual=2, absence=1, document_conflict=0, contradiction=0

| claim_id | type/subtype | support_status | contradictory | evidence | required | variant |
|---|---|---|---|---|---|---|
| cl1 | factual_claim/policy | supported | no | 1 | True | False |
| cl2 | factual_claim/policy | supported | no | 1 | True | False |
| cl3 | factual_claim/policy | supported | no | 1 | True | False |
| cl4 | factual_claim/policy | supported | no | 1 | True | False |
| cl5 | non_factual/absence | None | no | 0 | True | False |
| cl6 | factual_claim/policy | supported | no | 1 | True | False |
| cl7 | factual_claim/policy | supported | no | 1 | True | False |
| cl8 | non_factual/advice | None | no | 0 | False | False |

证据校验：6 条，失败 0 条。

| 检查 | 结果 | 说明 |
|---|---|---|
| cl5 non_factual/absence | PASS |  |
| cl5 support_status is null | PASS |  |
| C >= 0.7 | PASS | C=0.95 |
| F >= 0.8 | PASS | F=1.0 |
| no region penalty | manual | requires Judge semantics; not machine-checkable |
| no transit-time requirement | manual | requires answer semantics; not machine-checkable |

- answer_correctness: target=0.95 (in 0.7–1.0)；negative probe 0.0 rejected
- answer_relevancy: base=0.95 (in 0.8–1.0)；negative probe 0.0 rejected

## Q36

- Schema: PASS
- F: `8/8 = 1.000`；target `0.8–1.0` → PASS
- Counts: scorable=8, supported=8, unsupported=0, insufficient=0, non_factual=0, absence=0, document_conflict=1, contradiction=0

| claim_id | type/subtype | support_status | contradictory | evidence | required | variant |
|---|---|---|---|---|---|---|
| cl1 | factual_claim/policy | supported | no | 1 | True | False |
| cl2 | factual_claim/policy | supported | no | 1 | True | False |
| cl3 | factual_claim/policy | supported | no | 1 | True | False |
| cl4 | factual_claim/policy | supported | no | 1 | True | False |
| cl5 | factual_claim/policy | supported | no | 1 | True | False |
| cl6 | factual_claim/policy | supported | no | 1 | True | False |
| cl7 | factual_claim/policy | supported | no | 1 | True | False |
| cl8 | factual_claim/conflict | supported | no | 2 | False | True |

证据校验：9 条，失败 0 条。

| 检查 | 结果 | 说明 |
|---|---|---|
| cl8 factual/conflict/supported | PASS |  |
| cl8 not contradictory | PASS |  |
| cl8 two-sided evidence | PASS | evidence=2 |
| base C 0.5-0.6 | PASS | C=0.55 |
| base C not 0.0-0.2 | PASS | C=0.55 |
| variant C 0.9-1.0 | PASS | C=0.95 |
| wrong_facts empty for real quote | manual | requires Judge output |
| no forced canonical rule | manual | requires answer semantics |

- answer_correctness: v1.0.0-no-disclosure=0.55 (in 0.5–0.6), disclosure-variant=0.95 (in 0.9–1.0)；negative probe 0.0 rejected
- answer_relevancy: base=0.95 (in 0.8–1.0)；negative probe 0.0 rejected

## Q21#3

- Schema: PASS
- F: `3/5 = 0.600`；target `0.6–0.7` → PASS
- Counts: scorable=5, supported=3, unsupported=0, insufficient=2, non_factual=1, absence=0, document_conflict=0, contradiction=0

| claim_id | type/subtype | support_status | contradictory | evidence | required | variant |
|---|---|---|---|---|---|---|
| cl1 | factual_claim/policy | supported | no | 1 | True | False |
| cl2 | factual_claim/policy | supported | no | 1 | True | False |
| cl3 | factual_claim/policy | supported | no | 1 | True | False |
| cl4 | factual_claim/policy | insufficient_evidence | no | 0 | True | False |
| cl5 | factual_claim/policy | insufficient_evidence | no | 0 | True | False |
| cl6 | non_factual/advice | None | no | 0 | False | False |

证据校验：3 条，失败 0 条。

| 检查 | 结果 | 说明 |
|---|---|---|
| cl4 insufficient | PASS |  |
| cl4 not unsupported | PASS |  |
| cl5 insufficient | PASS |  |
| F != 1.0 | PASS | F=0.6 |
| single Q21#3 claim score=0.0 | PASS | score=0.0 |

- answer_correctness: n/a（矩阵未给该案例目标）
- answer_relevancy: n/a（矩阵未给该案例目标）

## Q11

- Schema: PASS
- F: `3/5 = 0.600`；target `0.6–0.8` → PASS
- Counts: scorable=5, supported=3, unsupported=0, insufficient=2, non_factual=1, absence=0, document_conflict=0, contradiction=0

| claim_id | type/subtype | support_status | contradictory | evidence | required | variant |
|---|---|---|---|---|---|---|
| cl1 | factual_claim/policy | supported | no | 1 | True | False |
| cl2 | factual_claim/policy | supported | no | 1 | True | False |
| cl3 | factual_claim/policy | supported | no | 1 | True | False |
| cl4 | factual_claim/policy | insufficient_evidence | no | 0 | True | False |
| cl5 | factual_claim/policy | insufficient_evidence | no | 0 | True | False |
| cl6 | non_factual/advice | None | no | 0 | False | False |

证据校验：3 条，失败 0 条。

| 检查 | 结果 | 说明 |
|---|---|---|
| cl4 factual/policy | PASS |  |
| cl4 insufficient | PASS |  |
| cl4 not excluded as non_factual | PASS |  |
| F != 1.0 | PASS | F=0.6 |
| F >= 0.5 | PASS | F=0.6 |

- answer_correctness: base=0.95 (in 0.8–1.0)；negative probe 0.0 rejected
- answer_relevancy: base=0.95 (in 0.9–1.0)；negative probe 0.0 rejected

## Q29

- Schema: PASS
- F: `skipped(no_scorable_claims)`
- Counts: scorable=0, supported=0, unsupported=0, insufficient=0, non_factual=3, absence=1, document_conflict=0, contradiction=0

| claim_id | type/subtype | support_status | contradictory | evidence | required | variant |
|---|---|---|---|---|---|---|
| cl1 | non_factual/absence | None | no | 0 | True | False |
| cl2 | non_factual/meta | None | no | 0 | True | False |
| cl3 | non_factual/advice | None | no | 0 | False | False |

证据校验：0 条，失败 0 条。

| 检查 | 结果 | 说明 |
|---|---|---|
| F skipped | PASS | status=skipped |
| skip reason no_scorable_claims | PASS | reason=no_scorable_claims |
| R >= 0.8 | PASS | R=0.95 |
| wrong refusal absent | manual | requires Judge output |

- answer_correctness: base=0.95 (in 0.9–1.0)；negative probe 0.0 rejected
- answer_relevancy: base=0.95 (in 0.9–1.0)；negative probe 0.0 rejected

## 负向与边界测试

| 测试 | 预期 | 实际 | 结果 |
|---|---|---|---|
| Q35 cl6 evidence points to C2 | FAIL containing 'quote not verbatim in C2' | cl6: quote not verbatim in C2 | PASS |
| Q23 cl1 demoted to non_factual | FAIL containing 'Q23/cl1' | Q23/cl1: claim_type expected 'factual_claim', got 'non_factual' | PASS |
| Q21 cl4 supported without evidence | FAIL containing 'supported without evidence_refs' | cl4: supported without evidence_refs | PASS |
| Q21 all claims supported -> F=1.0 | FAIL containing 'target_range' | supported/scorable=1.0, target_range=0.6-0.7 | PASS |
| Q29 fabricated supported policy claim | FAIL containing 'expected skipped' | expected skipped but faithfulness was evaluated | PASS |
| Q36 cl8 marked contradictory | FAIL containing 'conflict claim must not be contradictory' | cl8: conflict claim must not be contradictory | PASS |
| Q23 cl1 contradictory without pair | FAIL containing 'is_contradictory requires contradiction_with' | cl1: is_contradictory requires contradiction_with | PASS |
| Q36 cl8 single-sided evidence | FAIL containing 'conflict supported needs two-sided evidence' | cl8: conflict supported needs two-sided evidence | PASS |
| Q11 cl4 excluded as non_factual | FAIL containing 'Q11/cl4' | Q11/cl4: claim_type expected 'factual_claim', got 'non_factual' | PASS |
| Q35 cl5 marked supported | FAIL containing 'non_factual must not have support_status' | cl5: non_factual must not have support_status | PASS |
| Q21 alternative split 2/3=0.667 | PASS (range-only) | F=0.667, target=0.6-0.7 PASS | PASS |
| Q36 base answer without cl8 (7/7=1.0) | PASS (range-only) | F=1.000, target=0.8-1.0 PASS | PASS |

## 边界声明

- 未调用 LLM/Judge，未访问网络，未写数据库；
- 未生成真实 Judge 结果；C/R 仅为区间模拟候选；
- v1.1.1 仍为 `design_draft` / `active=false`；
- 未运行 10 条/40 条，未进入 Phase 4；
- 未修改 Human Gold、v1.0.0/v1.1.0 Prompt、Agent/Service/Schema/DB。
