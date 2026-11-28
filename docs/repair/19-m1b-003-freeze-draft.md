# M1-B-003 冻结草案（r2）：双指标 Faithfulness 契约

> 状态：`freeze_draft_pending_human`；**未 accepted、未实现、未激活、未跑 Judge**。
> 版本：`M1-B-003-r2`（2026-11-19 收尾；r1 `approve_with_changes`，r2 补两项契约澄清）。
> 决策人：江晚（D1–D4 原则同意，D1/D2 附约束）。
> 修订记录：r1 `20-m1b-003-revision-record.md`；r2 `21-m1b-003-r2-revision-record.md`。
> 范围：指标定义、状态边界、目标映射、双行生命周期、Run 配置一致性、Item 级聚合、报告标签、验收测试。
> 明确不做：修改运行时代码/Schema/Service/Prompt/API/DB、数据库迁移、创建/激活 v1.2.0、运行 Judge、自动标记 M1-B accepted、启动 M1-C 或 M2 前端。

**本次 r2 只收口契约文本，不改变已批准的 D1–D4 指标定义，不改变目标数值。**

## 1. 冻结输入与证据

| 资产 | SHA256 / 版本 | 状态 |
|---|---|---|
| 旧目标表 `pilot-40-targets-v1.2.0.json` | `34357b34c3d0fc85e78f90eeebb353b25a148926e3a55b19f17cc23b08b2b5eb`（v1.0.1） | 只读、未覆盖 |
| 新目标 revision `pilot-40-targets-v1.2.0-v1.0.2.json` | `3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846` | `freeze_draft_pending_human` |
| 新目标 validation | `pilot-40-targets-v1.2.0-v1.0.2.validation.json` | 20/20 通过 |
| 静态重算输入 `pilot-40-v1.0.0-vs-v1.1.5.json` | `29732088952ad406d296b2c7d8fd5d34f427fd1e703b9818e2bebf80374a5c68` | 已记录 |
| 静态重算脚本 `m1b003_static_recalc.py` | `e21c930b9e9678d4d19c87bd80850db891fbe40135c00de33f313052a97953b4` | 可复现 |
| 静态重算输出 `m1b003-static-recalc.json` | `53787fbb2a434953354bd821b62581e6e56ba5db10751149c236f1e7656437bb` | `static_recalculation_not_judge_run` |
| 静态重算 validation | `m1b003-static-recalc.validation.json` | 13/13 通过 |
| `pilot-40-final-labels.json` | `f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb` | 未变 |
| 语义规范冻结内容 | `92ce3ab` 版本；旧 freeze record `b50830b` 未改写 | 未变 |

**静态重算不是 Judge 运行**：输入是 v1.1.5 已记录的 40 条结果；脚本只做分桶/比值计算。Q17/Q32 的 `expected_v1.2.0` 是预期转换，不是已观测结果，已单独标记。

## 2. D1：指标命名与展示（定义不变，展示约束加强）

| metric key | 展示名称 | 含义 |
|---|---|---|
| `faithfulness` | **Faithfulness（证据覆盖）** | 全部 factual Claims 中得到支持的比例：`S/(S+U+I)` |
| `faithfulness_strict` | **Strict Faithfulness（可判定事实）** | 可判定 Claims 中得到支持的比例：`S/(S+U)` |

展示硬约束：

1. 不能只显示“Faithfulness / Strict Faithfulness”两个名字；必须同时显示分母说明。
2. `faithfulness` 的语义由 `metric_version` + `prompt_sha256` + `schema_version` 共同决定；**key 相同不等于语义相同**。
3. `faithfulness` v1/v2 是历史语义；v1.2.0 的 `faithfulness` = v3 = F_coverage。`faithfulness_strict` 仅 v3 存在。
4. 前端/报告必须显示 `metric_version`、`prompt_sha256`、`schema_version`；不同版本不得混算均值。
5. 目标 badge 只挂在 `faithfulness` v3；`faithfulness_strict` 不挂目标。
6. `unsupported` 的展示名是 **“未被上下文支持”**，不是“矛盾”；不得把 `F_strict` 显示为“无矛盾率”或“幻觉率”。

## 3. 指标定义（D1–D4 不变）

### 3.1 Claim 分桶

| 桶 | 条件 | 说明 |
|---|---|---|
| `S` | `factual_claim` + `support_status=supported` | 上下文明确支持 |
| `U` | `factual_claim` + `support_status=unsupported` | **未被上下文支持**；可能是矛盾、内部冲突、或证据存在但不支持；**不等于 contradiction** |
| `I` | `factual_claim` + `support_status=insufficient_evidence` | 证据不足/不可判定 |
| `N` | `non_factual`（absence/doc_scope/doc_relationship/uncertainty/meta/advice/greeting） | 不进任何分母 |

`invalid(contract_violation)` 不进任何桶，整条 metric 无分数。

**Contradiction 不是独立分桶**：只有 `is_contradictory=true` 或 `contradiction_with` 明确记录时，才可标记 `contradiction_flagged=true`；它不能替代 `U`，也不能从 `U` 反推。

