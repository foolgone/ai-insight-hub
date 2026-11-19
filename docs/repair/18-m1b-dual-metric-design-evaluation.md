# M1-B 双指标设计评估：F_strict + F_coverage

> Decision ID（提案）：`M1-B-003`
> 状态：`superseded_by_freeze_draft`；**未实现、未跑 Judge**。
> 日期：2026-11-19
> 背景：2026-11-19 人工选择方案 B；`M1-B-002`（单 F = supported/(supported+unsupported)）保留为历史决策，不再作为最终方案。
> **2026-11-19 更新：D1–D4 原则同意（D1/D2 附约束）；冻结草案见 `19-m1b-003-freeze-draft.md`。本文件保留为设计评估，不再作为冻结文本。**
> 范围：指标定义、状态边界、目标映射、Schema/Service 影响、验收测试；不修改 Prompt/Service/Schema/API/DB，不创建/激活 v1.2.0。
> 冲突处理：本文件是 B 的提案；在 B 冻结前，`13/14/15/16` 中 A 的规则只作为历史记录，不作为实现依据。

## 1. 结论

**建议采用 B，但把两个指标的角色定死：**

| 指标 | 角色 | 公式 | 是否承载目标 |
|---|---|---|---|
| `F_coverage` | 主指标，回答“回答里的事实断言有多少被上下文支持” | `supported / (supported + unsupported + insufficient)` | **是**；现有 `F` 目标全部映射到它 |
| `F_strict` | 诊断指标，回答“在能判定的断言里，有多少被支持” | `supported / (supported + unsupported)` | 否；v1.2.0 只观察，不设硬目标 |

关键理由：

1. **目标兼容**：用 v1.1.5 的 32 条结果静态重算，`F_coverage` 与旧 F 在 30/30 有分数的案例上（6 位小数内）一致；Q14/Q29 均为 skip；现有 Q11/Q17/Q21/Q23/Q32 目标不需要改数值。
2. **语义分离**：`F_strict` 高、`F_coverage` 低，说明“没有明显矛盾，但证据覆盖不足”；`F_strict` 低、`F_coverage` 高，说明“少量可判定断言里有矛盾”。两者一起看，才能区分“幻觉”和“证据不足”。
3. **全 insufficient 可解释**：`F_strict` 没有可判定 Claim → skip；`F_coverage` 有 factual 分母 → 0，并打 `all_insufficient=true`。这不是“发现幻觉”，是“证据不可判定”。
4. **不增加 Judge 调用**：两个分数从同一组 claims 派生，不需要跑两次模型。

**当前判断：B 可行，且比 A 更适合现有目标体系；但必须先冻结 M1-B-003，再写代码。**

## 2. 定义

### 2.1 Claim 分桶

对每条 Faithfulness 输出，按 `claim_type` / `support_status` 分桶：

| 桶 | 条件 |
|---|---|
| `S` | `factual_claim` + `support_status=supported` |
| `U` | `factual_claim` + `support_status=unsupported` |
| `I` | `factual_claim` + `support_status=insufficient_evidence` |
| `N` | `non_factual`（absence/doc_scope/doc_relationship/uncertainty/meta/advice/greeting） |

`invalid(contract_violation)` 不进入任何桶；整条 metric 无分数。

### 2.2 公式

```text
F_strict   = S / (S + U)          if S + U > 0
F_coverage = S / (S + U + I)      if S + U + I > 0
```

性质：

- 当 `I = 0` 时，`F_strict = F_coverage`；
- 当 `I > 0` 时，`F_strict >= F_coverage`；
- 两者都不是“正确答案率”，只衡量 Faithfulness（回答是否被上下文支持）；
- `N` 不进入任何分母。
- **`F_strict=1.0` 不代表回答被支持**：它只表示“在可判定 Claim 中没有矛盾”。必须同时看 `F_coverage` 和 `insufficient_ratio`。

### 2.3 状态矩阵

