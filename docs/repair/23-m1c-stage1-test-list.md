# M1-C Stage 1：测试清单与预期结果

> 状态：测试设计，只写清单；**不写业务代码、不跑 Judge、不创建/激活 v1.2.0**。
> 版本：Stage 1 rev2（2026-11-19，按人工审核退回意见重写）。
> 依据：`19-m1b-003-freeze-draft.md`（r2，唯一指标/生命周期/invalid 契约）、`22-m1c-stage0-gap-list.md`（rev2）、`12-judge-semantic-spec.md`（frozen）、`15-phase3e-v1.2.0-schema-service-design.md` §2.1。
>
> **本版最重要的修正：**
> 1. 十二条核心测试改为审核列出的 12 项生命周期/聚合要求（L01–L12）；
> 2. **T07/T08 改为 `invalid(contract_violation)`**，删除旧的“降级 I / coverage 0.5 / evaluated 0.0”预期；
> 3. T11 拆成 T11a（默认漂移仍复制父快照）与 T11b（显式换配置新建 Run）；
> 4. 补 evaluated+failed 同 Item、cancelled/timeout `unprocessed`、均值排除、历史 Run 兼容、只缺 strict 的派生；
> 5. T12 浮点只作为附加测试，不再占用核心第 12 条；
> 6. v2 降级语义只允许出现在 V01 历史兼容测试，不得进入 v3 契约测试；
> 7. 目标 SHA 改为 `pilot-40-targets-v1.2.0-v1.0.2.json`（`3ee15dfc…`），`34357b34…` 只读。

## 0. 测试分层与编号

| 层 | 编号 | 数量 | 是否跑模型 | 目的 |
|---|---|---|---:|---|
| 十二条核心测试 | `L01–L12` | 12 | 否 | 生命周期、Item 聚合、retry、历史兼容 |
| 附加契约/公式测试 | `F01–F05`、`T06–T10`、`T12`、`V01` | 12 | 否 | 公式、状态矩阵、invalid 契约、生命周期补充、浮点、v2 历史 |
| 目标回归 | `Q11/Q17/Q21/Q23/Q32` | 5 | 否（静态 claim 集） | F_coverage/F_strict 与目标映射 |
| Judge acceptance | 后续 | — | 是 | 语义标签正确性；不在本轮 |

编号说明：

- `L` = lifecycle/aggregation，对应审核的 12 项原始要求；
- `F` = formula，对应 r2 §9.1 的 S/U/I/N 组合；
- `T` = contract，负向/持久化/浮点；
- `V` = v2 兼容，只验证历史语义，不验证 v3。

**所有预期先于实现固定；实现后不得反过来改预期。**

## 1. 十二条核心测试（L01–L12）

### 1.1 审核 12 项 → L01–L12 对照

| # | 审核原始要求 | 本清单 |
|---|---|---|
| 1 | retry 配置继承 | L01 |
| 2 | 默认 Prompt 变化后 retry 仍用父配置 | L02 |
| 3 | 不同配置必须新建 Run | L03 |
| 4 | 两个 Metric Row 对应一个 Item | L04 |
| 5 | evaluated + skipped 聚合 | L05 |
| 6 | evaluated + failed 跨 Metric | L06 |
| 7 | invalid 与 execution failed 分离 | L07 |
| 8 | 全 insufficient 不判 skipped Item | L08 |
| 9 | cancelled / timeout 的 unprocessed | L09 |
| 10 | Item 数量守恒（含 unprocessed） | L10 |
| 11 | 均值排除 invalid/failed/skipped | L11 |
| 12 | 历史 Run 兼容性 | L12 |

### 1.2 十二条速览