### 3.2 公式

```text
F_strict   = S / (S + U)          if S + U > 0
F_coverage = S / (S + U + I)      if S + U + I > 0
```

- `F_strict >= F_coverage`（两者都 evaluated 时）；
- `I=0` 时两者相等；
- `N` 不进任何分母；
- **`F_strict=1.0` 的正确解释**：在可判定 Claim 中，没有被判为 `unsupported` 的 Claim；它**不表示**“没有矛盾”，也**不表示**全部 factual Claim 都被支持。
- 例：4 supported + 1 insufficient → `F_strict=1.0`、`F_coverage=0.8`；`F_strict=1.0` 不代表回答完整被支持。
- 如果 Judge 把矛盾标成 `unsupported`，`F_strict` 会下降；如果 Judge 未标 `unsupported`，`F_strict` 无法单独证明“无矛盾”。矛盾诊断只能看 `contradiction_flagged` / `is_contradictory` / `contradiction_with`。
- 不得把 `F_strict` 写成“矛盾率”“幻觉率”“无矛盾率”。

### 3.3 状态矩阵

| S | U | I | N | `faithfulness`（F_coverage） | `faithfulness_strict`（F_strict） |
|---|---|---|---|---|---|
| >0 | ≥0 | ≥0 | ≥0 | `evaluated S/(S+U+I)` | `evaluated S/(S+U)` |
| 0 | >0 | 0 | ≥0 | `evaluated 0.0` | `evaluated 0.0` |
| 0 | >0 | >0 | ≥0 | `evaluated 0.0` + `unsupported_count>0` | `evaluated 0.0` |
| 0 | 0 | >0 | ≥0 | `evaluated 0.0` + `all_insufficient=true` | `skipped(no_decidable_claims)` |
| 0 | 0 | 0 | >0 | `skipped(no_scorable_claims)` | `skipped(no_scorable_claims)` |
| 0 | 0 | 0 | 0 | `skipped(no_scorable_claims)` | `skipped(no_scorable_claims)` |
| — | — | — | — | `skipped(context_unavailable)` | `skipped(context_unavailable)` |
| — | — | — | — | `invalid(contract_violation)` | `invalid(contract_violation)` |
| — | — | — | — | `failed(execution)` | `failed(execution)` |

优先级：`context_unavailable` / `invalid` / `failed(execution)` 先于分桶计分。

## 4. D2：两条 result row 的生命周期（已加约束）

### 4.1 创建

1. **一次 Judge 调用**：只对 `faithfulness` 执行 Judge；`faithfulness_strict` 是派生结果，**不额外调用 LLM**。
2. 主结果 `faithfulness` 保存：完整 claims、evidence_refs、validation_errors、raw_output、S/U/I 统计、judge_config（含 prompt SHA/schema/metric version）。
3. 派生结果 `faithfulness_strict` 保存：S/U/I 计数、`F_strict`、`derived_from_result_id`、同一 `judge_config` 摘要；不重复保存完整 claims/evidence/raw_output。
4. 两条结果必须属于同一 `run_id`、同一 `dataset_item_id`、同一 `dataset_version_id`（由 Run 继承）、同一 `metric_version`、同一 `schema_version`、同一 `prompt_sha256`。
5. 先写主结果并 flush，再写派生结果；不允许出现“只有 strict、没有 coverage”的行。
6. 唯一约束见 §4.6；不得用 `(run_id, dataset_item_id, metric_name)` 省略 `metric_version`。

### 4.2 重试（新子 Run，配置不变）

**重试 = 新建子 Run，不是原地重算。**

| 场景 | 行为 |
|---|---|
| coverage 缺失 / failed / 版本过期 | 在子 Run 中重新执行 coverage，再从新 coverage 派生 strict；不得只重算 strict |
| coverage 存在且 current | 可从同一 coverage 重新派生 strict；`derived_from_result_id` 必须指向该行 |
| strict 存在但 coverage 过期 | 删除/忽略旧 strict，按新 coverage 重建；不得保留旧 strict |
| 只缺 strict | 从 current coverage 派生；不得重新调用 Judge |
| 两条版本不一致 | 以 coverage 的 `metric_version`/`prompt_sha256` 为准，重建 strict |
| 需要改 Prompt / Schema / 模型 / 检索配置 | **新建 Run**，不得用 retry；retry 只复制原配置 |

重试规则：

- 子 Run 必须有 `parent_run_id`、`attempt+1`、`retry_scope=failed_only`；
- 子 Run 的 `config_snapshot` 必须与父 Run **逐字段一致**；
- 不能修改 `dataset_version_id`、`execution_mode`、`adapter`、`retrieval_config`、`judge_config`、`item_selection`、`metric_version`、`schema_version`、`prompt_sha256`；
- 只允许对失败/缺失的 item/metric 重跑；不得借 retry 改变评测口径。

### 4.3 删除

- 当前没有 Run 删除接口；未来若增加，必须级联：先删 strict，再删 coverage，或使用 FK/cascade。
- 不允许 orphan strict：coverage 不存在时，strict 不得单独存在。
- 不允许删除 coverage 后保留 strict 引用旧 id。

