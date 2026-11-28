# v1.2.0 目标表 metadata revision（v1.0.2，冻结草案）

> 状态：`freeze_draft_pending_human`；**未 accepted、未用于运行时、未用于 Judge**。
> 日期：2026-11-19
> 文件：`pilot-40-targets-v1.2.0-v1.0.2.json`
> SHA256：`3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846`
> 校验：`pilot-40-targets-v1.2.0-v1.0.2.validation.json`（20/20 通过）

## 1. 修订性质

**metadata-only**：40 条目标数值与 v1.0.1 完全一致；只新增双指标元数据。

| 项 | 值 |
|---|---|
| supersedes | `pilot-40-targets-v1.2.0.json` |
| supersedes SHA256 | `34357b34c3d0fc85e78f90eeebb353b25a148926e3a55b19f17cc23b08b2b5eb` |
| target_values_changed | `false` |
| 旧文件是否被覆盖 | **否**；旧文件与旧 SHA 仍只读保留 |

## 2. 新增指标元数据

| 字段 | 值 | 含义 |
|---|---|---|
| `f_target_metric` | `faithfulness` | 现有 `F` 目标作用于 `faithfulness` |
| `f_target_denominator` | `S+U+I` | F_coverage 分母：supported + unsupported + insufficient |
| `f_target_denominator_long` | `supported_plus_unsupported_plus_insufficient` | 机器可读全称 |
| `f_target_display` | `Faithfulness（证据覆盖）` | 前端/报告显示名 |
| `f_strict_metric` | `faithfulness_strict` | 新增诊断指标 |
| `f_strict_role` | `diagnostic` | 不承载硬目标 |
| `f_strict_target` | `null` | v1.2.0 不设硬目标 |
| `f_strict_display` | `Strict Faithfulness（可判定事实）` | 前端/报告显示名 |
| `metric_version` | `v3` | 两个指标都属于 metric v3 |
| `schema_version` | `rag_judge_schema_v3` | 输出契约 |
| `runtime_active` | `false` | 未激活 |
| `not_for_run` | `true` | 未用于任何 Run |

## 3. 关键目标不变

| Case | F target | 备注 |
|---|---|---|
| Q17 | 0.7–0.9 | v1.2.0 预期 `policy_relationship` factual/insufficient → F_coverage 0.8 |
| Q21 | 0.6–0.7 | 2 条合法 insufficient → F_coverage 0.6 |
| Q23 | 0.4–0.5 | 1 unsupported + 2 insufficient → F_coverage 0.5 |
| Q32 | 0.9–1.0 | 3 factual 前提；若变 uncertainty/absence 导致 skipped，算未命中，无 skipped 兜底 |
| Q14 | F unavailable | known non-pass |

## 4. 校验覆盖（20/20）

- 40 行、Q01–Q40、无重复；
- 40 条 `targets` 与 v1.0.1 逐条深比较一致；
- `f_target_metric` / `f_target_denominator` / `f_strict_role` 正确；
- `f_strict_target=null`；
- `target_values_changed=false`；
- `supersedes_sha256` 匹配旧文件；
- 旧文件 SHA 未被改写；
- `status=freeze_draft_pending_human`；
- `revision=v1.0.2`；
- `final_labels` SHA 未变；
- `runtime_active=false`、`not_for_run=true`；
- `.sha256` 与新文件一致。

## 5. 边界

- 本文件是**冻结草案**，不是 accepted；
- 未替换旧目标表为运行时默认；
- 未修改 Prompt/Service/Schema/API/DB；
- 未创建/激活 v1.2.0；
- 未运行 Judge；
- 需人工审核后才可成为 v1.2.0 的目标元数据 revision。
