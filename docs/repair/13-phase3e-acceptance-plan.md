# Phase 3E 验收方案（v1.2.0 重设计）

> 状态：语义规范已于 2026-11-18 冻结；目标表已于 2026-11-18 冻结；**验收方案仍待审核**。本文只定义验收流程，不修改运行时代码，不运行新的 Judge。
>
> 核心原则：**13 条 Human Gold 用于校准，27 条 provisional 只用于观察，40 条整体只用于规模/回归；三者不能混成一个“通过率”。**
>
> 前置：40 条 final_labels 已冻结（`pilot-40-final-labels.json`，SHA `f139623f…`）；目标表已冻结（`pilot-40-targets-v1.2.0.json`，SHA `34357b34…`）；v1.2.0 运行时未创建/未激活。
>
> **2026-11-19 更新：人工改选方案 B（F_strict + F_coverage）。现有 `F` 目标映射到 `F_coverage`；`F_strict` 只作诊断。本文 §2.4 中“新分母 F=1.0 / Q21 不可达”等描述属于 A 方案的历史评估，B 下不再成立；B 的指标定义与目标映射见 `18-m1b-dual-metric-design-evaluation.md`（`M1-B-003`，`proposed_pending_human`）。**

## 1. 数据角色

| 数据 | 数量 | 角色 | 可写成什么 | 不可写成什么 |
|---|---:|---|---|---|
| Human Gold 基础题 | 13 | 校准/验收锚点 | “HG 校准通过/未通过” | “40 条 Human Gold 通过” |
| Human Gold Claim | 1（Q21#3） | 单 claim 校准 | “Q21#3 为 insufficient” | “整条回答等于该 claim” |
| Provisional 基础题 | 27 | 观察/回归 | “provisional 观察结果” | “人工 Gold 通过” |
| 40 条整体 | 40 | 规模/回归 | “39/40 目标通过 + known issues” | “40 条通过” |

Human Gold 范围以 `docs/repair/phase3e/human-gold.json` 为准：
- 13 条基础题；
- 1 条 claim（Q21#3）；
- 35 条 claims 中仅 1 条已确认，34 条 pending；
- key_facts 41 条（supported 38 / evidence_insufficient 2 / ambiguous 1）。

## 2. 40 条报告统计口径

### 2.1 必须分组的指标

报告至少分三组：

| 组 | 数量 | 统计 |
|---|---:|---|
| Human Gold | 13 | F/C/R 分布、目标命中、known non-pass、F unavailable |
| Provisional | 27 | F/C/R 分布、目标命中、观察性结论 |
| 40 条整体 | 40 | 运行完成度、目标通过数、known issues、未运行数 |

**禁止**：
- 把 HG 与 provisional 合并成一个均值；
- 把 provisional 结果写成人工 Gold；
- 把“目标通过”写成“Human Gold 通过”；
- 把单次模型输出写成绝对真值。

### 2.2 当前口径（v1.1.5）

- 完成：32/40。
- 目标通过：30/32（Q14 为 non-pass；Q32 为停止点）。
- Q14：F unavailable；C=0.7 本次低于 0.8–1.0，历史 0.7/0.7/0.9 方差；只计一次 non-pass。
- Q32：provisional F=0.75；cl1“无法确认”应归 meta；未决。
- **P0 曾未冻结（现已冻结）**：Q17/Q30 的 v1.1.x 目标是在把 `policy_scope`/`policy_relationship` 移出分母后得到的；v1.2.0 将政策范围/关系保留为 factual。目标已由 active target 冻结（Q17 0.7–0.9、Q30 0.4–1.0），但 M1-B-002 改变 F 分母，Q17/Q21 等目标需按 `16-m1b-decision-record.md` §4 重算，见 §2.4。
- 未运行：Q33–Q40 共 8 条。
- 基线：Q33/Q34/Q37/Q38/Q39/Q40 缺 v1.0.0 baseline；Q35/Q36 旧报告有 baseline，可复用。

### 2.3 最终 40 条报告模板

必须包含：

1. **版本**：F/C/R SHA、模型、temperature、max_tokens、日期。
2. **完成度**：完成/未完成、停止点、未运行列表。
3. **分组表**：HG 13、Provisional 27、整体 40。
4. **目标通过数**：明确“目标通过”不是“HG 通过”。
5. **known issues**：
   - Q14 F unavailable / C variance；
   - Q32 meta 误分类（若未修）；
   - Q35/Q36 quote 诊断；
   - Q31 quote 诊断；
   - Q10 typo（若出现）。
6. **重复实验**：高方差案例的 3 次结果。
7. **结论**：只能写“规模/回归结果”，不能写“40 条 Human Gold 验收通过”。

示例口径：
> v1.1.5：32/40 完成，30/32 目标通过；Q14 F unavailable/C variance；Q32 未决；Q33–Q40 未运行。不是 40 条通过，也不是 40 条 Human Gold 验收。