| ID | 场景 | 关键预期 |
|---|---|---|
| L01 | retry 无显式覆盖 | 子 Run 逐字段复制父快照；版本不混写 |
| L02 | 默认 Prompt/Schema 漂移 | retry 仍用父快照；不拒绝、不静默升级 |
| L03 | 显式换配置 / 父快照不可用 | 拒绝 retry；不创建子 Run |
| L04 | 1 Item 双 F 行 | 2 rows / 1 case；strict 指向 coverage |
| L05 | evaluated + skipped（3 Items / 6 rows） | evaluated=2、skipped=1、completed=2、success=0.666667 |
| L06 | evaluated + failed 跨 Metric（2 Items） | failed=1、evaluated=1；F mean=0.75 |
| L07 | invalid vs execution failed（4 Items） | invalid=1、failed=1、evaluated=1、skipped=1；不混算 |
| L08 | 全 insufficient | coverage 0.0 evaluated；strict skip；Item evaluated |
| L09 | cancelled / timeout（5 Items） | unprocessed=2；completion=0.6 |
| L10 | 守恒（10 Items） | 4+1+2+1+2=10；completed=4 |
| L11 | 均值排除（5 rows） | mean=0.75；evaluated=2 |
| L12 | 历史 v2 Run | completed 回填=2；不补 strict；不混算 |

### 1.3 Retry：L01–L03（= T11a / T11b）

#### L01 retry 配置继承（T11a）

**Setup**

- 父 Run：`prompt_version=v1.2.0`、`schema_version=v3`、`metric_version=v3`、`model=m1`、`retrieval_config=R1`、`item_selection=S1`；
- 父 Run 已终态，存在 failed/缺失 item/metric。

**Action**

- 调用 retry，不传任何 Prompt/Schema/模型/检索覆盖参数。

**Expected**

- 创建子 Run：`parent_run_id=父`、`attempt=父.attempt+1`、`retry_scope=failed_only`；
- 子 Run 的 `judge_config` / `config_snapshot` / `retrieval_config` / `item_selection` 与父 Run 逐字段一致；
- 子 Run 的 `metric_version=v3`、`schema_version=v3`、`prompt_sha256=父`；
- 子 Run 的 result row 版本与父快照一致；
- 若父 coverage failed/缺失/版本过期：子 Run 重新执行 coverage，再从新 coverage 派生 strict；不得只重算 strict；
- 不得调用当前默认 `build_judge_config()` 覆盖父快照。

**Negative**

- 任一字段与父不一致 → 失败；
- 子 Run 出现 v2/v3 混写 → 失败。

#### L02 默认 Prompt 漂移后仍用父快照（T11a）

**Setup**

- 父 Run：`v1.2.0 / schema v3 / metric v3`；
- 测试 fixture 把“当前默认”改为 `v1.3.0 / schema v4`（仅模拟默认值变化，不创建/激活 v1.3.0）；
- retry 不传显式覆盖。

**Expected**

- retry **成功**，不因默认值变化被拒绝；
- 子 Run 仍复制父 `v1.2.0 / v3`；
- 子 Run 不出现 `v1.3.0` 或 `schema v4` 行；
- 不出现 metric version 混写。

**Negative**

- 以“当前默认已变化”为由拒绝 retry → 失败（这是审核指出的写反点）；
- 静默升级到新默认 → 失败。

#### L03 显式换配置 / 父快照不可用 → 新建 Run（T11b）

**Setup**

- 父 Run：`v1.2.0 / schema v3 / metric v3`；
- 分别测试以下显式变化：
  - `prompt_version=v1.3.0`；
  - `schema_version=v4`；
  - `model=m2`；
  - `retrieval_config=R2`；
  - `item_selection=S2`；
- 另测父快照不可用：父 Prompt 资产被删除 / Schema 无法加载。

**说明**

- 若 retry API 不提供覆盖参数，则“显式换配置”通过创建新 Run 接口完成；retry 端仍不得读取当前默认值。

**Expected**

- 返回领域冲突错误（HTTP 409 或等价），消息明确“配置已变化/父快照不可用，必须新建 Run”；
- 不创建子 Run、不写 result row；
- 父 Run 不变；
- 不得回退到当前默认配置。

**Negative**

- 静默换配置后创建子 Run → 失败；
- 父快照不可用时用当前默认兜底 → 失败。

### 1.4 双行与 Item 状态：L04–L07

