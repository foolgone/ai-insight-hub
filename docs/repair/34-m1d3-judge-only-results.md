# M1-D-3 v1.2.1 Judge-only Production Service replay 结果（停止）

> 状态：`stopped`；在 Q23 F `invalid(contract_violation)` 处按停止条件停止。
> **已停止，不重跑、不改 Prompt、不跑剩余 cases、不跑 40。**
> 未创建 Run、未写 DB、未调用 WeKnora、未激活 v1.2.1。
> application SHA：`7077477ef6108dcf7996b5ce17b2c492752cbbc85644856d91abdb3b5f45da28`
> raw results SHA：`96ff0d9b03add2365f5a74219402deb59a3015f7c6adc1f174cb039cdb34c526`
> summary SHA：`5e4d38c37e94b55f5d8c3d126716ebc4c3f320dcf12cfbf20ef5ed256e71fe62`
> fixture SHA：`dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70`
> MANIFEST SHA：`8bdd673cd44ed772dfc1630280e571d4cdd8ed786066eb72eb553a9be8b0b278`

## 1. 10 条逐条状态

| Case | group | F | F_strict | C | R | 结果 | target |
|---|---|---:|---:|---:|---:|---|---|
| Q01 | provisional | 1.000000 | 1.000000 | 0.900000 | 0.900000 | attempted | PASS |
| Q04 | provisional | 1.000000 | 1.000000 | 0.900000 | 1.000000 | attempted | PASS |
| Q11 | provisional | 0.800000 | 1.000000 | 0.900000 | 0.900000 | attempted | PASS |
| Q17 | provisional | 0.800000 | 1.000000 | 0.900000 | 0.900000 | attempted | PASS |
| Q21 | provisional | 1.000000 | 1.000000 | 0.900000 | 0.900000 | attempted | FAIL |
| Q23 | human_gold | invalid(contract_violation) | invalid(contract_violation) | 0.000000 | 0.900000 | attempted | BLOCKED |
| Q29 | provisional | — | — | — | — | not_run | NOT_RUN |
| Q31 | provisional | — | — | — | — | not_run | NOT_RUN |
| Q35 | human_gold | — | — | — | — | not_run | NOT_RUN |
| Q36 | human_gold | — | — | — | — | not_run | NOT_RUN |

## 2. 停止原因与 invalid

- stop_triggered：`True`
- stop_reason：Q23 run 1: faithfulness=invalid(contract_violation), faithfulness_strict=invalid(contract_violation)
- 停止条件命中：`invalid(contract_violation)`；按批准规则立即停止。

### Q23 run 1 / faithfulness

- status：`invalid`
- invalid_reason：`contract_violation`
- error_type：`StructuredOutputError`
- error_message：StructuredOutputError: structured output is still invalid after repair
- errors：`["StructuredOutputError: structured output is still invalid after repair"]`

### Q23 run 1 / faithfulness_strict

- status：`invalid`
- invalid_reason：`contract_violation`
- error_type：`StructuredOutputError`
- error_message：—
- errors：`null`

Q23 原始 F 输出的关键契约问题（摘要）：

- 出现 `claim_type=factual_claim` + `claim_subtype=absence`；
- 出现 `support_status=supported` 但 `evidence_refs=[]`；
- 结构化输出修复后仍不合法 → `StructuredOutputError` → `invalid(contract_violation)`。

## 3. HG 三次结果

| Case | runs | F | F_strict | C | R | 说明 |
|---|---:|---:|---:|---:|---:|---|
| Q23 | 1 | invalid | invalid | 0.000000 | 0.900000 | 首轮 invalid，未继续 3 次 |
| Q35 | 0 | — | — | — | — | unprocessed |
| Q36 | 0 | — | — | — | — | unprocessed |

Q23 只有 1 次结果，不能计算 median/min/max；Q35/Q36 未运行。

## 4. Q36 C base/variant

Q36 未运行，因此没有 C actual / base / variant 结果；未做 post-hoc 选择。

## 5. 分类计数

| 类别 | 值 |
|---|---:|
| attempted cases | 6 |
| unprocessed cases | 4 |
| invalid | Q23 F；strict 同步 invalid |
| failed | 0 |
| skipped | 0（Q29 未到达） |

## 6. 调用与成本

| 项 | 实际 | 预算/上限 |
|---|---:|---:|
| case-runs | 6 | 16 |
| Judge calls | 18 | 51 |
| input tokens | 58335 | 198,900 |
| output tokens | 5039 | 29,410 |
| cost CNY | 0.188378 | 1.00 |
| preflight tokens | 9 / 6 | — |

## 7. 结论

- M1-D-3 状态：`blocked`；未 verified，更未 accepted。
- Q11 已通过（F=0.8，目标 0.6–0.9）；Q17 F=0.8（目标 0.7–0.9）通过。
- Q21 F=1.0，超出目标 0.6–0.7；如继续执行会 target FAIL，但本轮因 Q23 invalid 先停止。
- Q23 F invalid，10 条闸门未通过；Q29/Q31/Q35/Q36 未运行。
- 不申请 40 条；不激活 v1.2.1；不启动 M2/M3。

## 8. 边界

- 通过 `rag_judge_service.judge_trace(session=None, ...)` 执行；
- 未创建 `RagEvaluationRun`、未写 DB、未调用 WeKnora；
- 未激活 v1.2.1、未改默认版本/Prompt；
- 未跑 40、未启动 M2/M3；
- verified：`False`；accepted 仍需人工决定。