### 2.4 分类变化 → 目标影响（P0 后必须重审）

> **2026-11-19 注：以下为 A 方案（单 F 排除 insufficient）的历史评估；B 方案下 `F_coverage` 恢复旧分母，Q21/Q23 的“不可达/越界”不再成立。保留此表用于解释为什么改选 B。**

| Case | v1.1.x 口径 | v1.2.0 口径 | F 可能变化 | 目标动作 |
|---|---|---|---|---|
| Q17 | policy relationship 被移出分母 → F=1.0 | `policy_relationship` factual；无依据 insufficient | 新公式 1.0；旧口径 0.8 | 已冻结 F 0.7–0.9；**新分母下待重算**（`16-m1b-decision-record.md` §4） |
| Q20 | policy scope/generalization factual/insufficient | `policy_scope` factual | 约 0.8，可能不变 | 已冻结 F 0.6–1.0；重跑 baseline |
| Q30 | policy scope 被移出分母 → F=1.0 | `policy_scope` factual；无依据 insufficient | 可能回到 0.5 | 已冻结 F 0.4–1.0（expected 0.5） |
| Q19 | absence/示例推断部分被排除 | `absence` non_factual；示例仍 insufficient | 可能升高或分母缩小 | 已冻结 F 0.6–1.0；重跑 baseline |
| Q31 | absence/meta 部分被排除 | `absence` non_factual；quote 仍需校验 | 可能升高 | 已冻结 F 0.6–1.0；重跑 baseline |
| Q32 | “无法确认”被标 factual/insufficient | `uncertainty` non_factual | 新公式 1.0；旧口径 0.75 | 已冻结 F 0.9–1.0；3 factual 前提；skipped 算未命中 |
| Q35 | absence 被排除 | `absence` non_factual；quote 仍校验 | 可能升高 | 已冻结 F 0.8–1.0；重跑 baseline |
| Q36 | “能否退款取决于……”被当 meta 排除 | `condition` / `policy_scope` factual；应 supported | 可能不变或变化 | 已冻结 F 0.8–1.0；C base 0.5–0.6 / variant 0.9–1.0 |
| Q21 | Q21#3 insufficient | 不变 | 新公式 1.0；旧口径 0.6 | 已冻结 0.6–0.7；**新分母不可达，待决策** |
| Q14 | F unavailable；C 方差 | 不变 | 不可评估 | 保留 known non-pass；不因 key_facts 改成 PASS |

> **分母变更（M1-B-002，A 方案）**：F = supported/(supported+unsupported)，insufficient 不进分母。上表“新公式”是用 v1.1.5 结果静态重算，不是新运行。A 下 Q21/Q23 与 frozen target 直接冲突，Q17/Q11 边界；B 方案改用 `F_coverage`（旧分母）后该冲突消失，见 `18-m1b-dual-metric-design-evaluation.md`。目标未按 B 冻结前，不得把 40 条结果写成目标通过，也不得修改 frozen target 的 SHA。

> 目标表已冻结（2026-11-18）：`pilot-40-targets-v1.2.0.json`，SHA `34357b34…`；`pilot-40-final-labels.json` 只作分类来源，active target 文件是目标唯一来源；旧 `pilot-40-targets.json` 只读保留。
>
> 重批提案 `pilot-40-targets-v1.2.0-reapproval.json` 保留为历史记录；active target 文件已取代其 `proposed_pending_human` 状态。

### 2.5 分层口径

项目里有两套分类，必须写明：

| 口径 | 来源 | 数量 | 用途 |
|---|---|---|---|
| 原始候选分层 | `candidates.json` | direct 10 / multi 10 / constraint 8 / unanswerable 6 / ambiguous 6 | 覆盖统计、原始抽样 |
| 最终人工分类 | 人工审核口径（Q15→direct、Q16→constraint、Q40→direct） | direct 12 / multi 8 / constraint 9 / unanswerable 6 / ambiguous 5 | HG 校准、最终报告 |

最终人工分类明细（按 40 条口径）：

| 层 | 案例 |
|---|---|
| direct | Q01–Q10、Q15、Q40 |
| multi | Q11–Q14、Q17–Q20 |
| constraint | Q16、Q21–Q28 |
| unanswerable | Q29–Q34 |
| ambiguous | Q35–Q39 |

- `human-gold.json` 只覆盖 13 条 HG；40 条最终分类已冻结在 `pilot-40-final-labels.json`（SHA `f139623f…`）。
- 40 条报告只能使用 `pilot-40-final-labels.json` 作为分类来源；不得再把 candidates 原始分类写成“最终分类”。

## 3. 缺失 baseline 补齐策略

### 3.1 当前缺口