### 4.4 Item 级聚合（双 Metric Row）

#### 4.4.1 单 metric 状态

每个 metric row 只有四种终态：`evaluated`、`skipped`、`invalid`、`failed`。

#### 4.4.2 Item 级状态（优先级从高到低）

| 优先级 | Item 状态 | 条件 |
|---|---|---|
| 1 | `failed` | 任一 expected metric 为 `failed(execution)` |
| 2 | `invalid` | 无 failed，且任一 expected metric 为 `invalid(contract_violation)` |
| 3 | `evaluated` | 无 failed/invalid，且至少一个 expected metric 为 `evaluated` |
| 4 | `skipped` | 无 failed/invalid/evaluated，全部 expected metric 为 `skipped` |

示例：

| 场景 | coverage | strict | Item 状态 | 附加标记 |
|---|---|---|---|---|
| 正常支持 | evaluated | evaluated | `evaluated` | — |
| 全 insufficient | evaluated 0.0 | skipped(no_decidable) | `evaluated` | `all_insufficient=true`、`skipped_metrics=[faithfulness_strict]` |
| 上下文不可用 | skipped(context) | skipped(context) | `skipped` | `skip_reason=context_unavailable` |
| 全 non_factual | skipped(no_scorable) | skipped(no_scorable) | `skipped` | `skip_reason=no_scorable_claims` |
| 证据契约违约 | invalid | invalid | `invalid` | `invalid_metrics` |
| Judge 执行失败 | failed | failed | `failed` | `failed_metrics` |
| coverage 正常、C 失败 | evaluated | evaluated | `failed` | `failed_metrics=[answer_correctness]` |

**关键**：全 insufficient 的 Item 是 `evaluated`，不是 `skipped`，因为 coverage 有 0 分；strict 的 skipped 只是该 metric 的终态。

**优先级理由**：`failed`（执行侧未完成）优先于 `invalid`（输出违约），两者都优先于 `evaluated`；`evaluated` 优先于全 `skipped`。这样 Item 状态能反映最需要处理的异常，同时不把全 insufficient 误判为 skipped。

#### 4.4.3 计数与比率（按 item，不按 row）

| 字段 | 定义 |
|---|---|
| `total_items` | 选中的 **distinct `dataset_item_id`** 数 |
| `evaluated_items` | Item 状态 = evaluated |
| `invalid_items` | Item 状态 = invalid |
| `failed_items` | Item 状态 = failed |
| `skipped_items` | Item 状态 = skipped |
| `processed_items` | 上述四类之和 |
| `unprocessed_items` | 没有终态 expected metric row 的 item（pending/running/cancelled 未终态） |
| `completed_items` | **等于 `evaluated_items`**；只表示成功评价完成的 Item，不代表所有终态 Item |
| `completion_rate` | `processed_items / total_items` |
| `success_rate` | `evaluated_items / total_items` |
| `evaluation_coverage(metric)` | 该 metric 的 evaluated rows / `total_items` |

**互斥且完整覆盖**：每个 Item 在 `failed / invalid / evaluated / skipped / unprocessed` 中**恰好属于一类**；前四类是已处理终态，`unprocessed` 是未终态 bucket，不属于四类优先级。

守恒关系：

```text
total_items = evaluated_items + invalid_items + failed_items + skipped_items + unprocessed_items
```

- 全量处理完成时 `unprocessed_items = 0`，因此  
  `total_items = evaluated_items + invalid_items + failed_items + skipped_items`；
- 部分完成/取消/超时时 `unprocessed_items > 0`，不得把未处理 item 伪装成 skipped；
- `completed_items = evaluated_items`，不得把 invalid/failed/skipped 计入 completed；
- `completion_rate` 与 `success_rate` 必须分开，避免“完成率 100%”掩盖 invalid/failed/skipped。

规则：

1. `total_items` 不是 result row 数；一个 item 有 coverage+strict（以及 C/R）多行，仍只算 1 个 item。
2. `invalid_items` 与 `failed_items` 独立；不得把 invalid 合并进 failed。
3. 如果现有 API/Schema 没有 `invalid_items`/`unprocessed_items`，M1-C 必须新增或单独暴露；不得用 `failed_items`/`skipped_items` 吞掉。
4. `evaluation_coverage(metric)` 的分子是该 metric 的 evaluated 行数，分母是 `total_items`；不是总行数。
5. 指标行数 ≠ Case 数 ≠ Judge 调用次数；UI 不得把 row count 当 Case count。
6. 实现注意：`expected_metrics` 会增加 `faithfulness_strict`，但 `finalize_run` 必须继续按 `dataset_item_id` 分组；不得用 `len(results)` 作为完成数或 Case 数。

#### 4.4.4 跨 Metric 计数示例（证明 Case 数不翻倍）

3 个 item，只有 F_coverage + F_strict 两条 metric row：