| S | U | I | N | F_strict | F_coverage | 说明 |
|---|---|---|---|---|---|---|
| >0 | ≥0 | ≥0 | ≥0 | `S/(S+U)` | `S/(S+U+I)` | 正常 evaluated |
| 0 | >0 | 0 | ≥0 | `0.0` | `0.0` | 全部可判定且均不支持 |
| 0 | >0 | >0 | ≥0 | `0.0` | `0.0` | 有矛盾，也有 insufficient |
| 0 | 0 | >0 | ≥0 | `skipped(no_decidable_claims)` | **`evaluated 0.0` + `all_insufficient=true`** | 证据不可判定，不是幻觉 |
| 0 | 0 | 0 | >0 | `skipped(no_scorable_claims)` | `skipped(no_scorable_claims)` | 没有 factual Claim |
| 0 | 0 | 0 | 0 | `skipped(no_scorable_claims)` | `skipped(no_scorable_claims)` | 空 claim 集；不当作 invalid，除非 Schema 要求最少 1 条 |
| — | — | — | — | `skipped(context_unavailable)` | `skipped(context_unavailable)` | 无上下文；优先于其他状态 |
| — | — | — | — | `invalid(contract_violation)` | `invalid(contract_violation)` | 证据/结构违约；优先于计分 |
| — | — | — | — | `failed(execution)` | `failed(execution)` | Judge 调用失败且重试耗尽 |

优先级：`context_unavailable` / `invalid` / `failed(execution)` 先于分桶计分；不要把 invalid 降级成 insufficient 再算 0。

### 2.4 全 insufficient 的语义（重点审核）

**状态：`proposed_pending_human`；以下是设计建议，不是已批准的语义变更。**

人工建议：`F_strict` skip，`F_coverage` 0 + `all_insufficient=true`。设计评估如下。

| 方案 | F_strict | F_coverage | 优点 | 缺点 |
|---|---|---|---|---|
| **建议方案** | skip | `evaluated 0.0` + flag | 保留覆盖率信号；可区分“没有 factual”与“全部证据不足”；目标 0 分是真实 miss | 0 容易被误读为“幻觉”，必须靠 flag/报告文案防误读 |
| 两者都 skip | skip | skip | 不会误读 | 丢失覆盖率信号；无法统计“全部证据不足”的比例 |
| 两者都 0 | 0.0 | 0.0 | 数字简单 | `F_strict=0` 错误：没有可判定 Claim，不等于“全部矛盾” |

**建议采纳人工建议，但冻结时写死以下字段：**

```json
{
  "status": "evaluated",
  "score": 0.0,
  "details": {
    "supported_count": 0,
    "unsupported_count": 0,
    "insufficient_count": 3,
    "insufficient_ratio": 1.0,
    "all_insufficient": true,
    "report_label": "evidence_undecidable"
  }
}
```

报告文案必须写：

> 本题全部 factual Claim 为 `insufficient_evidence`，`F_coverage=0.0` 表示“没有一条事实断言被上下文支持”，属于证据不可判定；不是“发现了 3 条幻觉”。

不得写成“F=0，说明模型在编造”。

**同样是 `F_coverage=0`，必须区分两种情况：**

| 情况 | 字段 | 报告文案 |
|---|---|---|
| 全部 insufficient | `all_insufficient=true`，`unsupported_count=0` | “证据不可判定，未发现可支持的事实断言” |
| 有 unsupported | `unsupported_count>0`，`all_insufficient=false` | “存在与上下文矛盾的断言” |

## 3. 目标影响（B 的核心优势）

### 3.1 静态重算：F_coverage 与旧 F 一致

用 v1.1.5 的 32 条结果（不是新 Judge 运行）逐条重算：

| 项 | 结果 |
|---|---|
| `F_coverage` == 旧 F | **30/30 有分数的案例在 6 位小数内一致**；Q14/Q29 均为 skip，不产生分数 |
| `F_strict` == 旧 F | 19/32 数值一致；11 条含 insufficient 的案例不同；Q14/Q29 均为 skip |
| `F_strict` < 1.0 的案例 | 仅 Q23（0.75，1 条 unsupported） |
| `F_strict` = 1.0 的案例 | 有分数的 30 条中 29 条为 1.0（Q23 除外） |

含 insufficient 的案例：

