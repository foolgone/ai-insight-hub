# M1-D-4 v1.2.2 Prompt 资产校验（非 Judge 运行）

> 状态：`design_draft` / `active=false`；未冻结、未激活、未跑 Judge。
> version：`v1.2.2`；rubric_version：`v1.2.0`
> Schema / Metric：`rag_judge_schema_v3` / `v3`
> MANIFEST SHA256：`2456eeff1dcc5d8c76e61929f9795e0488f0d2e9cd21762ab288c670cb44665b`
> 校验输出 SHA256：`9d3aae11178c5e2e6a0473610f71f611ed35d9dde4ebf6bff4b1c716f4d357e1`

## Prompt SHA256

| 文件 | v1.2.2 | v1.2.1 |
|---|---|---|
| `faithfulness.txt` | `ed21979abd71dedd522ee97636b17509bae9d1b845d54fa114f4a1fbf8f01cf3` | `9efdc64df1eebafa727bc0946a03192c2d9e9907bd7a3170f867f19774211068` |
| `answer_correctness.txt` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` |
| `answer_relevancy.txt` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` |

## 检查

- 检查项：23；通过：23；失败：0
- 只改 F absence/直接支持；C/R SHA 与 v1.2.1 一致。
- repair example 版本隔离要求已记录；旧版本示例由 pytest 断言。
- 默认仍 v1.0.0；未跑 Judge、未激活、未跑 40。
