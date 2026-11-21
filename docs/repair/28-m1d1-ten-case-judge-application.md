# M1-D-1 10 条 Judge 申请材料

> 状态：`pending_approval`。**仅申请材料，未运行 Judge、未创建 Run、未激活 v1.2.0。**
> 日期：2026-11-21；frozen 提交：`df036a8`；freeze record：`docs/repair/27-m1d0-prompt-freeze-record.md`
> Prompt：`v1.2.0` / `frozen` / schema `rag_judge_schema_v3` / metric `v3`
> MANIFEST SHA256：`ee1c25be8767bf66069f92e769fd8dd1d986cb950d9e96d3f550af587c35f778`
> 申请 JSON SHA256：`a867a618dd70392f7f9de452c22b3752a6d7b2c506e2f533881badb635f47bbc`
> validation SHA256：`47ec811c2c873eca35f5e53037bbc2f6e62648c7db383f2762c3c2c9c224975c`

## 1. 申请结论

本文件只申请 **10 条** Judge：Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36。
10 条通过后才允许单独申请 40 条；本申请不包含 40 条、不激活 v1.2.0、不改默认版本。

## 2. 冻结资产

| 项 | 值 |
|---|---|
| Prompt 版本 | `v1.2.0` |
| Prompt 状态 | `frozen`；`active=false` |
| MANIFEST SHA256 | `ee1c25be8767bf66069f92e769fd8dd1d986cb950d9e96d3f550af587c35f778` |
| `faithfulness.txt` | `b637775869163fdd7bd2545ca9b79197c10193d2937c9bef4e61add72e934d61` |
| `answer_correctness.txt` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` |
| `answer_relevancy.txt` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` |
| Schema / Metric | `rag_judge_schema_v3` / `v3` |
| target | `pilot-40-targets-v1.2.0-v1.0.2.json`（`3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846`） |
| final labels | `pilot-40-final-labels.json`（`f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb`） |
| 默认版本 | `v1.0.0`（保持不变） |

## 3. 10 个 Cases

| Case | group | category | context | baseline | expected status | F target | C target | R target | known issue |
|---|---|---|---:|---|---|---|---|---|---|
| Q01 | provisional | direct | 2 | reused | evaluated | 0.9–1.0 | 0.9–1.0 | 0.8–1.0 | — |
| Q04 | provisional | direct | 2 | reused | evaluated | 1.0 | 0.8–1.0 | 0.9–1.0 | — |
| Q11 | provisional | multi | 2 | reused | evaluated | 0.6–0.9 | 0.8–1.0 | 0.9–1.0 | normative_requirement |
| Q17 | provisional | multi | 2 | reused | evaluated | 0.7–0.9 | 0.8–1.0 | 0.8–1.0 | policy_relationship_target_reapproval |
| Q21 | provisional | constraint | 2 | reused | evaluated | 0.6–0.7 | — | — | Q21#3_insufficient |
| Q23 | human_gold | constraint | 2 | reused | evaluated | 0.4–0.5 | 0.0–0.2 | 0.7–1.0 | quote_synthesis_history;internal_contradiction |
| Q29 | provisional | unanswerable | 2 | reused | skipped(no_scorable_claims) | skipped | 0.9–1.0 | 0.9–1.0 | correct_skip |
| Q31 | provisional | unanswerable | 2 | reused | evaluated | 0.6–1.0 | 0.8–1.0 | 0.8–1.0 | quote_absence_diagnostic |
| Q35 | human_gold | ambiguous | 2 | available_old_run | evaluated | 0.8–1.0 | 0.7–1.0 | 0.8–1.0 | absence_quote_diagnostic |
| Q36 | human_gold | ambiguous | 2 | available_old_run | evaluated | 0.8–1.0 | 0.5–0.6 | 0.8–1.0 | condition_sentence;conflict_disclosure |

固定口径：