#### L04 两个 Metric Row 对应一个 Item

**Setup**

- 1 个 item；coverage evaluated 1.0；strict 由同一 claims 派生 evaluated 1.0。

**Expected**

- 2 条 result row，1 个 distinct item；
- `strict.derived_from_result_id = coverage.id`；
- 两行同一 `run_id` / `dataset_item_id` / `metric_version` / `schema_version` / `prompt_sha256`；
- 先写 coverage 并 flush，再写 strict；
- strict 不重复保存完整 claims/evidence/raw_output（按 r2 §4.1）；
- 无 orphan strict（coverage 不存在时 strict 不得存在）；
- 同一 `(run_id, dataset_item_id, metric_name, metric_version)` 重投递幂等，不产生重复行；
- `total_items=1`、`processed_items=1`、`evaluated_items=1`、`completed_items=1`；
- `rows=2`、`cases=1`，不得把 rows 当 cases。

#### L05 evaluated + skipped 聚合

**Setup（3 items，双 F 行，共 6 rows）**

| Item | coverage | strict | Item 状态 |
|---|---|---|---|
| I1 | evaluated 1.0 | evaluated 1.0 | evaluated |
| I2 | evaluated 0.0（all_insufficient） | skipped(no_decidable_claims) | evaluated |
| I3 | skipped(no_scorable_claims) | skipped(no_scorable_claims) | skipped |

**Expected**

- `total_items=3`、`rows=6`、`cases=3`；
- `evaluated_items=2`（I1、I2）；
- `skipped_items=1`（I3）；
- `invalid_items=0`、`failed_items=0`、`unprocessed_items=0`；
- `completed_items=2`（= evaluated，不是 3）；
- `processed_items=3`、`completion_rate=1.0`、`success_rate=0.666667`；
- I2 的 `skipped_metrics=[faithfulness_strict]`，但 Item 仍是 evaluated；
- I2 必须进入 F_coverage 均值（0.0 是有效分数），不进 F_strict 均值。

**Negative**

- 把 I2 算作 skipped → 失败；
- 把 I3 算作 completed → 失败；
- `completed_items=3` → 失败。

#### L06 evaluated + failed 跨 Metric

**Setup（2 items，metrics = coverage / strict / answer_correctness）**

| Item | coverage | strict | answer_correctness | Item 状态 |
|---|---|---|---|---|
| I1 | evaluated 1.0 | evaluated 1.0 | failed(execution) | failed |
| I2 | evaluated 0.5 | evaluated 0.5 | evaluated 1.0 | evaluated |

**Expected**

- `failed_items=1`（I1）、`evaluated_items=1`（I2）；
- `completed_items=1`、`completion_rate=1.0`、`success_rate=0.5`；
- I1 的 Item 状态是 failed（任一 expected metric failed 优先），不是 evaluated；
- **per-metric 均值独立**：F_coverage 两行都 evaluated，均值 = (1.0+0.5)/2 = **0.75**；answer_correctness 只取 I2 = **1.0**；
- Item failed 不会把该 Item 的 evaluated F 行从 F 均值中删除；
- coverage failed 时 strict 必须 failed，不得 evaluated（另加负向断言）。

**Negative**

- 把 I1 算作 evaluated → 失败；
- 把 F 均值算成只取 I2（0.5）→ 失败；
- coverage failed 但 strict evaluated → 失败。

#### L07 invalid 与 execution failed 分离

**Setup（4 items，双 F 行）**

| Item | coverage | strict | Item 状态 |
|---|---|---|---|
| I1 | invalid(contract_violation) | invalid(contract_violation) | invalid |
| I2 | failed(execution) | failed(execution) | failed |
| I3 | evaluated 1.0 | evaluated 1.0 | evaluated |
| I4 | skipped(context_unavailable) | skipped(context_unavailable) | skipped |

**Expected**

