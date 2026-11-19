# M1-B-003 修订记录（r1）

> 修订 ID：`M1-B-003-r1`
> 日期：2026-11-19
> 历史记录：本文件记录 r1 时点；`19-m1b-003-freeze-draft.md` 已由 r2 取代，当前 SHA 见 `21-m1b-003-r2-revision-record.md`。
> 触发：人工审核 `approve_with_changes`
> 范围：**只修订冻结草案文本**；不进入实现，不修改运行时代码/Schema/Service/Prompt/API/DB，不运行 Judge，不创建/激活 v1.2.0，不标记 M1-B accepted，不启动 M1-C/M2 前端。
> 修订后草案：`19-m1b-003-freeze-draft.md`
> 新 SHA256：`1abfc22160bfca63b03614cec2d336bcb19956d310bfdbd5d91175af60d9c87e`
> 静态 Validation：`19-m1b-003-freeze-draft.validation.json`（21/21 通过）

## 1. 修订摘要（4 项问题 + 术语统一）

| # | 审核问题 | r1 处理 | 证明位置 |
|---|---|---|---|
| 1 | `F_strict=1.0` 被解释为“无矛盾” | 改为“可判定 Claim 中无 `unsupported`”；明确 `unsupported` ≠ contradiction；矛盾只看 `contradiction_flagged` / `is_contradictory` / `contradiction_with` | 草案 §3.1、§3.2、§7.4、§9.4 |
| 2 | `contradiction_or_mixed` 等标签不准确 | 主标签统一为 `contains_unsupported_claims`；新增 `contains_insufficient_claims`；删除 `contradiction_or_mixed` / `unsupported` 作为主标签 | 草案 §5.2、§7.4 |
| 3 | Run 配置/重试/唯一约束不清 | 新增 Run 不可变、retry 子 Run 配置逐字段一致、Prompt/Schema/模型/检索变化必须新建 Run；复核唯一键保留 | 草案 §4.2、§4.6、§9.3 |
| 4 | 双 Metric Row 的 Item 聚合不清 | 新增 Item 级 `evaluated/skipped/invalid/failed` 优先级、计数、`invalid_items`、Case 数不翻倍 | 草案 §4.4、§9.3、§9.4 |
| 5 | 标签/术语不统一 | 新增唯一展示术语表；Coverage 三分（F_coverage / 评测覆盖率 / 证据不足比例） | 草案 §7.3、§7.4 |

## 2. 逐项关闭证明

### 2.1 问题 1：F_strict=1.0 的解释

**修订前**：写成“可判定 Claim 中没有矛盾”。

**修订后**：

- `U = unsupported` 表示“未被上下文支持”，可能是矛盾、内部冲突、或证据存在但不支持；**不等于 contradiction**。
- `F_strict=1.0` = “可判定 Claim 中没有被判为 `unsupported` 的 Claim”；不表示“没有矛盾”，也不表示“全部 factual Claim 被支持”。
- 矛盾诊断只看 `contradiction_flagged` / `is_contradictory` / `contradiction_with`；不得从 `U` 反推矛盾。
- 例：4 supported + 1 insufficient → `F_strict=1.0`、`F_coverage=0.8`。

**证明**：草案 §3.1、§3.2、§7.4、§9.4；静态 validation `unsupported_not_contradiction`、`fstrict_explanation` 均为 true。

### 2.2 问题 2：报告标签准确性

**修订前**：`contradiction_or_mixed`、`unsupported` 作为主标签。

**修订后**：

| 情况 | 主标签 |
|---|---|
| `U>0` | `contains_unsupported_claims` |
| `U=0,I>0,S>0` | `contains_insufficient_claims` |
| `S=0,U=0,I>0` | `evidence_undecidable` |
| `S=0,U>0,I=0` | `contains_unsupported_claims` + `all_unsupported=true` |
| `S=0,U>0,I>0` | `contains_unsupported_claims` + `has_insufficient=true` |

- `contains_unsupported_claims` **不声明**“存在矛盾”；
- 只有 `contradiction_flagged=true` 才可显示“矛盾”；
- `unsupported` 展示为“未被上下文支持”，不得显示为“矛盾”。

**证明**：草案 §5.2、§7.4；静态 validation `no_active_contradiction_or_mixed`、`contains_unsupported_claims_label` 均为 true。

### 2.3 问题 3：Run 配置、重试、唯一约束

**修订后**：

1. Run 创建后，`dataset_version_id`、`execution_mode`、`adapter`、`retrieval_config`、`judge_config`、`config_snapshot`、`item_selection`、`metric_version`、`schema_version`、`prompt_sha256` 不可变。
2. 重试 = 新建子 Run；`parent_run_id`、`attempt+1`、`retry_scope=failed_only`；配置快照逐字段一致；只重跑失败/缺失 item。
3. Prompt/Schema/模型/检索配置变化 → **新建 Run**，不得 retry。
4. 唯一键 `(run_id, dataset_item_id, metric_name, metric_version)` 保留，不新增列；前提是 Run 配置不可变。
5. 服务层校验每行版本与 Run 快照一致；不一致拒绝写入或标 invalid。

**只读审计发现（未改代码）**：

- 当前 `retry_run` 重新调用 `build_judge_config`，可能取当前默认 Prompt 版本；`build_judge_config` docstring 明确写“重试必须用当前指纹”。这与 r1 契约冲突。
- M1-C 必须改为复制父 Run 快照；父版本不可用时拒绝 retry，提示新建 Run。

