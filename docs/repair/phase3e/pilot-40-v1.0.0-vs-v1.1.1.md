# 40 条规模运行：v1.0.0 vs v1.1.1（10/40，Q10 停止）

> **40 条规模/回归运行，不是 40 条 Human Gold 验收。** Human Gold 仅 13 条 + Q21#3 claim；其余 27 条 provisional。
> v1.1.1 使用 F SHA 3519fd3b…、C SHA 2ab6eac…；Faithfulness 只用 answer_contexts（C1–C2）。

## 执行状态

- 状态：**stopped**
- 停止原因：
  - `Q10/faithfulness: dropped 1.000->0.500 >0.10`
- 已完成案例：**10/40**
- Human Gold 已完成：**1/13**
- Provisional 已完成：**9/27**
- 未运行案例：Q11, Q12, Q13, Q14, Q15, Q16, Q17, Q18, Q19, Q20, Q21, Q22, Q23, Q24, Q25, Q26, Q27, Q28, Q29, Q30, Q31, Q32, Q33, Q34, Q35, Q36, Q37, Q38, Q39, Q40
- 模型：`qwen-max`；temperature=0.0；max_tokens=8192
- 复用案例：Q01, Q04

## Q36 披露 variant 前置 smoke

- `docs/repair/phase3e/q36-disclosure-variant-smoke.json`：C=0.9，missing=[]，wrong_facts=[]，reason 为“正确披露了文档冲突”；目标 0.9–1.0，**通过**。
- 40 条本身只含 Q36 v1.0.0 base answer（未披露 variant）。

## 逐案例（10/40）

| Case | 组 | v1.0.0 F/C/R | v1.1.1 F/C/R | 目标 | 结果 |
|---|---|---|---|---|---|
| Q01 | PROV | 1.000/0.900/0.800 | 1.000/0.900/0.900 | `{"F": [0.9, 1.0], "C": [0.9, 1.0], "R": [0.8, 1.0]}` | PASS |
| Q02 | PROV | 1.000/1.000/1.000 | 1.000/0.900/0.900 | `no regression >0.10` | PASS |
| Q03 | PROV | 1.000/1.000/1.000 | 1.000/0.900/0.900 | `no regression >0.10` | PASS |
| Q04 | PROV | 1.000/0.800/1.000 | 1.000/0.900/0.900 | `{"F": [1.0, 1.0], "C": [0.8, 1.0], "R": [0.9, 1.0]}` | PASS |
| Q05 | HG | 1.000/1.000/1.000 | 1.000/0.900/0.900 | `no regression >0.10` | PASS |
| Q06 | PROV | 1.000/1.000/1.000 | 1.000/0.900/0.900 | `no regression >0.10` | PASS |
| Q07 | PROV | 1.000/1.000/1.000 | 1.000/0.900/0.900 | `no regression >0.10` | PASS |
| Q08 | PROV | 1.000/1.000/1.000 | 1.000/0.900/0.900 | `no regression >0.10` | PASS |
| Q09 | PROV | 1.000/0.900/1.000 | 1.000/0.900/0.900 | `no regression >0.10` | PASS |
| Q10 | PROV | 1.000/0.900/1.000 | 0.500/0.900/0.900 | `no regression >0.10` | STOP |

## Q10 停止明细

- v1.0.0：F=1.0、C=0.9、R=1.0；v1.1.1：F=0.5、C=0.9、R=0.9。
- F 下降 1.0→0.5（-0.5），Q10 为 provisional，无显式目标，按“未解释下降 >0.10”停止。
- F counts：scorable=2，supported=1，insufficient=1。
- 原因：cl1 的 quote 为 `优惠券自领取之日起 30 夅内有效`，把“天”写成“夅”，不是 C1 逐字子串；Service 记 `quote_not_found` 并降级。
- validation_errors：`[{"claim_id": "cl1", "code": "quote_not_found", "message": "evidence quote is not a verbatim substring", "context_id": "C1"}, {"claim_id": "cl1", "code": "evidence_validation_failed", "message": "supported claim has invalid evidence; downgraded"}]`

## 分组汇总

| 组 | 已完成 | 均值说明 |
|---|---|---|
| human_gold | 1/13 | 不混算；样本未跑完，暂不给出验收均值 |
| provisional | 9/27 | 不混算；样本未跑完，暂不给出验收均值 |

## Token / 成本（已完成 10 条 × 2 臂）

| Arm | input | output | 估算成本（CNY） |
|---|---|---|---|
| v1.0.0 | 23678 | 2532 | 0.0811 |
| v1.1.1 | 76438 | 3645 | 0.2184 |
| **合计** |  |  | **0.2995** |

> 仅 10/40；Q01/Q04 为复用结果。

## 边界

- 40 条未完成；未跑 Q11 之后案例；未跑 40 条整体验收。
- v1.1.1 仍 `design_draft` / `active=false`；脚本退出前恢复 v1.0.0。
- 未激活、未改 Human Gold/Prompt 正文/DB；不进入 Phase 4。