- `invalid_items=1`、`failed_items=1`、`evaluated_items=1`、`skipped_items=1`、`unprocessed_items=0`；
- `completed_items=1`、`completion_rate=1.0`、`success_rate=0.25`；
- invalid 不得计入 `failed_items`，failed 不得计入 `invalid_items`；
- invalid/failed 均不进均值；
- I1 `invalid_reason=contract_violation`；I2 为 execution failure reason；
- API/报告标签分别为“输出契约无效”和“执行失败”，不得混用。

**A/B 持久化补充（= T09）**

- A：`status=invalid` + `invalid_reason` → invalid_items；
- B：`status=failed` + `invalid_reason` → 聚合层必须先看 `invalid_reason`，归 invalid_items，不得算 failed；
- A 的 `status=invalid` 且 `invalid_reason IS NULL` 必须被 DB CHECK 拒绝；
- B 无 `invalid_reason` 才是 execution failed。

### 1.5 全 insufficient 与 unprocessed：L08–L10

#### L08 全 insufficient 不判 skipped Item

**Setup**

- 1 个 item：S=0、U=0、I=3、N=0。

**Expected**

- coverage：`status=evaluated`、`score=0.0`、`all_insufficient=true`、`insufficient_ratio=1.0`、`supported=0`、`unsupported=0`、`insufficient=3`；
- strict：`status=skipped`、`reason=no_decidable_claims`，无分数；
- Item 状态 = `evaluated`，不是 `skipped`；
- `skipped_metrics=[faithfulness_strict]`；
- `completed_items=1`、`success_rate=1.0`（Item 被成功评价，尽管 coverage 是 0）；
- coverage 均值包含 0.0；strict 均值 `evaluated_count=0`、`mean=null`，不得补 0。

**Negative**

- Item 判 skipped → 失败；
- coverage 判 skipped 或 invalid → 失败；
- strict 补 0 分 → 失败。

#### L09 cancelled / timeout 的 unprocessed

**Setup**

- Run 选中 5 个 item，metrics = coverage + strict；
- I1 evaluated、I2 invalid、I3 failed；
- I4 只有 coverage skipped、strict 缺失（部分行）；
- I5 完全没有 result row；
- Run 因用户取消或时间预算耗尽停止：`stopped_reason=cancelled` 或 `time_budget_exhausted`。

**Expected**

- `total_items=5`；
- `evaluated_items=1`、`invalid_items=1`、`failed_items=1`、`skipped_items=0`、`unprocessed_items=2`；
- `processed_items=3`、`completion_rate=3/5=0.6`、`success_rate=1/5=0.2`；
- `completed_items=1`；
- 守恒：`5 = 1 + 1 + 1 + 0 + 2`；
- I4（部分行）与 I5（无行）都算 unprocessed，不得生成/补全 skipped 行，不得计入 skipped_items；
- `stopped_reason` 保留，不以 unprocessed 伪装“已处理”。

**Negative**

- 把 I4 或 I5 算 skipped → 失败；
- 把 completion_rate 算成 1.0 → 失败。

#### L10 Item 数量守恒（含 unprocessed）

**Setup**

- `total_items=10`；
- Item 状态分布：evaluated=4、invalid=1、failed=2、skipped=1、unprocessed=2；
- 每个 processed item 有 coverage+strict 两行，共 8×2=16 rows；本场景的 2 个 unprocessed item 无行（部分行 unprocessed 见 L09）。

**Expected**

- `4 + 1 + 2 + 1 + 2 = 10`；
- `processed_items=8`、`completion_rate=0.8`、`success_rate=0.4`、`completed_items=4`；
- `rows=16`、`cases=10`，`total_items != rows`；
- 每个 item 恰好属于一个 bucket，不得重复计数；
- 同一逻辑适用于 40 items；即使有 coverage/strict/C/R 多行，`total_items` 仍是 40，不是 80/160；
- 不得用 `len(results)` 作为 `total_items` 或 `completed_items`。

### 1.6 均值与历史兼容：L11–L12

#### L11 均值排除 invalid/failed/skipped

**Setup（faithfulness 5 行）**

