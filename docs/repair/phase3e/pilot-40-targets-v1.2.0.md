# v1.2.0 Active Target Table（冻结）

> 文件：`pilot-40-targets-v1.2.0.json`
> 状态：**frozen**
> 冻结日期：2026-11-18
> 冻结人：江晚
> SHA256：`34357b34c3d0fc85e78f90eeebb353b25a148926e3a55b19f17cc23b08b2b5eb`
> 校验：`pilot-40-targets-v1.2.0.validation.json`（24/24 通过）

## 1. 权威关系

- 本文件是 **v1.2.0 目标的唯一权威来源**。
- `pilot-40-final-labels.json` 只负责分类，不负责目标；其 `target_source` 是重批前状态。
- 旧 `pilot-40-targets.json` **只读保留**，SHA `8ae37ac4…`；不得修改，不得用于 v1.2.0 目标。
- v1.2.0 运行时未创建/未激活；本文件冻结不等于运行。

## 2. 目标汇总

| Case | 目标 |
|---|---|
| Q17 | F 0.7–0.9（期望 0.8）；C/R 0.8–1.0 |
| Q30 | F 0.4–1.0（期望 0.5）；C/R 0.8–1.0 |
| Q32 | F 0.9–1.0（期望 1.0）；C/R 0.8–1.0 |
| Q19 | F 0.6–1.0；C/R 0.8–1.0 |
| Q20 | F 0.6–1.0；C/R 0.8–1.0 |
| Q31 | F 0.6–1.0；C/R 0.8–1.0 |
| Q35 | F 0.8–1.0；C 0.7–1.0；R 0.8–1.0 |
| Q36 | F 0.8–1.0；C base 0.5–0.6 / variant 0.9–1.0；R 0.8–1.0 |
| Q14 | F unavailable；C/R 0.8–1.0；known non-pass |

其余 31 条沿用旧目标或保持无显式目标；完整 40 行见 JSON。

## 3. Q32 前提（冻结备注）

Q32 的 F 0.9–1.0 基于以下 3 个 factual 点仍存在：

1. 消费 1 元积 1 分；
2. 积分 12 个月有效；
3. 积分不可转让/提现。

如果 v1.2.0 实际输出把这 3 点也归为 uncertainty/absence，导致 F=`skipped(no_scorable_claims)`：

- 这是 **目标未命中**；
- 不得事后改为 skipped 兜底；
- 不得把 skipped 写成 PASS。

## 4. target_source 备注

`final_labels` 的 `target_source` 是重批前状态；本 active target 文件是目标权威来源。

- Q19、Q32 因新增目标，`target_source` 从 `none` 改为 `additional`；
- 因此本文件计数为：matrix 5 / pilot10 5 / additional 8 / none 22；
- 来源优先级仍为 `matrix > pilot10 > additional > none`，同一案例只取一个来源。

## 5. 状态统计

| target_status | 数量 |
|---|---:|
| unchanged | 31 |
| unchanged_rebaseline | 3（Q20/Q31/Q35） |
| reapproval_required | 2（Q17/Q30） |
| new_target_proposed | 2（Q19/Q32） |
| known_non_pass_reapproval | 1（Q14） |
| reapproval_with_variant | 1（Q36） |
| **合计** | **40** |

> `target_status` 记录的是**冻结前的变更来源**；本表中所有行都已批准。`reapproval_required` / `new_target_proposed` 是历史变更类型，不代表仍待审批。

## 6. 校验

`pilot-40-targets-v1.2.0.validation.json` 24/24 通过，包括：

- 40 行、Q01–Q40、无重复；
- SHA 与 `.sha256` 一致；
- final_labels SHA 匹配；
- 旧 `pilot-40-targets.json` SHA 匹配且标记 `read_only`；
- Q17/Q30/Q32/Q19/Q20/Q31/Q35/Q36/Q14 目标符合提案；
- Q32 不是 skipped，且前提备注存在；
- target_source 计数 5/5/8/22；
- target_status 计数 31/3/2/2/1/1；
- target_status 来源说明与 revision v1.0.1 存在；
- `runtime_active=false`。

## 7. 冻结边界

- 目标表已冻结；v1.2.0 运行时未创建/未激活；
- 未运行 10/40 条或其它 Judge；
- 未修改 Prompt/Service/Schema/API/DB；
- 未进入 Phase 4；
- 下一步：v1.2.0 Schema / 子类型 / Service 设计 → 负向测试 → 单案例 → 10 条 → 40 条。