| Case | S | U | I | F_strict | F_coverage（=旧 F） | frozen target | 目标状态 |
|---|---|---|---|---|---|---|---|
| Q11 | 5 | 0 | 1 | 1.000 | 0.833 | 0.6–0.9 | 通过 |
| Q12 | 2 | 0 | 1 | 1.000 | 0.667 | 无 | — |
| Q15 | 3 | 0 | 1 | 1.000 | 0.750 | 0.6–1.0 | 通过 |
| Q19 | 5 | 0 | 2 | 1.000 | 0.714 | 0.6–1.0 | 通过 |
| Q20 | 4 | 0 | 1 | 1.000 | 0.800 | 0.6–1.0 | 通过 |
| Q21 | 3 | 0 | 2 | 1.000 | 0.600 | 0.6–0.7 | 通过 |
| Q23 | 3 | 1 | 2 | 0.750 | 0.500 | 0.4–0.5 | 通过 |
| Q24 | 2 | 0 | 1 | 1.000 | 0.667 | 无 | — |
| Q28 | 6 | 0 | 1 | 1.000 | 0.857 | 0.8–1.0 | 通过 |
| Q31 | 5 | 0 | 1 | 1.000 | 0.833 | 0.6–1.0 | 通过 |
| Q32 | 3 | 0 | 1 | 1.000 | 0.750 | 0.9–1.0 | v1.1.5 标签下 miss；v1.2.0 预期通过 |
| Q17 | 4 | 0 | 0（v1.1.5 cl5=meta） | 1.000 | 1.000 | 0.7–0.9 | v1.1.5 越界；v1.2.0 预期 0.8 通过 |

### 3.2 v1.2.0 预期下的关键案例

| Case | v1.2.0 预期标签 | F_strict | F_coverage | target | 判断 |
|---|---|---|---|---|---|
| Q17 | cl5 `policy_relationship` factual + insufficient | 1.000（4/4） | 0.800（4/5） | 0.7–0.9 | 通过 |
| Q21 | 2 条合法 insufficient | 1.000（3/3） | 0.600（3/5） | 0.6–0.7 | 通过 |
| Q23 | 1 unsupported + 2 insufficient | 0.750（3/4） | 0.500（3/6） | 0.4–0.5 | 通过 |
| Q11 | 1 条 insufficient | 1.000（5/5） | 0.833（5/6） | 0.6–0.9 | 通过 |
| Q32 | cl1 `uncertainty` non_factual；3 factual 全 supported | 1.000（3/3） | 1.000（3/3） | 0.9–1.0 | 通过 |

结论：

- **现有目标全部映射到 `F_coverage`，不需要改数值**；
- 目标表只需 metadata 说明“`F` 指 `F_coverage`”，可选增加 `f_strict_role=diagnostic`；
- A 方案下 Q21/Q23 的冲突在 B 下消失；
- 如果 v1.2.0 的标签与预期不同，F_coverage 仍按同一分母计算，变化归因于标签，不归因于分母。

## 4. 命名与持久化（待拍板）

### 4.1 D1：指标 key

| 方案 | key | 优点 | 缺点 |
|---|---|---|---|
| **1（推荐）** | `faithfulness` = F_coverage；新增 `faithfulness_strict` | 目标/API/报告向后兼容；避免与 aggregate 的 `coverage` 字段重名 | “faithfulness”名字没体现 coverage，需要 UI 标注 |
| 2 | `faithfulness_coverage` + `faithfulness_strict` | 名字最明确 | 与 `aggregate.metrics[].coverage`（评测覆盖率）重名，UI/报告容易混淆；目标表要改映射 |
| 3 | 单 metric + `details.strict/coverage` | 存储最省 | 聚合、目标、M2 都要特殊分支；不推荐 |

**推荐 1**：保留 `faithfulness` 作为 target-bearing F_coverage，新增 `faithfulness_strict` 作为诊断。这样不需要改 frozen target 的 `F` 语义，也不会和 `coverage` 字段混淆。

### 4.2 D2：持久化

| 方案 | 做法 | 优点 | 缺点 |
|---|---|---|---|
| **1（推荐）** | 两条 result row：`faithfulness`（完整 claims/evidence/raw_output）+ `faithfulness_strict`（计数 + `derived_from_result_id`） | 聚合/目标/API 清晰；strict 不重复 20k raw_output | 需要约定 strict 行不承载 evidence 详情 |
| 2 | 两条 row 都存完整 details | 实现简单 | 存储/传输翻倍 |
| 3 | 一条 row 两个 score | 存储省 | 破坏“一行一 metric”契约，聚合复杂 |