| Item | `faithfulness` | `faithfulness_strict` | Item 状态 | metric rows |
|---|---|---|---|---|
| I1 | evaluated 1.0 | evaluated 1.0 | `evaluated` | 2 |
| I2 | evaluated 0.0（all_insufficient） | skipped(no_decidable) | `evaluated` | 2 |
| I3 | failed | failed | `failed` | 2 |

结果：

- `total_items = 3`（distinct dataset_item_id）；
- `evaluated_items = 2`（I1、I2）；
- `failed_items = 1`（I3）；
- `invalid_items = 0`；`skipped_items = 0`；`unprocessed_items = 0`；
- metric rows = 6；**Case 数 = 3**，不是 6；
- 若再加 C/R，rows 会增加，但 `total_items` 仍是 3。

#### 4.4.5 实现现状风险（只读审计，不改代码）

当前 `finalize_run` 的 `completed_items` 会计入“全部 metric skipped”的 item（条件只有 `all_present and not has_failed`），因此 `completed_items` 实际接近“已处理 item”，不是“evaluated item”。新契约要求：

1. `completed_items` = `evaluated_items`；
2. `skipped_items` 单独计数，不得混入 completed；
3. `invalid_items` 必须独立；当前模型没有该字段，且 `rag_evaluation_results.status` 只有 `evaluated/skipped/failed`，没有 `invalid`；M1-C 必须新增 `invalid` 枚举或 `failed + invalid_reason`，并单独暴露，不得把 invalid 计入 failed 质量；
4. `failed_items` 只统计 `failed(execution)`，不得吞掉 invalid；
5. `completion_rate` 与 `success_rate` 分开，避免“完成率 100%”掩盖大量 skipped/invalid。

如果 M1-C 不改这一点，双 Metric Row 下的完成率/成功率会继续虚高。

### 4.5 失败传播

| coverage 状态 | strict 状态 |
|---|---|
| `invalid(contract_violation)` | 同 `invalid`，同 reason |
| `failed(execution)` | 同 `failed`，同 reason |
| `skipped(context_unavailable)` | 同 skip |
| `skipped(no_scorable_claims)` | 同 skip |
| `evaluated` + all insufficient | `skipped(no_decidable_claims)` |
| `evaluated` + S/U>0 | `evaluated` |

**禁止**：coverage invalid/failed 时 strict 仍 evaluated；coverage skip 时 strict 有分数。

### 4.6 Run 配置不可变与 Result Row 唯一约束复核

#### 4.6.1 Run 配置不可变

Run 创建后，以下字段视为不可变快照（逻辑字段，可位于 `judge_config` / `config_snapshot`）：

- `dataset_version_id`、`dataset_checksum`
- `execution_mode`、`adapter`
- `retrieval_config`、`judge_config`、`config_snapshot`
- `item_selection`
- `metric_version`、`schema_version`、`prompt_sha256`

任何一项变化都必须**新建 Run**，不得在原 Run 上修改。重试只复制快照，不改变快照。

#### 4.6.2 Result Row 唯一约束复核

现有唯一键 `(run_id, dataset_item_id, metric_name, metric_version)` **保留，不新增列**。

理由：

1. `run_id` 隔离父/子 Run 与不同实验；
2. `dataset_item_id` 隔离 item；
3. `metric_name` 区分 `faithfulness` 与 `faithfulness_strict`（以及 C/R/检索指标）；
4. `metric_version` 防止同一 Run 内出现 v2/v3 混写；虽然 Run 不可变，唯一键保留版本列作为防御；
5. Run 配置不可变，`prompt_sha256`/`schema_version` 是 Run 级字段，不需要重复进唯一键；
6. `ON CONFLICT DO NOTHING` 仍可安全用于幂等重投递。

服务层不变量（必须实现）：

- 写入 result row 前，校验其 `metric_version`/`schema_version`/`prompt_sha256` 与 Run 快照一致；
- 不一致 → 拒绝写入或标 `invalid(contract_violation)`，不得以“新版本”名义插入同一 Run；
- 如果未来允许 Run 配置可变，必须新增 `config_fingerprint` 到 row 和唯一键；v1.2.0 不这样做。

#### 4.6.3 实现现状风险（只读审计，不改代码）

当前 `retry_run` 会重新调用 `build_judge_config(judge_metrics)`，可能取到**当前默认 Prompt 版本**，而不是父 Run 的 `judge_config` 快照。`build_judge_config` 的 docstring 甚至明确写“重试 Run 必须用当前指纹，不能照抄父 Run”；这与本 r1 的“retry 配置逐字段一致”直接冲突。

M1-C 必须改为：

1. 直接复制父 Run 的 `judge_config` / `config_snapshot` / `retrieval_config` / `item_selection`；
2. 校验父配置的 `metric_version` / `schema_version` / `prompt_sha256` 仍可用；
3. 若 Prompt/Schema 已变化，**拒绝 retry**，提示“新建 Run”，不得静默换版本；
4. 子 Run 的 result row 版本必须与父快照一致，聚合不得混算；
5. 重试候选判断用父快照版本，不能用当前 `build_judge_config` 的版本。

### 4.7 invalid 持久化契约（两种实现，同一语义）