- 未运行 8 条：Q33–Q40。
- 缺 v1.0.0 baseline 6 条：Q33、Q34、Q37、Q38、Q39、Q40。
- Q35、Q36 的 v1.0.0 baseline 在旧 40 条报告中，可复用。
- 因此补齐策略是：**跑 8 条 v1.1.x/v1.2.0 + 补 6 条 baseline + 复用 Q35/Q36 baseline**。

### 3.2 补齐顺序

1. 先冻结 v1.0.0 baseline：对 6 条缺失 case 跑一次 v1.0.0，保存 fingerprint。
2. 再跑目标版本 8 条；Q35/Q36 复用旧 baseline，但必须校验 fingerprint。
3. 补齐后再计算 40 条整体统计；未补齐前不得计算“40 条均值”。
4. 如果 baseline 与新 Run 的模型配置不一致（model/temperature/max_tokens），baseline 不可复用，必须重跑。

### 3.3 不得用“补 8 条 baseline”掩盖

- 8 条是未运行，不等于 8 条 baseline 全缺。
- 6 条 baseline 缺失，2 条 baseline 可复用。
- 报告中必须写清楚“未运行”“baseline 缺失”“baseline 可复用”三者。

## 4. Prompt SHA 与历史 Run 管理

### 4.1 版本锁

- 每次 F/C/R Prompt 变更 → 新版本目录 + 新 SHA。
- 一次实验只能使用一个 F SHA、一个 C SHA、一个 R SHA。
- 报告必须写全 SHA；缺一不可。
- 不得把 v1.1.2 的 10 条与 v1.1.3 的 30 条拼接成 40 条。

### 4.2 历史 Run

- 旧 Run 只读归档，不删除。
- 新版本运行前，旧结果标记 `invalidated_by_sha_change`。
- 任何 known miss/known diagnostic 必须绑定当时 SHA；不能跨版本继承。
- 版本目录保留；默认 `RAG_JUDGE_PROMPT_VERSION=v1.0.0`。

### 4.3 指纹校验

- 复用 baseline/旧结果前，校验：prompt SHA、model、temperature、max_tokens、schema_version、metric_version。
- 任一不一致 → 不得复用。
- 复用失败必须记录原因，不得静默使用。

## 5. 高方差与重复实验

### 5.1 何时重复

以下情况必须重复 3 次：

- Human Gold 单案例目标边界（F/C/R 落在目标上下界 0.1 内）；
- 历史出现 ≥0.2 波动的案例；
- R 指标出现 0.9→0.7 或 C 出现 0.8→0.7；
- 任何 known miss 的定性判断；
- 新版本首次跑 10 条闸门中的 HG 案例。

### 5.2 判定

| 场景 | 要求 |
|---|---|
| 硬门禁（Q23/Q30/Q17 等 HG/关键案例） | 3/3 在目标内；2/3 只能“观察”，不得开 40 |
| 一般 HG 目标 | 3 次中至少 2 次在目标内，且无 HG quote invalid；报告全部 3 次 |
| Provisional 观察 | 3 次全部报告；不因单次高/低直接下结论 |
| 高方差 | 标 `high_variance=true`；记录 min/median/max；不得只报最好一次 |
| 已知非 Judge 问题 | 单独列，不进入 Judge 方差统计 |

### 5.3 禁止

- 只跑一次就宣称通过；
- 跑三次只报最好一次；
- 用“复跑直到通过”替代规则修复；
- 把 known miss 写成 PASS；
- 把单次 0.9 当成稳定 0.9。

## 6. 验收分层

### 6.1 单案例层

每个案例必须满足：

1. Schema/JSON 合法；不是 `invalid(contract_violation)` 或 `failed(execution)`。
2. 不是“全部 claim 结构性无效”；该情况整条 `invalid`。
3. `supported` 必须有有效 evidence；`supported_without_evidence` → 整条 `invalid`。
4. Human Gold：不得出现 supported claim 被 quote 判 invalid（Q35/Q36 的 known diagnostic 需显式允许）。
5. 目标范围内（F/C/R 或 skipped/unavailable）；F 目标必须注明分母口径（M1-B-002）。
6. 高方差案例 3 次结果符合 5.2。

### 6.2 分层验收

**下表是原始候选分层（`candidates.json`，用于覆盖统计）：**

| 层 | 案例（原始 candidates.json category，一层一案例） | 验收 |
|---|---|---|
| direct | Q01–Q10 | 直接回答、单部分 |
| multi | Q11–Q20 | 多部分/条件分支 |
| constraint | Q21–Q28 | 约束/运算/冲突 |
| unanswerable | Q29–Q34 | absence/无法确认/context_unavailable |
| ambiguous | Q35–Q40 | 模糊/冲突披露 |

> 原始分层为 10/10/8/6/6。**HG 校准/最终报告应使用 §2.5 的最终人工分类（12/8/9/6/5）**；Q15→direct、Q16→constraint、Q40→direct。两套口径不得混用。

