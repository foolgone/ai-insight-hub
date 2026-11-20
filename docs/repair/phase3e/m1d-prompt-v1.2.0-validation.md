# M1-D-0 v1.2.0 Prompt 资产校验（非 Judge 运行）

> 状态：`frozen` / `active=false`；metadata-only 冻结，未激活、未跑 Judge、未上生产。
> Prompt 版本：`v1.2.0`
> Schema：`rag_judge_schema_v3`；rubric：`v1.2.0`
> MANIFEST SHA256：`ee1c25be8767bf66069f92e769fd8dd1d986cb950d9e96d3f550af587c35f778`
> 校验输出 SHA256：`21326f2cb3d275a7fe84291a87c2a04243e57dab23d0be2abd8fa27a42beb5f8`

## Prompt SHA256

| 文件 | SHA256 |
|---|---|
| `faithfulness.txt` | `b637775869163fdd7bd2545ca9b79197c10193d2937c9bef4e61add72e934d61` |
| `answer_correctness.txt` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` |
| `answer_relevancy.txt` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` |

## 检查

- 检查项：22；通过：22；失败：0
- 默认版本：`v1.0.0`；v1.2.0 已 metadata-only 冻结，但仍只能显式加载。
- `faithfulness_strict` 只在 `derived_metrics`，不在 `judge_metrics`。
- 未运行 Judge；未修改 v1.0.0/v1.1.x Prompt。
