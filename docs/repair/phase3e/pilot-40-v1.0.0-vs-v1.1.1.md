# 40 条规模运行：v1.0.0 vs v1.1.1（27/40，Q22 停止）

> **40 条规模/回归运行，不是 40 条 Human Gold 验收。** Human Gold 13 条 + Q21#3 claim；其余 27 条 provisional。
> v1.1.1 使用 F SHA 3519fd3b…、C SHA 2ab6eac…；Faithfulness 只用 answer_contexts（C1–C2）。

## 执行状态

- 状态：**stopped**
- 停止原因：
  - `Q22/faithfulness: dropped 1.000->0.400 >0.10`
  - `Q22: Human Gold supported claim downgraded by evidence`
- 已完成案例：**27/40**
- Human Gold 已完成：**10/13**
- Provisional 已完成：**17/27**
- 未运行案例：Q24, Q25, Q26, Q27, Q28, Q30, Q32, Q33, Q34, Q37, Q38, Q39, Q40
- 模型：`qwen-max`；temperature=0.0；max_tokens=8192
- 复用案例：Q01, Q04, Q11, Q17, Q21, Q23, Q29, Q31, Q35, Q36

## Q36 披露 variant 前置 smoke

- `q36-disclosure-variant-smoke.json`：C=0.9，missing=[]，wrong_facts=[]，目标 0.9–1.0，**通过**。
- 40 条只含 Q36 base answer（未披露 variant）；base C=0.5 已通过 10 条验证。

## 逐案例（27/40）

| Case | 组 | v1.0.0 F/C/R | v1.1.1 F/C/R | 目标/规则 | 结果 |
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
| Q10 | PROV | 1.000/0.900/1.000 | 0.500/0.900/0.900 | `no regression >0.10` | PASS(typo) |
| Q11 | PROV | 0.750/0.900/1.000 | 0.667/0.900/0.900 | `{"F": [0.6, 0.9], "C": [0.8, 1.0], "R": [0.9, 1.0]}` | PASS |
| Q17 | PROV | 1.000/0.900/1.000 | 1.000/0.900/0.900 | `{"F": [0.9, 1.0], "C": [0.8, 1.0], "R": [0.8, 1.0]}` | PASS |
| Q21 | PROV | 0.800/0.900/1.000 | 0.600/0.900/0.900 | `{"F": [0.6, 0.7]}` | PASS |
| Q23 | HG | 1.000/0.800/0.900 | 0.429/0.000/0.900 | `{"F": [0.4, 0.5], "C": [0.0, 0.2], "R": [0.7, 1.0]}` | PASS |
| Q29 | PROV | 1.000/1.000/0.800 | skipped(no_scorable_claims)/0.900/1.000 | `{"F": "skipped", "C": [0.9, 1.0], "R": [0.9, 1.0]}` | PASS |
| Q31 | PROV | 1.000/0.900/0.800 | 1.000/0.900/0.900 | `{"F": [0.6, 1.0], "C": [0.8, 1.0], "R": [0.8, 1.0]}` | PASS |
| Q35 | HG | 0.889/0.800/0.800 | 0.833/0.900/0.900 | `{"F": [0.8, 1.0], "C": [0.7, 1.0], "R": [0.8, 1.0]}` | PASS |
| Q36 | HG | 1.000/0.900/0.900 | 0.857/0.500/0.900 | `{"F": [0.8, 1.0], "C": [0.5, 0.6], "R": [0.8, 1.0]}` | PASS |
| Q12 | PROV | 0.400/1.000/1.000 | 0.667/0.900/1.000 | `no regression >0.10` | PASS |
| Q13 | HG | 1.000/0.900/0.900 | 1.000/0.900/0.900 | `no regression >0.10` | PASS |
| Q14 | HG | skipped(context_unavailable)/0.800/1.000 | skipped(context_unavailable)/0.900/0.900 | `{"F": "unavailable", "C": [0.8, 1.0], "R": [0.8, 1.0]}` | PASS(C/R; F n/a) |
| Q15 | HG | 1.000/1.000/1.000 | 0.667/0.900/0.900 | `{"F": [0.6, 1.0], "C": [0.8, 1.0], "R": [0.8, 1.0]}` | PASS(purpose) |
| Q16 | HG | 1.000/1.000/1.000 | 1.000/0.900/0.900 | `no regression >0.10` | PASS |
| Q18 | PROV | 1.000/0.800/1.000 | 1.000/0.900/0.900 | `no regression >0.10` | PASS |
| Q19 | HG | 0.600/0.900/1.000 | 0.833/0.900/0.900 | `no regression >0.10` | PASS |
| Q20 | PROV | 1.000/0.900/1.000 | 0.800/0.900/1.000 | `{"F": [0.6, 1.0], "C": [0.8, 1.0], "R": [0.8, 1.0]}` | PASS |
| Q22 | HG | 1.000/1.000/1.000 | 0.400/0.900/1.000 | `no regression >0.10` | STOP |

