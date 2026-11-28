# M1-D-6 Q23 根因与 M1-A target / Gold 复核

> 状态：**read-only 复核**；未跑 Judge、未改 target、未改 Prompt/Agent、未激活 v1.2.4。
> 日期：2026-11-23
> 关联：`49-m1d6-v1.2.4-single-case-diagnostic-results.md`；application SHA `54193e91…`；ledger SHA `c07b8401…`。
> 本文件只记录复核证据与待决策选项，不构成 target 变更批准。

## 1. 决策记录

项目决策角色（代江晚）在 2026-11-23 单案例复核后确认：

1. Q23 `invalid` 正确；patch 1 次后仍失败，停止正确。
2. **patch 的 `evidence_refs: null` 不是根因**；即使 patch 完美，按本次初始 claim 分解，Q23 F 仍为 `0.333`，低于 `[0.4, 0.5]`。
3. 不批准 v1.2.5 作为“让 Q23 通过”的 patch-only 方案。
4. 先做 M1-A Q23 target / Gold 复核；复核结论只有两种：
   - target 不成立 → 走 M1-A 生成 target v1.0.3，明确记录理由；不静默改 v1.0.2；
   - target 成立 → Judge 的 claim 判断有误 → 修 Prompt/Agent 的 claim 分解，仍不是 patch 能修的。
5. v1.2.5 patch 健壮性可并行设计，但报告必须写明：不改变 support_status/claim 分解，不保证 Q23 F 进区间。
6. Q23 下一次诊断建议跑 3 次 F，报 median / min / max；诊断结果不计入 10 条。
7. 当前状态不变：M1-D-6 diagnostic `blocked`，不 `verified`；v1.2.4 `frozen` / `inactive`；10/40、激活、改默认版本均不批准。

## 2. 可复现的 F 计算

对 `m1d6-single-case-results.json` 的 Q23 初始 F 输出做只读核算：

- 保留初始 `claim_type` / `claim_subtype` / `support_status` / claim 粒度；
- 把所有 evidence quote 替换为 C1 的合法连续子串；
- 调用 `app.services.rag_judge_service._faithfulness_score_v3`。

结果：

```json
{
 "coverage": {
  "status": "evaluated",
  "score": 0.333333,
  "claim_count": 10,
  "supported_count": 2,
  "unsupported_count": 1,
  "insufficient_evidence_count": 3,
  "non_factual_count": 4,
  "scorable_claim_count": 6,
  "validation_errors": []
 },
 "strict": {
  "status": "evaluated",
  "score": 0.666667
 }
}
```

结论：**0.333 不是 quote 错误造成的，是 claim 分解/support_status 决定的**。patch 只改 `evidence_refs`，无法把 0.333 变成 0.5。

## 3. 本次 Q23 初始 claim 分解

| claim_id | claim | type | subtype | support | 进入 F 分母 |
|---|---|---|---|---|---|
| cl1 | 可以按政策反馈 | factual | policy | **unsupported** | 是 |
| cl2 | 生鲜食品质量问题需在签收后 24 小时内拍照反馈 | factual | policy | supported | 是 |
| cl3 | 您是在签收后第 2 天（即超过 24 小时）才发现并反馈 | factual | fact | insufficient_evidence | 是 |
| cl4 | 已超出政策规定的反馈时效 | factual | derived | supported | 是 |
| cl5 | 该时限是硬性要求 | factual | condition | insufficient_evidence | 是 |
| cl6 | 文档未提及例外情形或宽限期 | non_factual | absence | null | 否 |
| cl7 | 24 小时起算点为“签收完成时间”… | factual | condition | insufficient_evidence | 是 |
| cl8 | 建议立即…提交带时间水印的照片凭证 | non_factual | advice | null | 否 |
| cl9 | 若已超时，可尝试联系客服… | non_factual | advice | null | 否 |
| cl10 | 文档未说明超时后申诉渠道或人工复核机制 | non_factual | absence | null | 否 |

计数：`supported=2`、`unsupported=1`、`insufficient=3`、`non_factual=4`、`scorable=6` → **F=2/6=0.333333**；strict=2/(2+1)=0.666667。