**推荐 1**：strict 行只存 `S/U/I` 计数和来源 id；Evidence 追踪统一读 `faithfulness` 行。

### 4.3 D3：全 insufficient 的 F_coverage 状态

按 §2.4 建议：`evaluated 0.0` + `all_insufficient=true`；`F_strict` skip。**这是待审核建议，不是已批准语义。**

### 4.4 D4：F_strict 是否设目标

推荐 v1.2.0 **只观察，不设硬目标**：

- 有分数的 30 条中 29 条 F_strict=1.0（Q23=0.75），区分度低；现在设目标容易变成“永远通过”；
- 先用 `unsupported_count` / `unsupported_ratio` 做诊断；
- 等 v1.2.0 数据出来，再决定是否给 HG 设“F_strict 不得低于 X”的 guard。

## 5. 聚合与 API 影响

### 5.1 Run aggregate

`aggregate.metrics` 增加 `faithfulness_strict`；每个 metric 继续有：

```json
{
  "metric_version": "v3",
  "mean": 0.95,
  "evaluated": 32,
  "skipped": 0,
  "invalid": 0,
  "failed": 0,
  "coverage": 0.8,
  "skip_reasons": {},
  "insufficient_count": 8,
  "insufficient_ratio": 0.02,
  "all_insufficient_count": 0
}
```

注意：`coverage` 字段是“评测覆盖率”（evaluated / total_items），**不是 F_coverage**；这就是 D1 推荐保留 `faithfulness` 命名的原因。

### 5.2 派生关系与 API 选择

`faithfulness_strict` 是 `faithfulness` 的**派生指标**，不是独立的 Judge 指标：

- 用户只选择 `faithfulness`；Service 自动派生 `faithfulness_strict`；
- 不允许只选 `faithfulness_strict` 而不选 `faithfulness`；
- `expected_metrics(run)` 在 query 模式下同时包含两者；
- 重试选择集必须把“缺 strict 行”也算缺失，不能只补 coverage；
- `finalize_run` 的 `len(rows) >= len(expected)` 会因两行而翻倍，完成/失败计数逻辑要按 item 聚合，不能按 row 数硬编码；
- 两个 metric 都写 `metric_version=v3`，但共享同一 Prompt 输出与 claim 集。

### 5.3 M2 展示

- Run 详情：两个卡片，`F_coverage` 标“目标指标”，`F_strict` 标“诊断指标”；
- 每个 Case：显示 `S/U/I` 计数、`insufficient_ratio`、`all_insufficient`；
- 目标 badge 只挂在 F_coverage；不要把 F_strict 当目标通过率；
- 全 insufficient：显示“证据不可判定”，不要显示“幻觉/编造”。

### 5.4 目标表 metadata

建议目标表新增（metadata-only，不改数值）：

```json
{
  "f_target_metric": "faithfulness",
  "f_target_denominator": "supported_plus_unsupported_plus_insufficient",
  "f_strict_metric": "faithfulness_strict",
  "f_strict_role": "diagnostic"
}
```

如果选 D1 方案 2，则 `f_target_metric` 改为 `faithfulness_coverage`，并需要新 revision。

## 6. 验收与测试（设计）

### 6.1 Service unit（不跑模型）

| # | S | U | I | N | 期望 F_strict | 期望 F_coverage |
|---|---|---|---|---|---|---|
| 1 | 5 | 0 | 0 | 0 | 1.0 | 1.0 |
| 2 | 3 | 1 | 0 | 0 | 0.75 | 0.75 |
| 3 | 3 | 0 | 2 | 0 | 1.0 | 0.6 |
| 4 | 0 | 1 | 0 | 0 | 0.0 | 0.0 |
| 5 | 0 | 0 | 3 | 0 | `skipped(no_decidable_claims)` | `evaluated 0.0` + `all_insufficient=true` |
| 6 | 0 | 0 | 0 | 3 | `skipped(no_scorable_claims)` | `skipped(no_scorable_claims)` |
| 7 | — | — | — | — | `skipped(context_unavailable)` | `skipped(context_unavailable)` |
| 8 | — | — | — | — | `invalid` | `invalid` |
| 9 | 3 | 0 | 2 | 0 | 1.0 | 0.6；`insufficient_ratio=0.4` |
| 10 | 3 | 1 | 2 | 0 | 0.75 | 0.5；`insufficient_ratio≈0.333` |
| 11 | 0 | 0 | 0 | 0 | `skipped(no_scorable_claims)` | `skipped(no_scorable_claims)` |

