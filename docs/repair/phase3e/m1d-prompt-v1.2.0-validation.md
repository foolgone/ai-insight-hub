# M1-D-0 v1.2.0 Prompt 资产校验（非 Judge 运行）

> 状态：`design_draft` / `active=false`；未跑 Judge、未激活、未上生产。
> Prompt 版本：`v1.2.0`
> Schema：`rag_judge_schema_v3`；rubric：`v1.2.0`
> MANIFEST SHA256：`5a98be00f8762a67d12b453f70dd17eea6228949a48914339740d8412e8e6a7b`
> 校验输出 SHA256：`907886bd0ad86a0f335f346966efed939a36be1ea852d608b9aa2623ffc7d493`

## Prompt SHA256

| 文件 | SHA256 |
|---|---|
| `faithfulness.txt` | `b637775869163fdd7bd2545ca9b79197c10193d2937c9bef4e61add72e934d61` |
| `answer_correctness.txt` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` |
| `answer_relevancy.txt` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` |

## 检查

- 检查项：22；通过：22；失败：0
- 默认版本：`v1.0.0`；v1.2.0 只能显式加载。
- `faithfulness_strict` 只在 `derived_metrics`，不在 `judge_metrics`。
- 未运行 Judge；未修改 v1.0.0/v1.1.x Prompt。