`invalid` 与 `failed(execution)` 是两类不同问题：

| 类别 | 含义 | 进入均值 | Item 计数 |
|---|---|---|---|
| `invalid` | Judge 调用成功，但输出违反结构/证据契约 | 否 | `invalid_items` |
| `failed(execution)` | Judge/服务调用失败，重试耗尽 | 否 | `failed_items` |

**invalid 不得被解释为模型执行失败。**

实现选择（M1-C 定）：

| 方案 | row 持久化 | 聚合识别 | 展示 |
|---|---|---|---|
| **A（优先）** | 独立 `invalid` 状态：`status=invalid` + `invalid_reason` | 直接归类 invalid | 输出契约无效 |
| B | `status=failed` + `invalid_reason`（结构化 code） | 聚合层看到 `invalid_reason` 必须归类 invalid，不得算 failed | 输出契约无效 |

共同语义：

1. `invalid_reason` 只由契约校验器写入，必须是结构化 code，例如 `missing_subtype`、`illegal_subtype`、`type_mismatch`、`supported_without_evidence`、`evidence_context_not_found`、`evidence_not_verbatim`、`answer_reference`、`conflict_single_sided`。
2. 如果采用 B，`status=failed` 只是持久化细节；聚合/API/报告必须按 `invalid_reason` 重新归类为 invalid。
3. `invalid_items` 与 `failed_items` 必须独立统计；item 级按 §4.4.2 优先级，二者互斥。
4. 同一 item 若同时有 execution failed metric 和 invalid metric，item 状态为 `failed`；但 metric 级仍要记录 invalid 行，不能隐藏。
5. invalid row 不进入指标均值；invalid_items 不计入 `completed_items`、`success_rate`。
6. Metric 级计数必须按以下规则，避免 B 方案把 invalid 算进 failed：

```text
invalid_results = (status = invalid) OR (status = failed AND invalid_reason IS NOT NULL)
failed_results  = (status = failed) AND (invalid_reason IS NULL)
```

7. execution failure 不得写 `invalid_reason`；若两者同时出现，视为数据异常，聚合按 `invalid_contract` 处理并记录 anomaly，不得算 `failed(execution)`。
8. API/前端必须把 invalid 显示为“输出契约无效”，不得显示为“执行失败”。

## 5. 报告标签与全 insufficient 语义

### 5.1 全 insufficient（D3 不变）

| 指标 | 结果 | 附加字段 |
|---|---|---|
| `faithfulness` | `evaluated 0.0` | `all_insufficient=true`、`insufficient_ratio=1.0`、`unsupported_count=0`、`report_label=evidence_undecidable` |
| `faithfulness_strict` | `skipped(no_decidable_claims)` | `skipped_reason=no_decidable_claims` |

报告文案：

> 本题全部 factual Claim 为 `insufficient_evidence`，`F_coverage=0.0` 表示没有一条事实断言被上下文支持，属于证据不可判定；不是发现了幻觉。

### 5.2 统一报告标签（主标签 + 标志）

主标签按优先级互斥；标志可共存。

| 优先级 | 主标签 | 条件 | 展示文案 |
|---|---|---|---|
| 1 | `execution_failed` | 任一 expected metric `failed(execution)` | 执行失败 |
| 2 | `invalid_contract` | 无 failed，任一 metric `invalid(contract_violation)` | 输出契约无效 |
| 3 | `context_unavailable` | 无 failed/invalid，上下文不可用 | 上下文不可用 |
| 4 | `no_scorable_claims` | 无 failed/invalid，无 factual Claim | 无可评价事实断言 |
| 5 | `evidence_undecidable` | 无 failed/invalid，`S=0,U=0,I>0` | 证据不可判定 |
| 6 | `contains_unsupported_claims` | 无 failed/invalid，`U>0` | 含未被上下文支持的断言 |
| 7 | `contains_insufficient_claims` | 无 failed/invalid，`U=0,I>0,S>0` | 含证据不足断言 |
| 8 | `supported` | 无 failed/invalid，`U=0,I=0,S>0` | 可判定事实均被支持 |

标志：

| 标志 | 条件 | 用途 |
|---|---|---|
| `has_unsupported` | `U>0` | 存在未被支持断言 |
| `has_insufficient` | `I>0` | 存在证据不足断言 |
| `all_insufficient` | `S=0,U=0,I>0` | 全部证据不可判定 |
| `all_unsupported` | `S=0,I=0,U>0` | 全部未被支持 |
| `contradiction_flagged` | `is_contradictory=true` 或有明确 `contradiction_with` | 仅标记矛盾，不改变主标签 |
| `strict_skipped` | coverage evaluated、strict skipped | 全 insufficient 的派生状态 |

**标签与 Item 状态分开**：`evaluated/skipped/invalid/failed` 是聚合状态，用于完成率/覆盖率；主标签是报告解释，不参与完成率计算。

**标签准确性约束**：