| row | status | score |
|---|---|---|
| 1 | evaluated | 1.0 |
| 2 | evaluated | 0.5 |
| 3 | invalid | — |
| 4 | failed | — |
| 5 | skipped | — |

**Expected**

- `mean = (1.0 + 0.5) / 2 = 0.75`；
- `evaluated=2`、`invalid=1`、`failed=1`、`skipped=1`；
- invalid/failed/skipped 不进分母，不补 0，不做插补；
- 另给 strict 5 行：evaluated 1.0、evaluated 0.8、invalid、failed、skipped → `mean=0.9`、`evaluated=2`；
- 负向：不得算成 `0.3`（sum/5）或 `0.15`（sum/10）。

#### L12 历史 Run 兼容性

**Setup**

- 旧 v2 Run：`metric_version=v2`，3 个 item；
- I1/I2 evaluated，I3 全部 skipped；
- 旧 `completed_items=3`（历史语义：含 skipped 的已处理数）；
- 没有 strict 行。

**Action**

- 执行 migration 022 回填；
- 通过 API 读取旧 Run；
- 尝试 retry 旧 Run（父 v2 快照可用/不可用两种）。

**Expected（migration 022 后）**

- `total_items=3`；
- `evaluated_items=2`、`skipped_items=1`、`invalid_items=0`、`failed_items=0`、`unprocessed_items=0`；
- `completed_items=2`（A 方案：`completed = evaluated`）；
- 守恒：`3 = 2 + 0 + 0 + 1 + 0`；
- 旧 result row 仍是 `metric_version=v2`，不被改写为 v3；
- 不回填 strict；旧 Run 不因迁移产生新行；
- API 返回 v2 数据，不用 v3 语义重新解释；
- 新 v3 Run 单独聚合，v2/v3 均值不混算；
- retry 旧 Run：父 v2 快照可用 → 子 Run 仍为 v2，不升级 v3；父快照不可用 → 拒绝 retry，不得用当前 v3 默认兜底；
- 旧 v2 payload 的旧 subtype 名称可解析；旧 subtype 归一/降级只在 v2 路径。

**Negative**

- 迁移后用 v3 语义重算旧 claims → 失败；
- 给旧 Run 补 strict 行 → 失败；
- 新旧版本混入同一均值 → 失败；
- retry 旧 Run 时静默升级 v3 → 失败。

## 2. 附加契约/公式测试（不计入 12 条）

### 2.1 公式与状态矩阵

| ID | 输入 S/U/I/N | F_coverage | F_strict | 其他断言 |
|---|---|---|---|---|
| F01 | 5/0/0/0 | **evaluated 1.0** | **evaluated 1.0** | 双行 evaluated；Item evaluated |
| F02 | 3/1/2/0 | **evaluated 0.5** | **evaluated 0.75** | `insufficient_ratio=0.333333`；U=1 |
| F03 | 0/1/0/0 | **evaluated 0.0** | **evaluated 0.0** | 全 unsupported；Item evaluated |
| F04 | 0/0/0/3 | **skipped(no_scorable_claims)** | **skipped(no_scorable_claims)** | Item skipped |
| F05 | context_unavailable | **skipped(context_unavailable)** | **skipped(context_unavailable)** | 不调 Judge；不是 0，不是 PASS |

公式：

```text
F01: coverage = 5/(5+0+0)=1.0; strict = 5/(5+0)=1.0
F02: coverage = 3/(3+1+2)=0.5; strict = 3/(3+1)=0.75
F03: coverage = 0/(0+1+0)=0.0; strict = 0/(0+1)=0.0
F04/F05: 无 factual 分母 / 无上下文 -> skipped
```

**r2 §9.1 的 11 组 Service 组合（同一参数化测试）：**

