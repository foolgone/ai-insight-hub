# M1-D-5 v1.2.3 Prompt 与合同修复静态校验（非 Judge 运行）

> 状态：`design_draft` / `active=false`；未冻结、未激活、未跑 Judge。
> version：`v1.2.3`；rubric_version：`v1.2.0`
> Schema / Metric：`rag_judge_schema_v3` / `v3`
> MANIFEST SHA256：`2257b143bf58d376b59889cfe6ccd1ade5e209a95386cc8b09158d935bc5ccf5`
> quote validator SHA256：`153ab4a6f203ca0398133a2cc2ca6fda834f7670afa90651c66cfa44b92c722a`
> 校验输出 SHA256：`496b466ce36c3d54c7f8244040d57824e1089f8f71e8a1e13bb2a7eaafdf9172`

## Prompt SHA256

| 文件 | v1.2.3 | v1.2.2 |
|---|---|---|
| `faithfulness.txt` | `4f3b9739b2f839f95de159542e2546ff9df96203b1a69fead227e9b8c399f0bf` | `ed21979abd71dedd522ee97636b17509bae9d1b845d54fa114f4a1fbf8f01cf3` |
| `answer_correctness.txt` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` |
| `answer_relevancy.txt` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` |

## 检查

- 检查项：25；通过：25；失败：0
- Agent quote 预校验、共享 validator、repair example、旧版本隔离。
- Prompt/repair example 不含 Q23/生鲜食品/fixture 专属文本。
- 默认仍 v1.0.0；未跑 Judge、未激活、未跑 10/40。
