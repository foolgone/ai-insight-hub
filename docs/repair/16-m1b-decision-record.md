# M1-B 决策记录：证据契约、F 分母与目标影响

> Decision ID：`M1-B-002`
> 日期：2026-11-18
> 决策人：江晚
> 状态：`implemented`（文档已改；跨文档一致性已人工核对，未做自动化验收）/ **不是 `accepted`**（目标影响未决）
> **2026-11-19 更新：人工改选方案 B（F_strict + F_coverage）。本记录的单 F 公式作为历史决策保留，不再作为实现依据；B 的设计评估见 `18-m1b-dual-metric-design-evaluation.md`（`M1-B-003`，`proposed_pending_human`）。**
> 范围：Schema / Service / Judge output contract；不创建/激活 v1.2.0，不修改 Prompt/Service/Schema/API/DB，不运行 Judge。

## 1. 背景

`d64cb13` 曾把 P1-2 定为“`supported_without_evidence` 降级 `insufficient_evidence`，claim 保留在分母”，并就地修改了已冻结的 `12-judge-semantic-spec.md`。该修改与 2026-11-18 的人工决策冲突：

- 人工决策：`supported` 无 Evidence → **整条 Metric invalid**，不能让无证据 Claim 参与有效评分；
- 冻结规范：`supported` 但 evidence 无效 → 降级 `insufficient_evidence`。

本轮处理：

1. 从 `92ce3ab` 恢复 `12-judge-semantic-spec.md` 原文；旧 freeze record 未改写。
2. 新建本决策记录，作为 v1.2.0 的实现契约与语义修订记录。
3. Schema/Service 设计、验收计划按本记录统一口径。
4. **不改** frozen target 表；目标影响单列，见 §4。

## 2. 决策

### 2.1 P1-1：测试分层（关闭）

| 测试类型 | 验证对象 | 不验证 |
|---|---|---|
| Schema 测试 | 字段、枚举、类型 | 语义标签是否正确 |
| Service unit | 分母、skip/invalid、evidence 校验、浮点、聚合 | “这句话原本是不是 policy_scope” |
| Judge acceptance | 模型标签是否符合 Gold | 程序是否按标签正确计分 |
| Integration | 模型输出 → 校验 → 计分 → 持久化 | 单层内部实现 |

Service **不得**用关键词猜 `policy_scope`、不得把 `meta` 自动改回 factual。语义标签错误由 Judge acceptance 负责。

### 2.2 P1-2：证据契约（选择 A）

| 情况 | Metric 结果 | 说明 |
|---|---|---|
| `claim_subtype` 缺失 | `invalid(contract_violation)` | 结构不完整 |
| `claim_subtype` 非法 | `invalid` | 不符合 Schema |
| `claim_type` 与 subtype 不一致 | `invalid` | 类型契约冲突 |
| `supported` 无 Evidence | `invalid` | 无证据却宣称支持 |
| `supported` 只有 v1 `evidence`、无 v3 `evidence_refs` | `invalid` | v3 契约要求 `evidence_refs`，不得自动迁移 |
| Evidence `context_id` 不存在 | `invalid` | 引用不存在 |
| Evidence 非逐字命中 | `invalid` | 引用真实性校验失败 |
| Evidence 引用 answer | `invalid` | 证据必须来自 context |
| Evidence 存在但不支持 Claim | `unsupported` | 语义判断，不是结构违约 |
| 合法 `insufficient_evidence` | 正常评价 | 不进 F 分母，单独统计 |
| 全部 Claim 为 non_factual | `skipped(no_scorable_claims)` | 没有可评价事实 |
| 全部 factual 均为 insufficient | `skipped(no_decidable_claims)` | 没有可计算支持比例，**不是 0.0** |

### 2.3 F 公式

```text
F = supported / (supported + unsupported)
```