- Q29 的 F 必须是 `skipped(no_scorable_claims)`；不得 0.0、不得用 skipped 兜底其它案例；
- Q35/Q36 只用 old run 参考，不把旧结果冒充 v1.2.0 实测；
- Q17 使用 v1.0.2 的 `0.7–0.9` 目标；旧 `0.9–1.0` 已被 reapproval 取代；
- Q21 只有 F 目标；Q21#3 保持 `insufficient_evidence`；
- Q36 base C 目标 `0.5–0.6`；若回答披露文档冲突，按 variant `0.9–1.0` 判定，报告必须写明用了哪一口径；
- Q23/Q35/Q36 为 Human Gold；其余 7 条为 provisional，报告不得混算均值。

## 4. Run 配置

| 项 | 值 |
|---|---|
| execution_mode | `query` |
| adapter | `weknora` |
| dataset | pilot-40 frozen test split (same dataset version as v1.1.5 pilot) |
| split / limit | `test` / `10` |
| top_k | `5` |
| judge_metrics | `faithfulness, answer_correctness, answer_relevancy` |
| derived_metrics | `faithfulness_strict` |
| judge_prompt_version | `v1.2.0`（显式指定，不改默认） |
| model | `qwen-max` |
| temperature | `0.0` |
| max_tokens | `8192` |
| soft budget | `1500s` |
| schema / metric | `rag_judge_schema_v3` / `v3` |

关键环境变量（不包含密钥）：

```text
DEFAULT_LLM_MODEL=qwen-max
DEFAULT_TEMPERATURE=0.0
RAG_JUDGE_MAX_TOKENS=8192
RAG_ADAPTER=weknora
RAG_JUDGE_PROMPT_VERSION=v1.0.0
```

- WeKnora KB：`4ae8e147-6f76-4330-93f1-d2b3fef3d9ba`；agent/tenant 使用现有部署值，并在 Run 快照中记录；
- Judge endpoint：existing DashScope-compatible endpoint used by prior qwen-max gates; no key in repo；
- 环境作用域：process-local for this Run only; do not write to repo/.env; restore after Run；
- 选择 10 条：按 `item_key` 解析 `item_ids`；Run 快照必须记录实际 UUID 与 dataset checksum。

## 5. 方法与解释边界

- 本次是平台 `query` Run 的端到端闸门：答案/contexts 由 WeKnora 重新生成；
- 10 条目标是 Judge 质量目标；Q35/Q36 的旧 run 只作参考，不作为固定输入复现；
- 若要求“固定同一批 answer/contexts，只切换 Judge Prompt”的 Judge-only 对比，本申请不适用，需另立方案；
- 报告不得把 v1.1.5 旧值写成 v1.2.0 实测，也不得把 Q17/Q32 的预期标签写成实测。

## 6. 预算与调用量

| 项 | 值 |
|---|---:|
| 主运行 case 数 | 10 |
| 主运行 Judge 调用 | 30（10 × 3 指标） |
| 条件重复 cases | Q23/Q35/Q36 |
| 条件重复额外 case-run | 6 |
| 最大 case-run | 16 |
| 最大 Judge 调用 | 48 |
| 估算 input tokens | 70,000–160,000 |
| 估算 output tokens | 9,000–26,000 |
| 预计成本 | CNY 0.35 |
| 上限 | CNY 0.60 |
| **批准 ceiling** | **CNY 0.80** |

计价口径：qwen-max public price: input CNY 0.0024/1K, output CNY 0.0096/1K; actual bill is authoritative。No 40-case spend; ceiling includes one execution retry and HG repeats, not repeated prompt tuning。

## 7. 停止条件与失败处理

