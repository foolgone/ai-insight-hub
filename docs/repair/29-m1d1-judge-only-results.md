# M1-D-1 Judge-only Production Service replay 结果（停止）

> 状态：`stopped`；在 Q11 的 F `invalid(contract_violation)` 处按停止条件停止。
> **已停止，不重跑、不改 Prompt、不跑剩余 cases、不跑 40。**
> 未创建 Run、未写 DB、未调用 WeKnora、未激活 v1.2.0。
> application SHA：`7378d368adf13b7d55e58904af200310fa20f47cf51ccc67967f13e7e437e2ad`
> raw results SHA：`821bd7ccbb5f842c34596f9f3b74f774b8e6318341a1d659f86c7ac473fe6472`
> summary SHA：`47f0979ee87f31795f92b33140fcc0bf89e3dc43f3d48fd15eca87ea5c7e9117`
> fixture SHA：`dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70`
> MANIFEST SHA：`ee1c25be8767bf66069f92e769fd8dd1d986cb950d9e96d3f550af587c35f778`

## 1. 10 条逐条状态

| Case | group | F | F_strict | C | R | 结果 | target |
|---|---|---:|---:|---:|---:|---|---|
| Q01 | provisional | 1.000000 | 1.000000 | 0.900000 | 0.900000 | attempted | PASS |
| Q04 | provisional | 1.000000 | 1.000000 | 0.900000 | 0.900000 | attempted | PASS |
| Q11 | provisional | invalid | invalid | 0.900000 | 0.900000 | attempted | BLOCKED |
| Q17 | provisional | — | — | — | — | not_run | NOT_RUN |
| Q21 | provisional | — | — | — | — | not_run | NOT_RUN |
| Q23 | human_gold | — | — | — | — | not_run | NOT_RUN |
| Q29 | provisional | — | — | — | — | not_run | NOT_RUN |
| Q31 | provisional | — | — | — | — | not_run | NOT_RUN |
| Q35 | human_gold | — | — | — | — | not_run | NOT_RUN |
| Q36 | human_gold | — | — | — | — | not_run | NOT_RUN |

## 2. 停止条件与 Q11 invalid

- stop_triggered：`True`
- stop_reason：Q11 run 1: faithfulness=invalid(contract_violation), faithfulness_strict=invalid(contract_violation)
- 停止条件命中：`invalid(contract_violation)`；按批准规则立即停止。

### Q11 run 1 / faithfulness

- status：`invalid`
- invalid_reason：`contract_violation`
- error_type：`None`
- validation_errors：`[{"claim_id": "cl1", "code": "quote_not_found", "message": "evidence_ref violates v3 contract", "context_id": "C1"}]`

### Q11 run 1 / faithfulness_strict

- status：`invalid`
- invalid_reason：`contract_violation`
- error_type：`None`
- validation_errors：`null`

Q11 的直接原因：F 输出中 `evidence_refs.quote` 不是 C1 的逐字连续子串。
Service 按 v3 契约判整条 F invalid；`faithfulness_strict` 同步 invalid；未进入目标判定。

## 3. 未处理 cases

- attempted：['Q01', 'Q04', 'Q11']
- unprocessed：['Q17', 'Q21', 'Q23', 'Q29', 'Q31', 'Q35', 'Q36']
- HG Q23/Q35/Q36：未运行，因此没有三次结果、median/min/max 或 Q36 C base/variant。

## 4. 分类计数

| 类别 | 值 |
|---|---:|
| attempted cases | 3 |
| unprocessed cases | 7 |
| invalid | 1（Q11 F；strict 同步 invalid） |
| failed | 0 |
| skipped | 0（Q29 未到达） |

## 5. 调用与成本

| 项 | 实际 | 预算/上限 |
|---|---:|---:|
| case-runs | 3 | 16 |
| Judge calls | 9 | 51 |
| input tokens | 28460 | 198,900 |
| output tokens | 2245 | 29,410 |
| cost CNY | 0.089856 | 1.00 |
| preflight tokens | 9 / 8 | — |

## 6. 结论

- M1-D-1 状态：`blocked`；**未 verified**，更未 accepted。
- 10 条闸门未通过；剩余 7 条未运行。
- 不申请 40 条；不激活 v1.2.0；不启动 M2/M3。
- 下一步只能由人工决定：复审 Q11 quote 契约问题、是否允许修复后重新申请。
