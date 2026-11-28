# M1-D-5 v1.2.3 Prompt 与合同修复静态校验（非 Judge 运行）

> 状态：`frozen` / `active=false`；metadata-only 冻结，未激活、未跑 Judge。
> version：`v1.2.3`；rubric_version：`v1.2.0`
> Schema / Metric：`rag_judge_schema_v3` / `v3`
> MANIFEST SHA256：`7856b74e588fc21ac00aee8340bc2294a090c0fd3e373de3079e3af41e7c4094`
> quote validator SHA256：`153ab4a6f203ca0398133a2cc2ca6fda834f7670afa90651c66cfa44b92c722a`
> leakage audit：findings=0，non_whitelisted=0
> 校验输出 SHA256：`8e790aacafccc04cd5b079c249c0720a3f0aa27d5a32f65d8f00b19c26908611`

## Prompt SHA256

| 文件 | v1.2.3 | v1.2.2 |
|---|---|---|
| `faithfulness.txt` | `52f1b3cf3b92d6f9616e73ed7de26a0721d65c27763f48edd41b38f1e06a025d` | `ed21979abd71dedd522ee97636b17509bae9d1b845d54fa114f4a1fbf8f01cf3` |
| `answer_correctness.txt` | `a5f9e5b2d3d0e1bb80803f8a09e5ea7c980b5e8d1c7b9155e86266de92d493ef` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` |
| `answer_relevancy.txt` | `f3efe431683ed26ba0a7338e6e2b5841d65d42dadde5cac30b8340e2ca95dfdc` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` |

## 检查

- 检查项：26；通过：26；失败：0
- Agent quote 预校验、共享 validator、repair example、旧版本隔离。
- Prompt/repair example 不含 Q23/生鲜食品/fixture 专属文本。
- 默认仍 v1.0.0；未跑 Judge、未激活、未跑 10/40。
