# M1-B-003 r2 修订记录：最终契约收尾

> 修订 ID：`M1-B-003-r2`
> 日期：2026-11-19
> 触发：r1 最终契约收尾；两项澄清（Item 级计数语义、invalid 持久化契约）。
> 范围：**只修订冻结草案和验证材料**；不修改运行时代码/Schema/Service/Prompt/API/DB，不运行 Judge，不创建/激活 v1.2.0，不标记 M1-B accepted，不启动 M1-C/M2 前端。
> 修订后草案：`19-m1b-003-freeze-draft.md`
> 新 SHA256：`d2d2e0decd84fee57b68acf90e862189c09acf6ce608d92578f6346f7cc5183d`
> 静态 Validation：`19-m1b-003-freeze-draft.validation.json`（33/33 通过）

## 1. 修订摘要

| # | 问题 | r2 处理 | 证明位置 |
|---|---|---|---|
| 1 | Item 级计数语义不完整 | 明确 `completed_items=evaluated_items`、`total_items` 按 distinct item、四类终态 + `unprocessed` 守恒、互斥完整覆盖、跨 Metric 示例 | 草案 §4.4.3、§4.4.4、§9.3、§9.4 |
| 2 | invalid 持久化契约不清 | 保留独立 invalid / `failed + invalid_reason` 两种实现；共同语义：归 invalid、与 failed 独立、不进均值、不得解释为执行失败 | 草案 §4.7、§9.3 |

## 2. 任务一：Item 级计数语义

### 2.1 修订前

- `completed_items` 语义不够明确，容易被理解为“所有终态 Item”。
- 四类状态与 `total_items` 的守恒关系只在“全部终态”时成立，未说明部分完成/取消/超时。
- 缺少跨 Metric 的 Case 数示例。

### 2.2 修订后

- `completed_items = evaluated_items`，只表示成功评价完成的 Item，不代表所有终态 Item。
- `total_items` 按 **distinct `dataset_item_id`** 统计。
- Item 状态互斥且完整覆盖：`failed / invalid / evaluated / skipped / unprocessed`，每个 Item 恰好属于一类。
- 守恒关系：

```text
total_items = evaluated_items + invalid_items + failed_items + skipped_items + unprocessed_items
```

- 全量处理完成时 `unprocessed_items=0`，四类终态之和 = `total_items`。
- 部分完成/取消/超时时 `unprocessed_items>0`，不得把未处理 item 当 skipped。
- `completion_rate = processed_items / total_items`；`success_rate = evaluated_items / total_items`。
- 跨 Metric 示例：3 个 item、6 条 metric rows、Case 数 = 3；I2 为 all-insufficient 但 Item 状态 = evaluated。

### 2.3 证明

草案 §4.4.3（计数表、守恒、规则）、§4.4.4（3 items / 6 rows / 3 cases）、§9.3 第 5/6/7/12/13 条、§9.4 守恒不变量。

## 3. 任务二：invalid 持久化契约

### 3.1 修订前

- 只写“新增枚举或 `failed + invalid_reason`”，未说明两种实现的共同语义。
- `invalid` 与 `failed(execution)` 的边界不够明确。

### 3.2 修订后

两种实现保留：

| 方案 | row 持久化 | 聚合识别 | 展示 |
|---|---|---|---|
| A（优先） | 独立 `status=invalid` + `invalid_reason` | 直接归类 invalid | 输出契约无效 |
| B | `status=failed` + `invalid_reason`（结构化 code） | 聚合层看到 `invalid_reason` 必须归类 invalid，不得算 failed | 输出契约无效 |

共同语义：

1. `invalid` 是 Judge 调用成功但输出违反结构/证据契约；`failed(execution)` 是调用失败/重试耗尽。
2. `invalid_reason` 必须是结构化 code，不是自由文本。
3. `invalid_items` 与 `failed_items` 独立统计；item 级互斥。
4. 同一 item 若同时有 execution failed 和 invalid metric，item 状态 = failed；metric 级仍保留 invalid 行，不隐藏。
5. invalid row 不进入指标均值；invalid_items 不计入 completed/success。
6. execution failure 不得写 `invalid_reason`；两者同时出现视为数据异常，按 invalid_contract 记录，不得算 failed(execution)。
7. UI 必须显示“输出契约无效”，不得显示“执行失败”。

### 3.3 证明

草案 §4.7（两种实现、共同语义、metric/item 两级）、§9.3 第 11 条、§9.4 不变量。

## 4. 不变约束复核

| 约束 | 结果 |
|---|---|
| D1–D4 指标定义 | 未变：`F_strict=S/(S+U)`、`F_coverage=S/(S+U+I)`、展示名、D3/D4 口径均保留 |
| 目标数值 | 未变；目标 revision 仍为 v1.0.2，40 条数值与 v1.0.1 一致 |
| 旧目标文件/SHA | 未覆盖；`34357b34…` 仍只读 |
| 目标 revision SHA | 未变；`3ee15dfc…` |
| Human Gold / provisional | 未修改 |
| 运行时代码/Schema/Service/Prompt/API/DB | 未修改 |
| Judge | 未运行 |
| v1.2.0 | 未创建、未激活 |
| M1-B accepted | 未标记 |
| M1-C / M2 前端 | 未启动 |

静态 validation 的 `no_runtime_changes`、`old_target_sha_unchanged`、`new_target_sha_unchanged`、`final_labels_sha_unchanged` 均为 true。

## 5. 变更文件

| 文件 | 变更 |
|---|---|
| `19-m1b-003-freeze-draft.md` | r2：Item 计数语义 + invalid 持久化契约 |
| `19-m1b-003-freeze-draft.sha256` | 新 SHA |
| `19-m1b-003-freeze-draft.validation.json` | 33/33 静态 validation |
| `21-m1b-003-r2-revision-record.md` | 本修订记录 |
| `README.md` | 状态更新（r2 待最终审核） |
| `06-repair-progress.md` | 进度记录 |

未修改：目标 revision、静态重算 JSON、Human Gold、provisional、backend、frontend、nginx、ops。

## 6. 剩余未决问题

1. 是否接受 r2 与目标 revision v1.0.2；
2. 是否接受 `completed_items=evaluated_items` 与四类终态 + unprocessed 的守恒关系；
3. 是否接受 invalid 两种持久化实现的共同语义；
4. 是否接受 M1-C 必须修改 `retry_run` / `finalize_run` / `status` 枚举；
5. 通过后才决定 M1-B 是否 `accepted`、M1-C 是否启动。

**状态：`freeze_draft_pending_human`**
**签字：Agent（代拟）**
**下一步：人工最终审核 → M1-B accepted 决策 → M1-C 启动决策**
