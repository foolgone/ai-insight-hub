# v1.2.0 目标重批提案（PENDING）

> 文件：`pilot-40-targets-v1.2.0-reapproval.json`
> 状态：**历史提案；已于 2026-11-18 批准并冻结为 `pilot-40-targets-v1.2.0.json`（SHA `070960c9…`）**
> 依据：`12-judge-semantic-spec.md`（2026-11-18 frozen）
> 分类来源：`pilot-40-final-labels.json`（SHA `f139623f…`）
> 旧目标：`pilot-40-targets.json`（未修改）
> **本文件保留作历史；active target 文件才是目标唯一来源。**

## 1. 受影响案例

| Case | 语义变化 | 旧目标 | 提案 | 状态 |
|---|---|---|---|---|
| Q17 | `policy_relationship` factual | F 0.9–1.0 | **F 0.7–0.9（期望 0.8）**；C/R 0.8–1.0 | reapproval_required |
| Q30 | `policy_scope` factual | F 0.4–1.0（旧 expected 1.0） | **F 0.4–1.0（期望 0.5）**；C/R 0.8–1.0 | reapproval_required |
| Q32 | `uncertainty` non_factual | 无 | **F 0.9–1.0（期望 1.0）**；C/R 0.8–1.0 | new_target_proposed |
| Q19 | absence/meta 排除 | 无 | **F 0.6–1.0**；C/R 0.8–1.0 | new_target_proposed |
| Q20 | `policy_scope` factual | F 0.6–1.0 | F 0.6–1.0（期望 0.8）；C/R 0.8–1.0 | unchanged_rebaseline |
| Q31 | absence/meta 排除 | F 0.6–1.0 | F 0.6–1.0；C/R 0.8–1.0 | unchanged_rebaseline |
| Q35 | absence 排除 | F 0.8–1.0 | F 0.8–1.0；C 0.7–1.0；R 0.8–1.0 | unchanged_rebaseline |
| Q36 | 条件句 factual | F 0.8–1.0；C 0.5–0.6 | **F 0.8–1.0**；C base 0.5–0.6 / variant 0.9–1.0；R 0.8–1.0 | reapproval_with_variant |
| Q14 | F unavailable | F unavailable；C/R 0.8–1.0 | **F unavailable**；C/R 0.8–1.0；保留 0.7 方差 | known_non_pass_reapproval |

## 2. Q32 选择

选择 **F 0.9–1.0（期望 1.0）**，不选 `skipped`：

- Q32 回答仍有 3 条明确积分规则（1 元 1 分、12 个月有效、不可转让/提现）；
- 只有“无法确认积分支持礼品兑换”是 `uncertainty`；
- `uncertainty` 退出分母后，剩余 3 条 factual 应 supported → F=1.0；
- 如果未来回答完全只有 uncertainty/absence，才走 `skipped(no_scorable_claims)`。

## 3. 状态统计

| target_status | 数量 |
|---|---:|
| unchanged | 31 |
| unchanged_rebaseline | 3（Q20/Q31/Q35） |
| reapproval_required | 2（Q17/Q30） |
| new_target_proposed | 2（Q19/Q32） |
| known_non_pass_reapproval | 1（Q14） |
| reapproval_with_variant | 1（Q36） |
| **合计** | **40** |

## 4. 校验

`pilot-40-targets-v1.2.0-reapproval.validation.json`：

- **18/18 通过**；
- 40 行、Q01–Q40；
- old_targets 与 `pilot-40-targets.json` 完全一致；
- final_labels SHA 匹配；
- Q17/Q30/Q32/Q19/Q20/Q31/Q35/Q36/Q14 提案范围符合上表；
- target_source 与 final_labels 一致；Q19/Q32 因新目标改为 `additional`；
- 全部 `approval=pending_human`、`not_for_run=true`。

## 5. 冻结边界

- 旧 `pilot-40-targets.json` **未修改**；
- 本文件是目标重批提案，不是 active target；
- 未创建/激活 v1.2.0；
- 未运行 10/40 条或其它 Judge；
- 未修改 Prompt/Service/Schema/API/DB；
- 未进入 Phase 4。

## 6. 下一步

1. 人工签字本表。
2. 签字后生成 active target 文件（替换/新增 `pilot-40-targets` 的 v1.2.0 版本），并冻结 SHA。
3. 进入 v1.2.0 Schema / 子类型 / Service 设计。
4. 先负向测试，再单案例、10 条、40 条。
5. 仍不创建/激活 v1.2.0、不跑 Judge，直到 Schema/目标设计复核通过。
