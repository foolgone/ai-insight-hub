# M1-C C4 静态目标回归（非 Judge 运行）

> 状态：`static_target_regression_not_judge_run`；生成日期 2026-11-20。
> 目标：`pilot-40-targets-v1.2.0-v1.0.2.json` SHA256 `3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846`
> 分类：`pilot-40-final-labels.json` SHA256 `f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb`
> 重算：`m1b003-static-recalc.json` SHA256 `53787fbb2a434953354bd821b62581e6e56ba5db10751149c236f1e7656437bb`
> 脚本：`m1c_c4_static_targets.py` SHA256 `a509c43350a5fc76ec2874dfa9a98ff61d54e6341b6a1b26aa15ea1e6f82a13f`
> 输出：`m1c-c4-static-targets.json` SHA256 `3ead3bdf8e354d3968d6dcc77561068d9c2a455ec42070e16dda20e58d2c5f44`

| Case | target F | source | F_coverage | F_strict | target |
|---|---:|---|---:|---:|---|
| Q11 | [0.6, 0.9] | observed_v1.1.5 | 0.833333 | 1.0 | in |
| Q17 | [0.7, 0.9] | expected_v1.2.0 | 0.8 | 1.0 | in |
| Q21 | [0.6, 0.7] | observed_v1.1.5 | 0.6 | 1.0 | in |
| Q23 | [0.4, 0.5] | observed_v1.1.5 | 0.5 | 0.75 | in |
| Q32 | [0.9, 1.0] | expected_v1.2.0 | 1.0 | 1.0 | in |

## 边界

- 本文件是静态目标回归，不是 Judge 新运行；
- Q17/Q32 使用 `expected_v1.2.0`，不是实测；
- Q11/Q21/Q23 使用 `observed_v1.1.5`；
- F_strict 只记录，不作为目标通过率；
- 未修改 Prompt/Service/Schema/API/DB；未运行 Judge。