| # | S | U | I | N | F_coverage | F_strict | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | 5 | 0 | 0 | 0 | 1.0 | 1.0 | F01 |
| 2 | 3 | 1 | 0 | 0 | 0.75 | 0.75 | I=0 时两者相等 |
| 3 | 3 | 0 | 2 | 0 | 0.6 | 1.0 | 有 I 但无 U |
| 4 | 0 | 1 | 0 | 0 | 0.0 | 0.0 | F03 |
| 5 | 0 | 0 | 3 | 0 | evaluated 0.0 + all_insufficient | skipped(no_decidable_claims) | L08 |
| 6 | 0 | 0 | 0 | 3 | skipped(no_scorable_claims) | skipped(no_scorable_claims) | F04 |
| 7 | 0 | 0 | 0 | 0 | skipped(no_scorable_claims) | skipped(no_scorable_claims) | 空 claims |
| 8 | — | — | — | — | skipped(context_unavailable) | skipped(context_unavailable) | F05 |
| 9 | — | — | — | — | invalid(contract_violation) | invalid(contract_violation) | T06–T08 |
| 10 | 3 | 1 | 2 | 0 | 0.5 | 0.75 | F02 |
| 11 | 3 | 0 | 2 | 0 | 0.6 | 1.0 | 有 I 但无 U |

> #8/#9 不是 S/U/I/N 组合，分别由 F05 与 T06–T08 覆盖；其余 9 组用参数化测试一次性覆盖。

### 2.2 契约负向

| ID | 输入 | 预期 |
|---|---|---|
| T06 | 缺 `claim_subtype` / 非法 subtype / type 不一致 | **both `invalid(contract_violation)`**；无分数；`invalid_items=1`；不得 failed/skipped |
| T07 | `supported` 但无 evidence | **both `invalid(contract_violation)`**；**不得降级 I**；**不得产出任何分数**；`invalid_items=1`、`failed_items=0`；不进均值 |
| T08 | quote 非逐字 / `context_id` 不存在 / quote 引用 answer / 冲突单边 evidence | **both `invalid(contract_violation)`**；**不得 evaluated 0.0**；**不得 all_insufficient**；`invalid_items=1`、`failed_items=0`；不得降级；不进均值 |
| T09 | A：`status=invalid + invalid_reason`；B：`status=failed + invalid_reason` | 均归 `invalid_items=1`、`failed_items=0`；不进均值；A 缺 reason 被 CHECK 拒绝；B 无 reason 才是 execution failed |

### 2.3 生命周期补充

| ID | 输入 | 预期 |
|---|---|---|
| T10 | 只缺 strict；coverage 存在且 current | 从同一 coverage 派生 strict；`derived_from_result_id` 指向该 coverage；**不再调用 Judge**；不新增/覆盖 coverage 行；不得出现 orphan strict。另测：strict 存在但 coverage 过期 → 删除/忽略旧 strict，按新 coverage 重建，不得保留旧 strict。 |

### 2.4 Retry 别名

| ID | 对应 | 说明 |
|---|---|---|
| T11a | L01 + L02 | 配置不变/默认漂移 → 仍复制父快照；不得拒绝 |
| T11b | L03 | 显式换 Prompt/Schema/模型/检索，或父快照不可用 → 拒绝 retry，新建 Run |

### 2.5 浮点与 v2 历史

| ID | 输入 | 预期 |
|---|---|---|
| T12 | old=0.80；new=0.70 / 0.699999 | 0.70 差值恰好 0.10 → **不停止**；0.699999 差值 0.100001 → **停止**；比较用 `> 0.10 + 1e-9` |
| V01 | v2 历史 payload | 只允许在此验证旧语义：`supported` 无 evidence → 降级 insufficient；quote 非逐字 → 降级 insufficient；未知 context → 降级 insufficient；非法 subtype → 归一 policy/meta 并记 error；全 insufficient → 旧单指标 0.0。**这些行为不得出现在 v3 契约测试** |

**V01 边界声明：**

- V01 是 v2 parser/历史兼容测试，不是 v3 验收；
- 同一 payload 若标 `schema_version=v3`，必须走 T06/T07/T08 的 invalid 路径；
- 禁止把 V01 的降级预期复制到任何 v3 测试。

## 3. 目标回归（静态 claim 集，不跑 Judge）