1. **禁止**使用 `contradiction_or_mixed`；统一用 `contains_unsupported_claims`。
2. **禁止**把 `unsupported` 单独当主标签；它不区分“矛盾”“内部冲突”“证据存在但不支持”。
3. `contains_unsupported_claims` **不声明**“存在矛盾”；只有 `contradiction_flagged=true` 才可显示“矛盾”。
4. 存在 `unsupported` 时，即使 `F_coverage=0`，也不得标 `evidence_undecidable`。
5. `all_insufficient=true` 必须满足 `unsupported_count=0` 且 `insufficient_ratio=1.0`。
6. `contains_insufficient_claims` 不是失败标签；它是覆盖率 caveat，报告仍需按目标判断是否 miss。

## 6. D4：Strict 只观察（不变）

v1.2.0 阶段只记录、不设硬目标：

| 观察字段 | 定义 |
|---|---|
| `faithfulness_strict` | `S/(S+U)` |
| `unsupported_count` | `U` |
| `unsupported_ratio` | `U/(S+U+I)` |
| `insufficient_ratio` | `I/(S+U+I)` |
| `strict_gap` | `F_strict - F_coverage`（≥0） |

- 不把 `faithfulness_strict` 写成 PASS/FAIL；
- 不设 `F_strict` 目标；
- 当前样本 29/30 有分数案例为 1.0，区分度有限；等人工确认数据增加后再讨论目标；
- `strict_gap` 只作诊断，不参与目标通过率；
- 矛盾只能来自 `is_contradictory` / `contradiction_with` 的明确标记，不得从 `unsupported_count` 反推。

## 7. 冻结前检查点

### 7.1 静态重算可复现性

| 项 | 值 |
|---|---|
| 类型 | `static_recalculation_not_judge_run` |
| 输入 | `pilot-40-v1.0.0-vs-v1.1.5.json`，SHA `29732088…` |
| 脚本 | `m1b003_static_recalc.py`，SHA `e21c930b…` |
| 输出 | `m1b003-static-recalc.json`，SHA `53787fbb…` |
| Validation | `m1b003-static-recalc.validation.json`，13/13 通过 |
| 行数 | 40（32 observed + 8 not_run） |
| 复跑一致性 | 连续两次运行输出 SHA 相同 |
| 静态结果 | `F_coverage` 30/30 有分数案例与旧 F 一致（6 位小数）；Q14/Q29 skip |
| 预期值隔离 | Q17/Q32 的 `expected_v1.2.0` 单独字段，`is_expected=true`、`not_observed=true` |

**Q32 特别说明**：`expected_v1.2.0` 使用“cl1 转 uncertainty”的预期标签，不是 v1.1.5 观测值；不得把 1.0 写成“已实测”。Q17 同理（cl5 转 policy_relationship factual/insufficient）。

### 7.2 双行生命周期

已写入 §4。关键不变量：

- strict 不能脱离 coverage 存在；
- strict 不重复调用 Judge；
- coverage 版本变化 → strict 重建；
- item 计数不因两条 row 翻倍；
- coverage invalid/failed → strict 同失败，不产生分数；
- retry 是子 Run，配置快照逐字段一致；
- Prompt/Schema/模型/检索配置变化 → 新 Run，不是 retry。

### 7.3 Coverage 术语区分

| 术语 | 定义 | 显示名 | 不得写成 |
|---|---|---|---|
| `F_coverage` | `S/(S+U+I)`，证据覆盖 | **Faithfulness（证据覆盖）** | “Coverage” / “评测覆盖率” |
| `aggregate.metrics[].coverage` | `evaluated_rows / total_items`，评测覆盖率 | **评测覆盖率** | “F_coverage” / “证据覆盖率” |
| `insufficient_ratio` | `I/(S+U+I)`，无法判定的 Claim 比例 | **证据不足比例** | “覆盖率” / “错误率” |
| `completion_rate` | `processed_items / total_items`，流程完成率 | **流程完成率** | “评测覆盖率” / “成功率” |
| `success_rate` | `evaluated_items / total_items`，成功 item 比例 | **成功 Item 比例** | “完成率” |

### 7.4 统一展示术语（唯一来源）

| 类别 | 内部值 | 展示文案 | 禁用写法 |
|---|---|---|---|
| Claim 状态 | `supported` | 已被上下文支持 | “正确” / “无幻觉” |
| Claim 状态 | `unsupported` | **未被上下文支持** | “矛盾” / “错误” |
| Claim 状态 | `insufficient_evidence` | 证据不足 / 不可判定 | “不支持” / “错误” |
| 矛盾标记 | `contradiction_flagged` | 矛盾（仅在明确标记时） | 由 `unsupported` 反推“矛盾” |
| 指标 | `faithfulness` | **Faithfulness（证据覆盖）** | “Faithfulness” 不带分母说明 |
| 指标 | `faithfulness_strict` | **Strict Faithfulness（可判定事实）** | “无矛盾率” / “幻觉率” |
| 主标签 | `evidence_undecidable` | 证据不可判定 | “幻觉” / “编造” |
| 主标签 | `contains_unsupported_claims` | 含未被上下文支持的断言 | `contradiction_or_mixed` / `unsupported` |
| 主标签 | `contains_insufficient_claims` | 含证据不足断言 | “失败” / “不支持” |
| 主标签 | `no_scorable_claims` | 无可评价事实断言 | “跳过” 无原因 |
| 主标签 | `context_unavailable` | 上下文不可用 | “0 分” |
| 主标签 | `invalid_contract` | 输出契约无效 | “失败” 混用 |
| 主标签 | `execution_failed` | 执行失败 | “无效” 混用 |
| 覆盖率 | `aggregate.metrics[].coverage` | 评测覆盖率 | “F_coverage” |
| 比率 | `insufficient_ratio` | 证据不足比例 | “覆盖率” |

