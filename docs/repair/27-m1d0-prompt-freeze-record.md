# M1-D-0 v1.2.0 Prompt 冻结记录（metadata-only）

> 状态：**frozen**；`active=false`、`runtime_active=false`。**未激活、未跑 Judge、未上生产。**
> 批准人：项目决策角色（代江晚）
> 批准日期：2026-11-20
> 设计草案提交：`071c3b6`
> 冻结类型：仅元数据（MANIFEST `status` / `frozen` / `note`）；**不改 3 个 Prompt 正文**。
> 本记录所在提交：见 `git log -- docs/repair/27-m1d0-prompt-freeze-record.md`。

## 1. 批准范围

人工审核通过 `071c3b6` 的 Prompt 资产、MANIFEST、SHA、validation 与新增测试，批准执行一次 metadata-only freeze：

| 字段 | 冻结前 | 冻结后 |
|---|---|---|
| `status` | `design_draft` | `frozen` |
| `frozen` | `false` | `true` |
| `active` | `false` | `false`（保持） |
| `runtime_active` | `false` | `false`（保持） |
| `default_prompt_version` | `v1.0.0` | `v1.0.0`（保持） |
| `schema_version` | `rag_judge_schema_v3` | `rag_judge_schema_v3`（保持） |
| `rubric_version` | `v1.2.0` | `v1.2.0`（保持） |
| `judge_metrics` | F/C/R | F/C/R（保持；不含 strict） |
| `derived_metrics` | `["faithfulness_strict"]` | 保持 |

未修改：3 个 Prompt 正文、Prompt SHA、`version.txt`、Schema、Service、API、DB、migration 022、r2、目标 v1.0.2、Human Gold / provisional。

## 2. Prompt SHA（冻结后不变）

| Prompt | SHA256 | 与 `071c3b6` 对比 |
|---|---|---|
| `faithfulness.txt` | `b637775869163fdd7bd2545ca9b79197c10193d2937c9bef4e61add72e934d61` | 未变 |
| `answer_correctness.txt` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` | 未变 |
| `answer_relevancy.txt` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` | 未变 |

## 3. MANIFEST SHA

| 项 | SHA256 |
|---|---|
| 冻结前 `MANIFEST.json`（`design_draft`） | `5a98be00f8762a67d12b453f70dd17eea6228949a48914339740d8412e8e6a7b` |
| 冻结后 `MANIFEST.json`（`frozen`） | `ee1c25be8767bf66069f92e769fd8dd1d986cb950d9e96d3f550af587c35f778` |

旧 `design_draft` 记录保留在提交 `071c3b6`；本记录不覆盖该提交，也不改写旧 SHA。

## 4. Validation

| 项 | 值 |
|---|---|
| 冻结前 validation | `m1d-prompt-v1.2.0-validation.json`，SHA `907886bd0ad86a0f335f346966efed939a36be1ea852d608b9aa2623ffc7d493`，22/22 pass |
| 冻结后 validation | `m1d-prompt-v1.2.0-validation.json`，SHA `21326f2cb3d275a7fe84291a87c2a04243e57dab23d0be2abd8fa27a42beb5f8`，22/22 pass |
| 校验脚本 | `m1d_prompt_assets_validate.py`，SHA `bddb26e6935b4673d87d366c07abcc21b0403ce05cc7220a51c8eae1e69d4490` |
| 校验内容 | MANIFEST 状态/active/frozen、3 个 Prompt SHA、16 subtype、v3 字段、invalid 契约、无案例 ID、strict 不进 `judge_metrics`、v1.0.0/v1.1.5 Prompt 完整性 |
| Judge 运行 | 否 |
| 运行时激活 | 否 |

## 5. 冻结后状态

| 项 | 状态 |
|---|---|
| v1.2.0 Prompt | `frozen` |
| `active` | `false` |
| `runtime_active` | `false` |
| 默认 `RAG_JUDGE_PROMPT_VERSION` | `v1.0.0` |
| v1.2.0 默认选中 | 否 |
| 显式加载 | 允许（仅显式 `judge_prompt_version=v1.2.0`） |
| 10 条 Judge | 未批准 |
| 40 条 Judge | 未批准 |
| M1-C | 未 accepted |
| M1-D | 未 accepted |
| M2/M3 | 未启动 |

## 6. 激活前置条件（仍未满足）

冻结 ≠ 激活。以下全部满足后才可讨论激活：

1. 10 条 Judge 单独批准，并提交：10 个 cases、冻结后的 Prompt SHA / MANIFEST SHA、run 配置（adapter / top_k / model / temperature / max_tokens）、预算与预计调用量、停止条件与失败处理、明确不会把 v1.2.0 设为默认。
2. 10 条 Judge 通过。
3. 40 条 Judge 单独批准并通过。
4. 默认版本切换单独批准；不得与冻结或 Judge 申请捆绑。
5. 生产发布单独批准。

在以上完成前，`active` 保持 `false`，`runtime_active` 保持 `false`，默认版本保持 `v1.0.0`。

## 7. 冻结后明确不允许

- 把 `active` 改为 `true`；
- 修改默认 `RAG_JUDGE_PROMPT_VERSION`；
- 运行 Judge（单案例 / 10 条 / 40 条）；
- 启动 M2 / M3；
- 把 M1-C / M1-D 标为 `accepted`；
- 修改 3 个 Prompt 正文或 Prompt SHA；
- 修改 Schema v2 语义、r2、目标 v1.0.2、Human Gold / provisional、migration 022；
- 把 `faithfulness_strict` 写入 `judge_metrics` 或另建独立 Prompt。

## 8. 结论

**v1.2.0 Prompt 已完成 metadata-only 冻结；`status=frozen`、`active=false`、默认仍 `v1.0.0`。未激活、未跑 Judge、未上生产；10/40 Judge 仍未批准。**