- `insufficient_evidence` 不进分母；
- 必须独立输出 `insufficient_count`、`insufficient_ratio`；
- 分母为 0（全部 insufficient）→ `skipped(no_decidable_claims)`；
- `unsupported` 是合法评价结果，必须进分母；
- `invalid` / `failed(execution)` 不产出分数，不进均值。

### 2.4 状态词汇

| 状态 | 含义 | 进均值 |
|---|---|---|
| `evaluated` | 至少一条可判定 factual | 是 |
| `skipped(no_scorable_claims)` | 全部 non_factual | 否 |
| `skipped(no_decidable_claims)` | 全部 factual 都 insufficient | 否 |
| `skipped(context_unavailable)` | 无上下文 | 否 |
| `invalid(contract_violation)` | 输出/证据契约违约 | 否 |
| `failed(execution)` | Judge 调用失败且重试耗尽 | 否 |

`invalid` 与 `failed(execution)` 必须分开：前者是模型输出违约，后者是执行失败。

## 3. 与 frozen spec 的差异（语义修订）

本轮**没有**修改 `12-judge-semantic-spec.md` 文件；但以下规则在 v1.2.0 中与原文不同，属于语义修订，不是单纯实现细节：

| 项 | frozen spec 原文 | v1.2.0（M1-B-002） |
|---|---|---|
| `supported` 无 evidence | “直接判为校验失败，不进入 supported”（§5.4） | 整条 metric `invalid` |
| evidence quote 非逐字 | 降级 `insufficient_evidence`，记 `evidence_validation_failed`（§5.4） | 整条 metric `invalid` |
| F 分母 | “scorable factual claims”（§11.1）；v1.1.x 实现含 insufficient | 只含 supported + unsupported；insufficient 排除 |
| `policy_scope`/`policy_relationship` 无依据 | 判 `insufficient_evidence`，“不得退出分母”（§6.1） | 仍判 `insufficient_evidence`；但不进 F 分母，改记 `insufficient_count/ratio` |
| 全部 insufficient | v1.1.x 实现为 `evaluated 0.0` | `skipped(no_decidable_claims)` |
| 全部 claim 无效 | `failed(all_invalid)` | `invalid(contract_violation)` |

因此：

- 旧 freeze record 保留，不覆盖；
- 本记录是 v1.2.0 的语义修订与实现契约；
- 若未来要让 v1.1.x 也采用新契约，必须另开版本，不得回填。

## 4. 目标影响（P0，未决）

frozen target 表 `pilot-40-targets-v1.2.0.json`（SHA `34357b34…`）本身未声明 F 分母；从 Q21/Q17 的目标值与 v1.1.5 结果反推，它是按旧 F 分母（insufficient 计入）校准的。改用 `M1-B-002` 公式后，含 insufficient 的案例 F 会上升，部分 frozen target 不可达或越界。

用 v1.1.5 的 40 条结果做静态重算（不是新 Judge 运行）：

| Case | v1.1.5 F（旧分母） | 新公式 F | frozen target | 影响 |
|---|---|---|---|---|
| Q21 | 0.600（3 supported / 5 scorable） | 1.000（3/3） | 0.6–0.7 | **不可达**；Q21#3 的 insufficient 设计目的被抵消 |
| Q23 | 0.500（3/6） | 0.750（3/4） | 0.4–0.5 | **越界** |
| Q17 | 1.000（cl5 为 meta）；v1.2.0 旧分母约 0.800（4/5） | 1.000（4/4） | 0.7–0.9 | 上界 +0.1，边界 |
| Q11 | 0.833（5/6） | 1.000（5/5） | 0.6–0.9 | 上界 +0.1，边界 |
| Q32 | 0.750（3/4） | 1.000（3/3） | 0.9–1.0 | 通过 |
| Q15/Q20/Q28/Q31 | 0.75–0.86 | 1.000 | 上限 1.0 | 通过 |

结论：

- **Q21、Q23 与 frozen target 直接冲突；Q17、Q11 处于边界。**
- 不能把“新公式 F=1.0”写成目标通过，也不能回头改 frozen target 的 SHA。
- 目标表必须二选一处理：按新公式重新校准并出新 revision，或改回包含 insufficient 的目标口径。