补充：

- 浮点：`>0.10 + 1e-9`；恰好 0.10 不停止；
- 全 insufficient 的 coverage 0 必须进均值（status=evaluated），否则 0 没有聚合意义；
- strict 的 skip 不得进均值；
- invalid 不得进入任何均值；
- `F_coverage <= F_strict` 作为不变量测试（两者都 evaluated 时）。

### 6.2 目标回归（不跑 Judge，用静态 claim 集）

| Case | 目标 | 期望 F_coverage | 期望 F_strict |
|---|---|---|---|
| Q11 | 0.6–0.9 | 0.833 | 1.0 |
| Q17 | 0.7–0.9 | 0.800（v1.2.0 标签） | 1.0 |
| Q21 | 0.6–0.7 | 0.600 | 1.0 |
| Q23 | 0.4–0.5 | 0.500 | 0.75 |
| Q32 | 0.9–1.0 | 1.000（v1.2.0 标签） | 1.0 |

### 6.3 不做

- 不在本轮创建 Prompt v1.2.0；
- 不改 Schema/Service/API/DB；
- 不跑单案例/10/40；
- 不把 `F_strict` 写成目标通过率。

## 7. 冻结包（建议）

B 要冻结的不是代码，而是以下四项：

| 项 | 内容 | 产物 |
|---|---|---|
| 1. 指标定义 | §2.1–2.4 的 S/U/I/N、公式、状态矩阵、全 insufficient 语义 | 本文件 + `M1-B-003` 决策记录 |
| 2. 目标映射 | `F` 目标 → `F_coverage`；`F_strict` 诊断 | 目标表 metadata revision（不改数值） |
| 3. 命名/持久化 | D1/D2/D3/D4 的选择 | 决策记录补充 |
| 4. 验收测试 | §6 的 11 条单测 + 5 条目标回归 | 测试清单（M1-C 实现前） |

**目标数值不变**：现有 40 条 `F` 目标继续有效；本冻结只声明它们作用于 `F_coverage`，不重新校准数值。若未来要给 `F_strict` 设目标，另开 revision。

冻结后才允许：

1. 写 Schema v3 / Service 双指标；
2. 跑负向测试；
3. 单案例/10/40 Judge。

## 8. 风险与待决

| 风险 | 说明 | 处理 |
|---|---|---|
| F_strict 区分度低 | 有分数的 30 条中 29 条为 1.0，容易变成“永远通过” | v1.2.0 只观察；不设硬目标 |
| 全 insufficient 0 被误读 | 0 可能被读成“幻觉” | `all_insufficient=true` + `report_label=evidence_undecidable` + 报告文案 |
| 两条 result row 重复 | strict 行若复制 details/raw_output，存储翻倍 | strict 行只存计数 + 来源 id |
| `coverage` 重名 | aggregate 的 coverage 是评测覆盖率 | 保留 `faithfulness` 作为 F_coverage key |
| invalid 持久化 | DB status 当前无 invalid | M1-C 决定新增枚举或 `failed + invalid_reason` |
| 目标表未声明分母 | 现有 target 只有 F 数值 | metadata revision 增加 `f_target_denominator` |

## 9. 建议的下一步

1. 人工审核本文件，重点拍板：
   - D1：`faithfulness`（F_coverage）+ `faithfulness_strict`，还是双显式 key；
   - D2：两条 result row，strict 只存计数；
   - D3：全 insufficient 的 coverage 0 + flag；
   - D4：F_strict 只观察。
2. 审核通过后，把本文件的关键决定写入 `M1-B-003` 冻结记录；
3. 再做目标表 metadata revision（不改数值）；
4. 最后才进入 Schema/Service 实现。

**在 M1-B-003 冻结前，不启动 M1-C，不写代码，不跑 Judge。**
