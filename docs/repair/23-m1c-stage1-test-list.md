# M1-C Stage 1：测试清单与预期结果

> 状态：测试设计，只写清单；**不写业务代码、不跑 Judge、不创建/激活 v1.2.0**。
> 依据：`19-m1b-003-freeze-draft.md`（r2）、`22-m1c-stage0-gap-list.md`、`15-phase3e-v1.2.0-schema-service-design.md`。
> 范围：Schema v3 契约、Service 双指标、invalid 持久化、聚合/重试、浮点边界；目标回归为静态 claim 集。

## 0. 测试分层

| 层 | 数量 | 是否跑模型 | 目的 |
|---|---:|---|---|
| Stage 1 核心测试 | **12** | 否 | Schema/Service/聚合/生命周期/阈值 |
| 目标回归 | **5** | 否（静态 claim 集） | Q11/Q17/Q21/Q23/Q32 的 F_coverage/F_strict |
| Judge acceptance | 后续 | 是 | 语义标签正确性；不在本轮 |

**Stage 1 的 12 条测试必须先于业务代码实现写出来；预期结果固定，不允许实现后反过来改预期。**

## 1. 12 条核心测试

| ID | 类型 | 输入 | 预期 F_coverage | 预期 F_strict | 其他断言 |
|---|---|---|---|---|---|
| T01 | 正常支持 | S=5, U=0, I=0, N=0 | **1.0** | **1.0** | status=evaluated；无 invalid |
| T02 | 混合 | S=3, U=1, I=2, N=0 | **0.5** | **0.75** | insufficient_ratio=0.333333；U=1 |
| T03 | 全 insufficient | S=0, U=0, I=3, N=0 | **evaluated 0.0** | **skipped(no_decidable_claims)** | coverage：all_insufficient=true、insufficient_ratio=1.0；Item=evaluated |
| T04 | 全 non_factual | S=0, U=0, I=0, N=3 | **skipped(no_scorable_claims)** | **skipped(no_scorable_claims)** | Item=skipped |
| T05 | 无上下文 | context_unavailable | **skipped(context_unavailable)** | **skipped(context_unavailable)** | F unavailable；不是 0，不是 PASS |
| T06 | 契约违约 | 缺 `claim_subtype` | **invalid(contract_violation)** | **invalid(contract_violation)** | 无分数；invalid_items=1；不得 failed/skipped |
| T07 | 证据降级 | S=2,U=0,I=0，其中 1 条 supported 无 evidence | **0.5** | **1.0** | 该 claim 降级 I；`supported_without_evidence`；仍占分母 |
| T08 | quote 降级 | S=1,U=0,I=0，其中 1 条 quote 非逐字 | **evaluated 0.0 + all_insufficient** | **skipped(no_decidable_claims)** | 该 claim 降级 I；`evidence_not_verbatim`；仍占分母 |
| T09 | invalid 持久化 | A：status=invalid + reason；B：status=failed + invalid_reason | 不进均值 | 不进均值 | 两种都归 invalid_items=1、failed_items=0；不得混入 failed |
| T10 | Item 聚合 | 3 items，coverage+strict 双行，共 6 rows；I1 evaluated/evaluated，I2 evaluated 0/skipped，I3 failed/failed | 2 evaluated items | 1 failed item | total_items=3；evaluated=2；failed=1；invalid=0；skipped=0；unprocessed=0；completed=2；completion_rate=1.0；success_rate=0.666667；rows=6，cases=3 |
| T11 | Retry 快照 | 父 Run + 当前 Prompt/Schema 变化 | 不适用 | 不适用 | 必须拒绝 retry，提示新建 Run；配置不变时子 Run 逐字段复制父快照；不得混 metric_version |
| T12 | 浮点阈值 | old=0.80；new=0.70 / 0.699999 | 不适用 | 不适用 | 0.70 恰好 0.10：**不停止**；0.699999（差 >0.10）：**停止**；比较用 `>0.10 + 1e-9` |

### 1.1 T01–T05 公式说明