**统一规则**：API、前端、报告只能使用本表展示文案；`unsupported` 不得显示为“矛盾”，`contains_unsupported_claims` 不得显示为“矛盾/混合”。

## 8. 目标映射与 revision（数值不变）

新目标 revision：`pilot-40-targets-v1.2.0-v1.0.2.json`（SHA `3ee15dfc…`，20/20 validation）。

| 字段 | 值 |
|---|---|
| `f_target_metric` | `faithfulness` |
| `f_target_denominator` | `S+U+I` |
| `f_target_denominator_long` | `supported_plus_unsupported_plus_insufficient` |
| `f_target_display` | `Faithfulness（证据覆盖）` |
| `f_strict_metric` | `faithfulness_strict` |
| `f_strict_role` | `diagnostic` |
| `f_strict_target` | `null` |
| `target_values_changed` | `false` |
| `supersedes_sha256` | `34357b34…` |
| `runtime_active` | `false` |
| `not_for_run` | `true` |

- 40 条目标数值与 v1.0.1 完全一致；
- 旧文件与旧 SHA 未覆盖；
- 该 revision 仍是 `freeze_draft_pending_human`，不是 accepted；
- 目标表 revision 的人工审核与 M1-B-003-r2 一起进行。

## 9. 验收测试（冻结后实现，不在本轮）

### 9.1 Service unit（11 条）

| # | S | U | I | N | F_strict | F_coverage |
|---|---|---|---|---|---|---|
| 1 | 5 | 0 | 0 | 0 | 1.0 | 1.0 |
| 2 | 3 | 1 | 0 | 0 | 0.75 | 0.75 |
| 3 | 3 | 0 | 2 | 0 | 1.0 | 0.6 |
| 4 | 0 | 1 | 0 | 0 | 0.0 | 0.0 |
| 5 | 0 | 0 | 3 | 0 | `skipped(no_decidable_claims)` | `evaluated 0.0` + `all_insufficient` |
| 6 | 0 | 0 | 0 | 3 | `skipped(no_scorable_claims)` | 同左 |
| 7 | 0 | 0 | 0 | 0 | `skipped(no_scorable_claims)` | 同左 |
| 8 | — | — | — | — | `skipped(context_unavailable)` | 同左 |
| 9 | — | — | — | — | `invalid` | 同左 |
| 10 | 3 | 1 | 2 | 0 | 0.75 | 0.5 |
| 11 | 3 | 0 | 2 | 0 | 1.0 | 0.6 |

### 9.2 目标回归（静态 claim 集，不跑 Judge）

| Case | 目标 | F_coverage | F_strict |
|---|---|---|---|
| Q11 | 0.6–0.9 | 0.833333 | 1.0 |
| Q17 | 0.7–0.9 | 0.8（预期标签） | 1.0 |
| Q21 | 0.6–0.7 | 0.6 | 1.0 |
| Q23 | 0.4–0.5 | 0.5 | 0.75 |
| Q32 | 0.9–1.0 | 1.0（预期标签） | 1.0 |

### 9.3 生命周期与聚合测试

1. 创建：1 次 Judge → 2 行；strict `derived_from_result_id` 指向 coverage。
2. 重试：新子 Run；配置快照逐字段一致；只重跑失败/缺失 item。
3. 只缺 strict：从 current coverage 派生，不再调 Judge。
4. coverage invalid/failed：strict 不 evaluated。
5. 全 insufficient：coverage evaluated 0、strict skipped；**Item 状态 = evaluated**，`skipped_metrics=[faithfulness_strict]`。
6. 全 non_factual / context_unavailable：Item 状态 = skipped。
7. 40 items、双 F 行 + C/R：`total_items=40`，不是 80/160 行。
8. coverage/ strict 版本不一致：以 coverage 版本为准重建 strict。
9. Prompt/Schema/模型/检索配置变化：新建 Run，不是 retry。
10. 唯一键冲突：同一 `(run_id,item,metric,version)` 重投递幂等，不产生重复行。
11. invalid 持久化 A（status=invalid）与 B（status=failed + invalid_reason）都归类为 `invalid_items`，不得进入 `failed_items` 或均值。
12. 部分完成/取消/超时：`unprocessed_items > 0`，四类终态 + unprocessed = total_items；不得把未处理 item 当 skipped。
13. 3 个 item、双 F 行：6 条 metric rows，但 `total_items=3`、Case 数=3。

### 9.4 不变量