## 4. 关键：同一句“第 2 天已超出 24 小时”被拆成两条

M1-A 语义规范（`12-judge-semantic-spec.md`）：

- §3.1 `derived`：由明确规则/条件/数字推导出的结论，示例明确包含“**第 10 天已超出 7 天时限**”。
- §8：多步算术/派生结论可以 `supported`，但必须使用 `derived`，并引用依据规则的最短连续子串；每一步都要有明确规则。

按该规范，“签收后第 2 天已超出 24 小时反馈时限”更适合作为 **1 条 derived claim**：

- 前提：query 给出“第 2 天”；
- 规则：C1 给出“质量问题需在签收后 24 小时内拍照反馈”；
- 结论：第 2 天 > 24 小时 → 已超出。

本次 v1.2.4 把它拆成：

- cl3 “第 2 天” → `insufficient_evidence`（认为 context 没有用户时间）；
- cl4 “已超出” → `supported`（引用 24 小时规则）。

这不是 patch 能修的：patch 只改 evidence_refs，不合并 claim，也不改 support_status。

## 5. 不同 claim 分解下的 F

| 方案 | cl1 | cl2 | cl3/cl4 | cl5 | cl7 | scorable | supported | F | 目标 [0.4,0.5] |
|---|---|---|---|---|---|---:|---:|---:|---|
| S0 本次拆分 | U | S | I + S | I | I | 6 | 2 | **0.333** | miss |
| S1 合并 cl3+cl4 为 1 条 derived S | U | S | S | I | I | 5 | 2 | **0.400** | pass（下界） |
| S2 合并 cl3+cl4 为 1 条 derived I | U | S | I | I | I | 5 | 1 | **0.200** | miss |
| S3 历史口径（cl1 S、cl3 S，按用户复核） | S | S | S | I | I | 6 | 3 | **0.500** | pass（上界） |

说明：

- S1 与 M1-A `derived` 定义最一致；若人工确认“第 2 天已超出 24 小时”应合成 1 条，则 **F=0.400，target [0.4,0.5] 仍成立**。
- S0 是本次实际输出；0.333 是“当前拆分下的诚实分数”，不是 target 的必然反证。
- S3 是用户复核引用的历史口径；同一 F Prompt SHA 在不同运行/拆分下可能得到 0.333、0.4、0.5 三种结果，说明 target 对 claim 粒度高度敏感。

## 6. cl1 应该 supported 还是 unsupported

Q23 Gold：`不能按该条款反馈。生鲜食品质量问题需在签收后 24 小时内拍照反馈，超过 24 小时反馈不符合该条款。`

Answer 首句：`是的，可以按政策反馈。` 后文又说已超出时效、原则上不符合受理条件。

按 `12-judge-semantic-spec.md` §7：

- 回答 vs Context 矛盾 → `support_status=unsupported`；
- 回答内部矛盾 → `is_contradictory=true`，support_status 仍按证据判断。

初步判断（待人工确认）：

- cl1 “可以按政策反馈” **应为 unsupported**，不是 insufficient；本次 v1.2.4 的 unsupported 比 v1.2.3 的 insufficient 更接近规范。
- cl1 同时是回答内部矛盾（首句“可以” vs 后文“不符合”），`is_contradictory` 应为 true；本次输出为 false，属于可修的 claim 标注问题，但不是 patch 问题。
- 因此“把 cl1 改成 supported 让 F 到 0.5”不是正确方向；S3 的 0.5 依赖一个语义上不该 supported 的 claim。

## 7. 对四个复核问题的初步回答

| 问题 | 初步回答 | 依据 |
|---|---|---|
| “可以按政策反馈” supported 还是 unsupported？ | **unsupported**；并应标 `is_contradictory=true` | Gold 否定该句；回答内部矛盾；语义规范 §7 |
| “第 2 天已超出 24 小时” 1 条 derived 还是 2 条？ | **1 条 derived supported** 更符合规范 | `derived` 定义示例“第 10 天已超出 7 天”；§8 多步派生 |
| 0.333 是诚实分数吗？[0.4,0.5] 是否成立？ | 0.333 是 S0 拆分下的诚实分数；若采用 S1，F=0.400，target 仍成立 | S0/S1 计算 |
| Q23 单次 gate 还是 3 次 median？ | **3 次 median**；单次波动可跨出窄带 | 0.333/0.4/0.5 对一条 claim 敏感；用户决策 |