### 4.1 可选方案

| 方案 | 做法 | 优点 | 代价 |
|---|---|---|---|
| A（当前决策） | 单 F = supported/(supported+unsupported)；重算 Q11/Q17/Q21/Q23 目标 | 语义最纯：只衡量“可判定 claim 中是否被支持” | Q21#3 不再降低 F；证据覆盖率只能看 insufficient_ratio |
| B（推荐评估） | 双指标：`F_strict` = supported/(supported+unsupported)，`F_coverage` = supported/(supported+unsupported+insufficient)；目标暂挂 `F_coverage` | 同时保留“幻觉”和“证据覆盖”两个信号；Q21/Q23 目标可继续用 | 多一个指标/字段；报告和聚合要改 |
| C | 单 F 改为 supported/(supported+unsupported+insufficient)，全 insufficient 才 skip | 与旧目标兼容；Q21 0.6 可复现 | 与“insufficient 不进分母”的人工决策相反 |

**目标表修订时必须新增 `f_denominator` 字段**（例如 `supported_plus_unsupported` / `supported_plus_unsupported_plus_insufficient`），否则下一轮还会出现同样的口径歧义。

**建议**：在 M1-C 实现前先定 A/B/C。若选 A，必须重算并重冻 Q11/Q17/Q21/Q23 目标；若选 B，目标可暂留，但要新增 `F_coverage` 字段与聚合键；若选 C，需要撤销本轮公式决策。

## 5. 冻结控制

- `12-judge-semantic-spec.md`：恢复 `92ce3ab` 原文，SHA 不变；不覆盖旧 freeze record。
- `pilot-40-final-labels.json`：SHA `f139623f…` 不变，只作分类。
- `pilot-40-targets-v1.2.0.json`：SHA `34357b34…` 不变；本记录不修改目标值。
- 本记录：新增文件，作为 v1.2.0 语义修订/实现契约；需人工确认 §4 方案后才可把 M1-B 标为 `accepted`。
- 任何目标变更必须新文件 + 新 SHA + 新 validation，不得静默改旧文件。

## 6. 验收映射

| 决策 | Service unit | Judge acceptance | 集成 |
|---|---|---|---|
| 缺/非法 subtype → invalid | 1–3 | — | 落库 status/reason 正确 |
| supported 无 evidence → invalid | 4 | — | 不产生分数 |
| context_id 不存在 / quote 非逐字 / 引用 answer → invalid | 5–6 | — | 不产生分数 |
| evidence 存在但不支持 → unsupported | 12 | Q17/Q30 标签 | 进分母 |
| 合法 insufficient → 不进分母、单独统计 | 11–12 | Q21#3 | `insufficient_count/ratio` 落库 |
| 全 non_factual → skipped(no_scorable_claims) | 10 | — | 不进均值 |
| 全 insufficient → skipped(no_decidable_claims) | 11 | — | 不进均值，不是 0.0 |
| policy_scope/relationship 不回退 | 15 | 1–2、6–7 | 分母保留 |

### 6.1 持久化/API 映射（M1-C 待定）

`invalid` 是 metric 结果，不是 DB 现状。`rag_evaluation_results.status` 当前枚举只有 `evaluated / skipped / failed`。M1-C 必须二选一：

1. 新增 `invalid` 枚举（需要 migration），API/M2 直接显示 `invalid`；或
2. 落 `status=failed` + `details.invalid_reason`，但聚合、报告、M2 必须把 invalid 与 `failed(execution)` 分开，不得把 invalid 计入“执行失败”。

无论选哪种，`invalid` 不得进入均值，也不得被写成 PASS。

## 7. 不做

- 不创建/激活 v1.2.0；
- 不修改 Prompt/Service/Schema/API/DB；
- 不运行 Judge；
- 不修改 frozen target 数值；
- 不把 M1-B 标为 `accepted`。