- `F_strict >= F_coverage`（两者 evaluated）；
- `F_strict=1.0` 只表示“无 unsupported”，不表示“无矛盾”，不表示“全部 factual 被支持”；
- `all_insufficient=true` ⇒ `unsupported_count=0` 且 `insufficient_ratio=1.0`；
- `unsupported_count>0` ⇒ 主标签必须是 `contains_unsupported_claims`，不得 `evidence_undecidable`；
- `invalid`/`failed` 不进均值；
- `skipped` 不进均值；
- `total_items = evaluated_items + invalid_items + failed_items + skipped_items + unprocessed_items`；
- 全量处理完成时 `unprocessed_items=0`，四类终态之和 = `total_items`；
- `completed_items = evaluated_items`，不代表所有终态 Item；
- `invalid_items` 与 `failed_items` 独立；
- 同一 `(run_id,item,metric,metric_version)` 只有一行；
- result row 的 `metric_version`/`schema_version`/`prompt_sha256` 必须等于 Run 快照。

### 9.5 标签/展示测试

1. `U>0` 且 `is_contradictory=false`：主标签 `contains_unsupported_claims`，不得出现“矛盾”文案。
2. `U>0` 且 `is_contradictory=true`：主标签仍 `contains_unsupported_claims`，附加 `contradiction_flagged=true`；可显示“检测到矛盾标记”，不得把主标签改成“矛盾”。
3. `S=0,U=0,I>0`：主标签 `evidence_undecidable`；文案“证据不可判定”，不得“幻觉/编造”。
4. `S=0,U>0,I=0`：主标签 `contains_unsupported_claims` + `all_unsupported=true`；不得 `evidence_undecidable`。
5. `S>0,U=0,I>0`：主标签 `contains_insufficient_claims`；不是失败标签。
6. `F_strict=1.0` 且 `I>0`：报告必须同时显示 `F_coverage` 和 `insufficient_ratio`，不得写“无矛盾”或“全部支持”。

## 10. 冻结范围与明确不做

**本轮允许**：

- 本冻结草案 r2；
- 修订记录；
- 静态 validation 与 SHA 校验；
- 目标 metadata revision 的引用（不修改目标文件）。

**本轮不做**：

- 修改 `app/schemas` / `app/services` / `app/agents` / Prompt / API / DB；
- 数据库迁移；
- 创建/激活 v1.2.0；
- 运行 Judge（单案例/10/40 都不跑）；
- 把 M1-B 自动标 `accepted`；
- 启动 M1-C 或 M2 前端。

## 11. 修订摘要

### 11.1 r1（4 项关闭 + 术语统一）

| # | 问题 | r1 处理 | 证明位置 |
|---|---|---|---|
| 1 | `F_strict=1.0` 被解释为“无矛盾” | 改成“无 unsupported”；明确 unsupported ≠ contradiction；矛盾只看 `contradiction_flagged` | §3.1、§3.2、§7.4、§9.4 |
| 2 | `contradiction_or_mixed` 等标签不准确 | 统一主标签 `contains_unsupported_claims`；删除 `contradiction_or_mixed`/`unsupported` 主标签 | §5.2、§7.4 |
| 3 | Run 配置/重试/唯一约束不清 | 新增 Run 不可变、retry 子 Run 配置一致、Prompt/Schema 变化新建 Run；复核唯一键 | §4.2、§4.6、§9.3 |
| 4 | 双 Metric Row 的 Item 聚合不清 | 新增 Item 级状态优先级、计数、`invalid_items`、Case 数不翻倍 | §4.4、§9.3、§9.4 |
| 5 | 标签/术语不统一 | 新增唯一展示术语表；Coverage 三分 | §7.3、§7.4 |

### 11.2 r2（2 项收尾）

| # | 问题 | r2 处理 | 证明位置 |
|---|---|---|---|
| 1 | Item 级计数语义不完整 | 明确 `completed_items=evaluated_items`、`total_items` 按 distinct item、四类终态 + `unprocessed` 守恒、互斥完整覆盖、跨 Metric 示例 | §4.4.3、§4.4.4、§9.3、§9.4 |
| 2 | invalid 持久化契约不清 | 保留独立 invalid / `failed + invalid_reason` 两种实现；共同语义：归 invalid、与 failed 独立、不进均值、不得解释为执行失败 | §4.7、§9.3 |

## 12. 待人工审核

1. 是否接受本 r2 冻结草案与目标 revision v1.0.2；
2. 是否接受 `contains_unsupported_claims` 主标签与标志体系；
3. 是否接受 Item 级 `evaluated/skipped/invalid/failed` 优先级与 `invalid_items` 独立计数；
4. 是否接受 Run 不可变 + retry 子 Run + 唯一键保留的结论；
5. 是否接受 M1-C 必须修改 `retry_run` / `finalize_run` / `status` 枚举的实现义务；
6. 通过后才决定 M1-B 是否 `accepted`、M1-C 是否启动。

**签字：Agent（代拟）**
**状态：`freeze_draft_pending_human`**
**下一步：人工最终审核 → M1-B accepted 决策 → M1-C 启动决策**
