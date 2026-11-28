# M1-B-003 静态重算（非 Judge 运行）

> 状态：`static_recalculation_not_judge_run`；生成日期 2026-11-19。
> 输入：`pilot-40-v1.0.0-vs-v1.1.5.json` SHA256 `29732088952ad406d296b2c7d8fd5d34f427fd1e703b9818e2bebf80374a5c68`
> 目标：`pilot-40-targets-v1.2.0-v1.0.2.json` SHA256 `3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846`
> 脚本：`m1b003_static_recalc.py` SHA256 `e21c930b9e9678d4d19c87bd80850db891fbe40135c00de33f313052a97953b4`
> 输出：`m1b003-static-recalc.json` SHA256 `53787fbb2a434953354bd821b62581e6e56ba5db10751149c236f1e7656437bb`

## 定义

- `F_strict = S / (S + U)`
- `F_coverage = S / (S + U + I)`
- `S/U/I/N`：factual supported / factual unsupported / factual insufficient / non_factual

## 关键案例

| Case | target | old F | F_strict | F_coverage | 说明 |
|---|---|---|---|---|---|
| Q11 | [0.6, 0.9] | 0.833333 | 1.0 | 0.833333 | observed v1.1.5 |
| Q14 | unavailable | — | — | — | skipped |
| Q17 | [0.7, 0.9] | 1.0 | 1.0 | 1.0 | observed v1.1.5 |
| Q17（预期） | [0.7, 0.9] | — | 1.0 | 0.8 | expected v1.2.0；v1.2.0 expected: cl5 policy_relationship factual/insufficient; v1.1.5 cl5 was meta |
| Q21 | [0.6, 0.7] | 0.6 | 1.0 | 0.6 | observed v1.1.5 |
| Q23 | [0.4, 0.5] | 0.5 | 0.75 | 0.5 | observed v1.1.5 |
| Q29 | skipped | — | — | — | skipped |
| Q32 | [0.9, 1.0] | 0.75 | 1.0 | 0.75 | observed v1.1.5 |
| Q32（预期） | [0.9, 1.0] | — | 1.0 | 1.0 | expected v1.2.0；v1.2.0 expected: cl1 uncertainty non_factual; v1.1.5 cl1 was factual/insufficient |

## 边界

- 本文件是静态重算，不是 Judge 新运行；
- Q17/Q32 的 `expected_v1.2.0` 是预期转换，不是已观测结果；
- 未修改 Prompt/Service/Schema/API/DB；
- 未创建/激活 v1.2.0；未运行 Judge。