## 8. 选项与建议

### 选项 A：target 不成立 → target v1.0.3

适用条件：人工确认 S0（当前拆分）是正确口径，且 0.333 是 Q23 的诚实分数。

动作：

- 走 M1-A 生成 target v1.0.3，明确记录“Q23 target 由 [0.4,0.5] 调整为 …”的理由；
- 不静默改 v1.0.2；v1.0.2 保持只读；
- 需要单独批准，不能由本复核自动生效。

### 选项 B：target 成立 → 修 claim 分解（推荐优先评估）

适用条件：人工确认 S1（“第 2 天已超出 24 小时”合成 1 条 derived）符合语义规范。

动作：

- 不改 target [0.4,0.5]；
- 修 F Prompt/Agent 的 claim 分解规则：禁止把同一派生结论拆成“前提 insufficient + 结论 supported”；
- cl1 保持 unsupported，并补 `is_contradictory=true`；
- 这是 Prompt/Agent 变更，不是 patch 变更；需要新版本、重新 freeze、重新单案例；
- 不能用 v1.2.5 patch-only 代替。

### 选项 C：Q23 3 次 median（建议与 A/B 并行）

动作：

- 下一次 Q23 诊断跑 3 次 F；
- 报告 median / min / max，以及每次的 claim 分解；
- 不用单次结果直接判死；
- 仍不计入 10 条；不改变 10 条 gate 的批准状态。

### 建议（待人工决策）

1. **优先评估选项 B**：现有证据更支持“cl3/cl4 过度拆分”，而不是 target 必然错误；S1 下 F=0.400，target 仍可达。
2. 同时采用选项 C：Q23 窄带 + 单次波动，3 次 median 更适合作为诊断口径。
3. 只有在人工确认 S0 是正确口径时，才进入选项 A（target v1.0.3）。
4. v1.2.5 patch 健壮性可另行设计（null/refusal、unsupported/insufficient 空 refs、supported 非空），但不得写成“保证 Q23 通过”。

## 9. 当前状态与边界

| 项 | 状态 |
|---|---|
| M1-D-6 diagnostic | `blocked`，不 `verified` |
| v1.2.4 | `frozen` / `active=false` / 默认 `v1.0.0` |
| target v1.0.2 | 未修改；本复核不产生 v1.0.3 |
| Q23 target/Gold 复核 | 本文件；待人工选择 A/B/C |
| v1.2.5 patch-only | 不批准作为 Q23 通过方案 |
| v1.2.5 patch 健壮性 | 可并行设计；不保证 Q23 F 进区间 |
| 10/40 Judge | 不批准 |
| v1.2.4 激活 / 改默认版本 | 不批准 |
| M1-D-4 / M1-D-1 / M1-D-3 | 保持 blocked |
| M1-C / M1-D | 未 accepted |
| M2/M3 | 未启动 |

**未执行**：Judge 调用、target 修改、Prompt/Agent 修改、10/40、激活、默认版本切换。

## 10. 证据来源

| 项 | 值 |
|---|---|
| application SHA | `54193e918daf3111014790923431695c7641fb629d2341bd71ecbe03001b1388` |
| raw results SHA | `dec1d9644f091338d59d24200d1fe1f0a40659e130bc7ceff7d6cf752bf3d939` |
| analysis SHA | `24bea3ec6acc31e313a4908b88934ecd225716f983a6a25d11b9f56c14ecebe9` |
| report SHA | `d7762d6ad49f69d7ee3369e891c6a7f5ea0fcdf9dd754bc2ec8df5e650f8265e` |
| ledger SHA | `c07b8401778e3668676db797376cd014406a8cafc587288ab71a966a20dfedf7` |
| F / C / R | `52f1b3cf…` / `ca489fcf…` / `f3efe431…` |
| target | `3ee15dfc…`（v1.0.2，未改） |
| labels | `f139623f…` |
| agent_commit / freeze | `8dcd53d` / `c813443` |