| code | 条件 | 动作 |
|---|---|---|
| `preflight_failure` | WeKnora 配置/健康检查、LLM endpoint/model、dataset version、10 个 item_ids、Prompt/MANIFEST SHA 或 22/22 validation 任一不满足 | 拒绝创建 Run；不得跳过 preflight |
| `invalid_contract` | 任一 case/metric 出现 invalid(contract_violation)，包括 schema/subtype/evidence/quote/conflict 违约 | 立即停止；保留已完成结果；不得改 Prompt 或放宽契约后重跑 |
| `failed_execution` | 任一 case/metric 出现 failed(execution) | 同配置最多重试一次；再次失败立即停止 |
| `hg_supported_quote_invalid` | Q23/Q35/Q36 任一 supported claim 的 quote 非逐字、跨片段拼接或引用 answer | 立即停止；不得把 HG quote invalid 当 known diagnostic 放行 |
| `q29_not_skipped` | Q29 的 F 不是 skipped(no_scorable_claims) | 立即停止；不得用 0.0 或其它 skipped 兜底 |
| `unexplained_drop` | 有 baseline 的 case 出现 old - new > 0.10 + 1e-9 的未解释下降 | 停止并人工复核；恰好 0.10 不停止 |
| `second_typo_or_number_change` | 第二次出现 evidence typo、数字/日期/金额改动 | 立即停止 |
| `unprocessed_items` | finalize 后 unprocessed_items > 0，或 10 条未全部终态 | 停止；不得把未处理 item 当 skipped |
| `fingerprint_mismatch` | prompt SHA / MANIFEST SHA / schema / metric / model / temperature / max_tokens / top_k 与申请不一致 | 拒绝运行或立即停止；不得静默换版本 |
| `activation_drift` | v1.2.0 被设为默认、active=true 或 runtime_active=true | 立即停止；回到 frozen / active=false |

失败处理：

- **invalid**：不重试；保留 invalid_reason 与 validation_errors；停止并复审
- **failed_execution**：同配置最多重试一次；不得改 Prompt/Schema/model/top_k
- **skipped**：按 case 语义单独记录；不得把 skipped 当 PASS
- **stop**：保留已完成结果与 run 快照；不启动 40；新 Run 需新批准
- **no_prompt_tuning**：10 条期间不得改 Prompt、Schema、Service、目标或 stop conditions

## 8. 报告要求

- 使用 docs/repair/phase3e/m1c-c4-report-template.md
- 逐条报告 status、F_coverage、F_strict（仅诊断）、C、R、invalid/skipped/failed、insufficient_count/ratio、known issue
- 逐条写 PASS/FAIL/BLOCKED；Q29 只能按 skipped 语义判定
- HG 3 条（Q23/Q35/Q36）与 provisional 7 条分开，不混算均值
- Q17 标 policy_relationship_target_reapproval；Q35/Q36 标 old run only，不冒充 v1.2.0 实测
- 报告写 target v1.0.2 SHA、final_labels SHA、Prompt SHA、MANIFEST SHA、schema/metric version、dataset checksum
- 报告写 adapter/model/temperature/max_tokens/top_k 与 run config_snapshot
- 结论只能写 implemented/verified/blocked；不得自行写 accepted

## 9. 边界

- 本文件是申请材料，不是 Judge 运行；未调用模型、未创建 Run
- 不激活 v1.2.0；active 保持 false、runtime_active 保持 false
- 不修改默认 RAG_JUDGE_PROMPT_VERSION=v1.0.0
- qwen-max / max_tokens / RAG_ADAPTER 只作本次 Run 的临时进程环境，不写入仓库或长期 .env，Run 后恢复
- 不修改 Prompt、MANIFEST、Schema、Service、API、DB、migration 022
- 不运行 40 条；10 条通过后才可单独申请 40 条
- 不启动 M2/M3；不把 M1-C/M1-D 标 accepted
- 不把 Q17/Q32 的预期标签写成实测；本申请不含 Q32

## 10. 批准清单

- [ ] 确认 10 个 cases 与顺序：Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36
- [ ] 确认 v1.2.0 frozen Prompt SHA、MANIFEST SHA、schema v3、metric v3
- [ ] 确认 run 配置：query / weknora / top_k=5 / qwen-max / temperature=0.0 / max_tokens=8192
- [ ] 确认预算上限 CNY 0.80 与最大 48 次 Judge 调用
- [ ] 确认停止条件与失败处理
- [ ] 确认不会激活 v1.2.0、不会改默认版本、不会跑 40
- [ ] 批准后才执行 10 条；执行后停下报告

批准后只执行 10 条；执行完停下报告。10 条通过后才单独申请 40 条。