## 特别诊断

- **Q10**：provisional `evidence_typo`，quote “30 夅内” vs “30 天内”；F=0.5、C=0.9、R=0.9；按裁定继续，不按事实回归。
- **Q14**：F=`skipped(context_unavailable)`，**F 未评估，不算 PASS**；C/R=0.9/0.9。40 条 F 有效覆盖因此为 39/40。
- **Q15**：Human Gold F=0.667，cl3“电话联系目的”为真实回答中的目的句，上下文未支持，insufficient；Q15 目标已注册 F 0.6–1.0，PASS。v1.0.0 的 1.0 是粗粒度合并，不是 v1.1.1 退化。
- **Q20**：provisional F=0.8，cl5“该政策适用于所有符合积分累积条件的订单”为 generalization_insufficient；Q20 目标已注册 F 0.6–1.0，PASS；wrong_facts=[]。
- **Q22**：Human Gold F 1.0→0.4；cl1/cl4 supported 被 quote_not_found 降级；按 HG evidence downgrade + 未解释下降 >0.10 停止。

## Q22 停止明细

- v1.0.0：F=1.0、C=1.0、R=1.0；v1.1.1：F=0.4、C=0.9、R=1.0。
- F counts：scorable=5，supported=2，insufficient=3。
- cl1 与 cl4 原为 supported，但 quote 不是 C1 逐字子串；Service 记 `quote_not_found` 并降级为 insufficient。
- 这是 Human Gold supported claim 被 evidence 降级，且 F 1.0→0.4，按停止条件停止。
- C details：`{"missing_points": [], "wrong_facts": [], "reason": "回答关键事实、条件与金标一致，且补充了相关运费规则的详细说明。"}`

## v1.1.2 Q22 修复（单案例）

- 新建 v1.1.2 F Prompt：quote 单行/保留换行、Q22 5 条 few-shot、absence 不进分母。
- 新 F SHA：`3db91171edb644f8d2764b588bd1fafdadc044a44c2e7989f9fe1ae04ee2f80c`。
- Q22 F 单案例：**F=1.0，4 scorable / 4 supported / 1 non_factual，6/6 evidence，validation_errors=[]**；cl5 absence。
- 40 条 v1.1.2 **未重跑**；上述 27/40 为 v1.1.1 旧 SHA。若以 v1.1.2 为最终版本，必须整批重跑 40 条，不能混合 SHA 称为 40 条通过。

## 分组汇总

| 组 | 已完成 | 说明 |
|---|---|---|
| human_gold | 10/13 | 不混算；样本未跑完，暂不给出验收均值 |
| provisional | 17/27 | 不混算；样本未跑完，暂不给出验收均值 |

## Token / 成本（27/40）

| Arm | input | output | 估算成本（CNY） |
|---|---|---|---|
| v1.0.0 | 71587 | 10835 | 0.2758 |
| v1.1.1 | 210936 | 16708 | 0.6666 |
| **合计** |  |  | **0.9424** |

> 仅 26/40；Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36 为复用结果。

## 边界

- 40 条未完成；未跑 Q24, Q25, Q26, Q27, Q28, Q30, Q32, Q33, Q34, Q37, Q38, Q39, Q40。
- v1.1.1 仍 `design_draft` / `active=false`；脚本退出前恢复 v1.0.0。
- 未激活、未改 Human Gold/Prompt 正文/DB；不进入 Phase 4。