每层至少报告：
- 完成数；
- 目标通过数；
- known issues；
- high variance 数。

### 6.3 整体验收

- **10 条闸门**：10/10 目标通过；不得有 HG supported quote invalid、`invalid(contract_violation)`、`failed(execution)`。
- **40 条规模/回归**：完成 40/40；目标通过数 + known issues 分开报告；不得写“40 条 Human Gold 通过”。
- **Human Gold 校准**：13 条中 clean pass 数；Q14 F unavailable 单独列；Q21#3 单 claim 单独列。
- **Provisional 观察**：27 条只作观察；不得把 provisional 目标通过写成 HG 通过。
- **系统质量**：`invalid`、`failed(execution)`、`skipped(no_scorable_claims)`、`skipped(no_decidable_claims)`、`skipped(context_unavailable)` 分别计数；insufficient_count/ratio 单列。

## 7. 停止条件

以下任一触发停止，不得继续累积：

1. `invalid(contract_violation)` / 结构化输出失败。
2. 全部 claim 结构性无效（整条 invalid）。
3. Human Gold supported claim 被 quote 判 invalid（除已显式允许的 Q35/Q36 known diagnostic）。
4. `supported_without_evidence` → 整条 `invalid`。
5. 重复 `claim_id` 或冲突证据单边/嵌套。
6. 未解释的指标下降 >0.10（浮点比较用容差；恰好 0.10 不停止）。
7. 同一 provisional 案例第二次 evidence typo / 数字改变。
8. 高方差案例 3 次中 2 次低于硬门禁。
9. `insufficient_ratio` 异常升高但 F 因分母缩小而上升（分母效应，不得当质量提升）。

停止后必须：
- 记录 case、metric、现象、根因、SHA；
- 不把该 case 写成 PASS；
- 决定“规则修复 / 目标注册 / 数据修复 / 停止”，不得默认继续。

## 8. Q14 与 Context 可用性

- Q14：F=`skipped(context_unavailable)`，F 不可评估；不是 PASS，不是 0。
- Q14 C：本次 0.7 低于 0.8–1.0，历史 0.7/0.7/0.9 方差；只计一次 non-pass，不重复记 F+C。报告只能写“Q14 F unavailable / C 0.7 本次方差”，不得写成“F miss + C miss 两个失败”。
- Q33：同样 `context_unavailable`；未运行前不推测。
- C1-only（Q22/Q26/Q27/Q34/Q37/Q40）：报告必须注明单上下文；不得与双上下文混算 F 均值。
- `context_unavailable` 不计入 F 分母，也不进入 F 通过率；单独列“F unavailable”。

## 9. 报告字段（最小集）

每次 Run 必须输出：

```json
{
  "version": {"f_sha": "...", "c_sha": "...", "r_sha": "...", "model": "...", "temperature": 0.0},
  "final_labels": {"file": "pilot-40-final-labels.json", "sha256": "f139623f..."},
  "completion": {"run": 40, "completed": 32, "not_run": ["Q33", "Q34", "Q35", "Q36", "Q37", "Q38", "Q39", "Q40"]},
  "groups": {"human_gold": 13, "provisional": 27},
  "targets": {"passed": 30, "total_run": 32, "known_issues": []},
  "known_issues": [
    {"case_id": "Q14", "kind": "F_unavailable", "detail": "C=0.7 this run; historical 0.7/0.7/0.9; one non-pass only"},
    {"case_id": "Q32", "kind": "uncertainty_misclass", "detail": "cl1 should be uncertainty/non_factual"}
  ],
  "repeats": [{"case_id": "Q16", "metric": "R", "scores": [0.9, 0.9, 1.0]}],
  "baseline": {"reused": 30, "new": 2, "missing": 6, "available_not_run": 2}
}
```

> `reused + new + missing + available_not_run = 40`；Q35/Q36 的 baseline 在旧报告中，属于 `available_not_run`。

## 10. 成本与执行边界

- 10 条闸门：约 ¥0.6（双版本）。
- 40 条整批：约 ¥1.4–1.8（含 baseline 补齐）。
- 高方差重复：约 ¥0.2–0.4。
- v1.2.0 增量直接成本约 ¥2.5–3.1；加 30% 缓冲约 **¥3.3–4.0**。
- 已花 v1.1.x 约 ¥5–6；完整程序总预算按 **¥8–10** 估算，分阶段签字，不一次批准。
- 不激活、不进入 Phase 4、不修改 Human Gold/Prompt 正文/DB；任何激活需人工签字。

## 11. 一句话总结

**13 条 HG 是校准锚点，27 条 provisional 是观察样本，40 条是规模/回归；只有“分层 + 重复 + SHA 锁定 + known issue 分列”的报告，才允许进入人工审核。**
