# M1-D-2 v1.2.1 Prompt 资产校验（非 Judge 运行）

> 状态：`design_draft` / `active=false`；未冻结、未激活、未跑 Judge。
> version：`v1.2.1`；rubric_version：`v1.2.0`（A 方案）
> Schema / Metric：`rag_judge_schema_v3` / `v3`
> MANIFEST SHA256：`fa375109d661e53f23a2f35f5cff20a3ea7314e80211975fc44a4d23aec026ed`
> 校验输出 SHA256：`f3f5e375f0d0f208b2781861bb38864fa1156b6a8f3f58cadb4d993dba244f05`

## Prompt SHA256

| 文件 | v1.2.1 | v1.2.0 |
|---|---|---|
| `faithfulness.txt` | `ff9a1b610d43e3cedbabf06352a9ace9443da9a7c65f3c76ee81b17aca9c63a9` | `b637775869163fdd7bd2545ca9b79197c10193d2937c9bef4e61add72e934d61` |
| `answer_correctness.txt` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` |
| `answer_relevancy.txt` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` |

## 检查

- 检查项：22；通过：22；失败：0
- 只改 F evidence 连续性；C/R SHA 与 v1.2.0 完全一致。
- rubric_version 保持 v1.2.0，不声称 rubric 变更。
- 默认仍 v1.0.0；v1.2.1 只显式加载。
- 未跑 Judge、未激活、未跑 40。