**证明**：草案 §4.2、§4.6、§9.3；静态 validation `run_config_immutable`、`retry_is_child_run`、`unique_key_reviewed` 均为 true。

### 2.4 问题 4：Item 级聚合

**修订后**：

| Item 状态 | 条件 |
|---|---|
| `failed` | 任一 expected metric `failed(execution)` |
| `invalid` | 无 failed，任一 metric `invalid(contract_violation)` |
| `evaluated` | 无 failed/invalid，至少一个 metric evaluated |
| `skipped` | 无 failed/invalid/evaluated，全部 metric skipped |

- 全 insufficient：coverage evaluated 0 + strict skipped → **Item 状态 = evaluated**，`skipped_metrics=[faithfulness_strict]`。
- `evaluated_items + skipped_items + invalid_items + failed_items = total_items`。
- `completed_items` = `evaluated_items`；`invalid_items` 独立，不得并入 failed。
- `completion_rate` 与 `success_rate` 分开。
- 指标行数 ≠ Case 数；40 items 不会因为双 F 行变成 80 cases。

**只读审计发现（未改代码）**：

- 当前 `finalize_run` 的 `completed_items` 会计入全 skipped item；M1-C 必须改为 evaluated_items，否则完成率虚高。
- 当前 `rag_evaluation_results.status` 只有 `evaluated/skipped/failed`，没有 `invalid`；M1-C 必须新增枚举或 `failed + invalid_reason`，并单独计数。

**证明**：草案 §4.4、§9.3、§9.4；静态 validation `item_level_status`、`case_count_not_row_count` 均为 true。

### 2.5 问题 5：统一标签/术语

**修订后**：草案 §7.4 是唯一展示术语表，覆盖：

- Claim 状态：supported / unsupported / insufficient_evidence；
- 矛盾标记：contradiction_flagged（仅明确标记时）；
- 指标：Faithfulness（证据覆盖）/ Strict Faithfulness（可判定事实）；
- 主标签：execution_failed / invalid_contract / context_unavailable / no_scorable_claims / evidence_undecidable / contains_unsupported_claims / contains_insufficient_claims / supported；
- Coverage 三分：F_coverage / 评测覆盖率 / 证据不足比例；
- 完成率/成功率：流程完成率 / 成功 Item 比例。

**证明**：草案 §7.3、§7.4；静态 validation `unified_terminology` 为 true。

## 3. 不变约束复核

| 约束 | 结果 |
|---|---|
| D1–D4 指标定义 | 未变：`F_strict=S/(S+U)`、`F_coverage=S/(S+U+I)`、展示名、D3/D4 口径均保留 |
| 目标数值 | 未变；目标 revision 仍为 v1.0.2，40 条数值与 v1.0.1 一致 |
| 旧目标文件/SHA | 未覆盖；`34357b34…` 仍只读 |
| Human Gold / provisional | 未修改 |
| 运行时代码/Schema/Service/Prompt/API/DB | 未修改 |
| Judge | 未运行 |
| v1.2.0 | 未创建、未激活 |
| M1-B accepted | 未标记 |
| M1-C / M2 前端 | 未启动 |

静态 validation `no_runtime_changes`、`old_target_sha_unchanged`、`new_target_sha_unchanged`、`final_labels_sha_unchanged` 均为 true。

## 4. 变更文件

| 文件 | 变更 |
|---|---|
| `19-m1b-003-freeze-draft.md` | r1 修订：4 项问题 + 术语统一 |
| `19-m1b-003-freeze-draft.sha256` | 新 SHA |
| `19-m1b-003-freeze-draft.validation.json` | 21/21 静态 validation |
| `20-m1b-003-revision-record.md` | 本修订记录 |
| `README.md` | 状态更新（r1 待审核） |
| `06-repair-progress.md` | 进度记录 |

未修改：目标 revision、静态重算 JSON、Human Gold、provisional、backend、frontend、nginx、ops。

## 5. M1-C 实现义务（不在本轮）

r1 只定义契约，以下由 M1-C 实现，当前未改：

1. `retry_run` 改为复制父 Run 快照；Prompt/Schema 变化拒绝 retry。
2. `finalize_run` 的 `completed_items` 改为 evaluated_items；新增 `invalid_items`。
3. `rag_evaluation_results.status` 增加 `invalid` 或 `failed + invalid_reason`；聚合/报告分开。
4. 双指标 `expected_metrics`、`derived_from_result_id`、item 级聚合。
5. 标签/术语 API/前端映射。

## 6. 剩余未决问题

1. 是否接受 r1 冻结草案与目标 revision v1.0.2；
2. 是否接受 `contains_unsupported_claims` 主标签与 flag 体系；
3. 是否接受 Item 级 `evaluated/skipped/invalid/failed` 优先级与 `invalid_items` 独立计数；
4. 是否接受 Run 不可变 + retry 子 Run + 唯一键保留的结论；
5. 是否接受 M1-C 必须修改 `retry_run` / `finalize_run` / `status` 枚举的实现义务；
6. 通过后才决定 M1-B 是否 `accepted`、M1-C 是否启动。

**状态：`freeze_draft_pending_human`**
**签字：Agent（代拟）**
**下一步：人工最终审核 → M1-B accepted 决策 → M1-C 启动决策**