| Case | 目标区间 | F_coverage | F_strict | 预期 |
|---|---|---|---|---|
| Q11 | 0.6–0.9 | **0.833333** | **1.0** | PASS |
| Q17 | 0.7–0.9 | **0.800000**（v1.2.0 预期标签） | **1.0** | PASS |
| Q21 | 0.6–0.7 | **0.600000** | **1.0** | PASS |
| Q23 | 0.4–0.5 | **0.500000** | **0.750000** | PASS |
| Q32 | 0.9–1.0 | **1.000000**（3 factual 点；cl1=uncertainty） | **1.0** | PASS |

**文件与 SHA（修正）：**

- 目标值来源：`docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.2.json`；
- SHA256：`3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846`；
- revision：v1.0.2；
- 旧文件 `pilot-40-targets-v1.2.0.json`（SHA `34357b34c3d0fc85e78f90eeebb353b25a148926e3a55b19f17cc23b08b2b5eb`，v1.0.1）**只读**，不得再作为目标值来源。

说明：

- Q17/Q32 使用 v1.2.0 预期标签，不是 v1.1.5 实测值；不得写成“Judge 已实测”；
- 目标回归只验证公式/分母/目标映射，不验证 Judge 语义；
- F_strict 只记录，不作为目标通过率；
- 任何跨版本（v2/v3）均值必须分开。

## 4. 执行顺序

1. **先写契约负向**：T06、T07、T08、T09、V01（V01 只锁 v2 历史边界）。
2. 再写公式/状态矩阵：F01–F05。
3. 再写生命周期补充：T10。
4. 再写 Item 聚合：L04–L11。
5. 再写 retry：L01–L03。
6. 再写 migration/历史兼容：L12。
7. 再写浮点：T12。
8. 最后写目标回归 5 条。
9. 以上全部通过后，才允许进入 Judge acceptance（单案例 Q17/Q30/Q32/Q36）。
10. 单案例通过后，才允许 10 条闸门；10 条通过后，才允许 40 条。

**不得先跑 Judge 看结果再定测试。**

## 5. 通过标准

### 5.1 核心十二条

- L01–L12 **12/12** 通过；
- L02 默认漂移不拒绝 retry；L03 显式换配置/父快照不可用才拒绝；
- L05 的 I2（全 insufficient）必须算 evaluated，不得算 skipped；
- L06 的 I1 必须算 failed，但 F_coverage 均值仍包含其 evaluated 行（0.75）；不得把 Item failed 当成 F 行 failed；
- L07 invalid 与 failed 独立计数、独立标签、均不进均值；
- L08 Item 不得 skipped；coverage 0.0 进均值；strict 不补 0；
- L09 `unprocessed_items=2`，不得伪装 skipped；
- L10 守恒 `total = evaluated + invalid + failed + skipped + unprocessed`；
- L11 均值分母只含 evaluated；
- L12 旧 Run 保持 v2，不回填 strict，不混算；`completed_items` 回填为 evaluated。

### 5.2 附加测试

- F01–F05、T06–T10、T12、V01 全部通过；
- **T07/T08 必须是 invalid**，不得出现任何降级/0 分/all_insufficient 预期；
- T10 只缺 strict 时不得再调 Judge，不得新增/覆盖 coverage；
- V01 的降级行为只存在于 v2 路径。

### 5.3 目标回归

- 5/5 通过；
- 数值与上表一致（6 位小数）；
- Q32 不得 skipped；
- 目标 SHA 使用 `3ee15dfc…`，不得引用 `34357b34…` 作为 v1.0.2 来源。

### 5.4 失败处理

- 任一测试失败：先修契约/实现，不得改预期；
- 若预期本身错误：新开 revision，记录原因，不静默改表；
- 不允许“先跑 Judge 看结果再定测试”。

## 6. 不做

- 不跑 Judge；
- 不创建/激活 v1.2.0；
- 不修改 Prompt/Service/Schema/API/DB；
- 不创建 migration 022；
- 不进入 M1-D/M1-E；
- 不把 Stage 1 测试通过当作 Human Gold 验收。