```text
T01: coverage = 5/(5+0+0)=1.0; strict = 5/(5+0)=1.0
T02: coverage = 3/(3+1+2)=0.5; strict = 3/(3+1)=0.75
T03: coverage = 0/(0+0+3)=0.0; strict = skipped(no_decidable_claims)
T04: no factual -> both skipped(no_scorable_claims)
T05: no contexts -> both skipped(context_unavailable)
```

### 1.2 T06–T09 契约说明

- T06：缺/非法 subtype、type 不一致都按 `invalid(contract_violation)`；不产出分数，不进入均值。
- T07：`supported_without_evidence` 统一降级 `insufficient_evidence`，保留分母；不允许 drop。
- T08：quote 非逐字/引用 answer 统一降级 `insufficient_evidence`，保留分母；错误码 `evidence_not_verbatim`/`answer_reference`。
- T09：A 方案（推荐）`status=invalid + invalid_reason`；B 方案 `status=failed + invalid_reason` 必须在聚合层重新归类为 invalid，不能算 failed。

### 1.3 T10–T12 生命周期/阈值说明

- T10：Case 数按 `dataset_item_id`，不是 result row；`completed_items=evaluated_items`，不把 skipped/invalid/failed 算 completed。
- T11：retry 复制父快照；Prompt/Schema/模型/检索配置变化必须新建 Run，不允许 retry 换口径。
- T12：恰好 0.10 不停止；只有 `>0.10 + 1e-9` 才停止，避免浮点误判。

## 2. 目标回归（静态 claim 集，不跑 Judge）

| Case | 目标 | F_coverage | F_strict | 预期 |
|---|---|---|---|---|
| Q11 | 0.6–0.9 | **0.833333** | **1.0** | PASS |
| Q17 | 0.7–0.9 | **0.800000**（v1.2.0 预期标签） | **1.0** | PASS |
| Q21 | 0.6–0.7 | **0.600000** | **1.0** | PASS |
| Q23 | 0.4–0.5 | **0.500000** | **0.750000** | PASS |
| Q32 | 0.9–1.0 | **1.000000**（3 factual 点；cl1=uncertainty） | **1.0** | PASS |

说明：
- Q17/Q32 使用 v1.2.0 预期标签，不是 v1.1.5 观测值；不得写成“Judge 已实测”。
- 目标回归只验证公式/分母/目标映射，不验证 Judge 语义；Judge acceptance 是后续独立测试。
- 目标值来自 `pilot-40-targets-v1.2.0.json`（SHA `34357b34…`）与 metadata revision v1.0.2。

## 3. 执行顺序

1. **先写 T06/T08/T09/T12**（契约/负向/浮点），确保失败路径先定义。
2. 再写 T01–T05（公式/状态矩阵）。
3. 再写 T10–T11（聚合/生命周期/retry）。
4. 最后写目标回归 5 条（静态 claim 集）。
5. 12 条核心 + 5 条目标回归全部通过后，才允许进入 Judge acceptance（单案例 Q17/Q30/Q32/Q36）。
6. 单案例通过后，才允许 10 条闸门；10 条通过后，才允许 40 条。
7. 任何阶段不得把单次 Judge 输出写成绝对真值。

## 4. 通过标准

### 4.1 Stage 1 核心

- 12/12 通过；
- T06/T09 不得把 invalid 算 failed，也不得进入均值；
- T07/T08 必须保留 claim 在分母；
- T03 的 coverage 0 必须进入均值，strict 必须 skip；
- T10 的 `total_items=3`、`completed=2`、`success_rate=0.666667`；
- T11 的 retry 不得混版本；
- T12 恰好 0.10 不停止。

### 4.2 目标回归

- 5/5 通过；
- F_coverage/F_strict 数值与上表一致（6 位小数）；
- Q32 不得 skipped；
- F_strict 不作为目标通过率，只记录。

### 4.3 失败处理

- 任一测试失败：先修契约/测试，不得改预期；
- 若预期本身错误：新开 revision，记录原因，不静默改表；
- 不允许“先跑 Judge 看结果再定测试”。

## 5. 不做

- 不跑 Judge；
- 不创建/激活 v1.2.0；
- 不修改 Prompt/Service/Schema/API/DB；
- 不创建 migration 022；
- 不进入 M1-D/M1-E；
- 不把 Stage 1 测试通过当作 Human Gold 验收。
