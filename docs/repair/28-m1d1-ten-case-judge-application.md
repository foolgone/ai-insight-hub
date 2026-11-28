# M1-D-1 10 条 Judge 申请材料（r3，Judge-only Production Service replay）

> 状态：`pending_approval`（r3，退回补充后重提）。**仅申请材料，未运行 Judge、未创建 Run、未激活 v1.2.0。**
> 日期：2026-11-21；frozen 提交：`df036a8`；freeze record：`docs/repair/27-m1d0-prompt-freeze-record.md`
> Prompt：`v1.2.0` / `frozen` / schema `rag_judge_schema_v3` / metric `v3`
> MANIFEST SHA256：`ee1c25be8767bf66069f92e769fd8dd1d986cb950d9e96d3f550af587c35f778`
> fixture SHA256：`dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70`
> 申请 JSON SHA256：`7378d368adf13b7d55e58904af200310fa20f47cf51ccc67967f13e7e437e2ad`
> validation SHA256：`bb2e16023315e6573f90c47cb217a98e9c766754310155c332af36ce2899330d`

## 1. 申请结论

方法 A：**Judge-only 固定 pilot answer/contexts/gold**，只切 v1.2.0 Prompt；不创建平台 Run、不调用 WeKnora、不重新生成答案。

本文件只申请 **10 条** Judge：Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36。
10 条通过后才允许单独申请 40 条；本申请不包含 40 条、不激活 v1.2.0、不改默认版本。

| 退回项 | r3 处理 |
|---|---|
| P0 执行载体绕过 Service | 改为 `judge_trace` production Service replay；synthetic RagTrace；driver 只汇总 JudgeOutcome |
| P1-1 端到端与固定目标混用 | 方法 A：Judge-only fixture；adapter/top_k 不适用；目标用于 Judge 语义判定 |
| P1-2 Q36 base/variant | C 同时报 base 与 variant，只作诊断，不参与 PASS/FAIL；F/R 仍判定 |
| P1-3 HG 重复 | Q23/Q35/Q36 固定 3 次；触发/合成规则预注册；51 次上限（48 planned + 3 retry reserve） |
| P1-4 成本不可复算 | 增加 per-metric token 表、单价来源、51 次计算与 CNY 1.00 硬停止 |

## 2. 冻结资产与固定输入

| 项 | 值 |
|---|---|
| Prompt 版本 | `v1.2.0` |
| Prompt 状态 | `frozen`；`active=false` |
| MANIFEST SHA256 | `ee1c25be8767bf66069f92e769fd8dd1d986cb950d9e96d3f550af587c35f778` |
| `faithfulness.txt` | `b637775869163fdd7bd2545ca9b79197c10193d2937c9bef4e61add72e934d61` |
| `answer_correctness.txt` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` |
| `answer_relevancy.txt` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` |
| Schema / Metric | `rag_judge_schema_v3` / `v3` |
| fixture | `docs/repair/phase3e/pilot-10-v1.1.5-gate.json`（`dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70`） |
| target | `pilot-40-targets-v1.2.0-v1.0.2.json`（`3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846`） |
| final labels | `pilot-40-final-labels.json`（`f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb`） |
| 默认版本 | `v1.0.0`（保持不变） |

固定输入字段：`question` / `answer` / `contexts[].content` / `gold_answer`；10 个 case 从 fixture 读取，缺失或 SHA 不符即停止。fixture 内的 historical target 字段不读取，目标只用 `pilot-40-targets-v1.2.0-v1.0.2.json`。

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
- Q35/Q36 使用 fixture 中的固定旧 run answer/contexts；不生成新答案，不把旧结果冒充新端到端结果；
- Q17 使用 v1.0.2 的 `0.7–0.9` 目标；旧 `0.9–1.0` 已被 reapproval 取代；
- Q21 只有 F 目标；Q21#3 保持 `insufficient_evidence`；
- Q36 的 C 同时报 base `0.5–0.6` 与 variant `0.9–1.0`，只作诊断，不参与 10 条 PASS/FAIL；F/R 仍按目标判定；
- Q23/Q35/Q36 固定 3 次：Q23 需 3/3 在目标内；Q35/Q36 需至少 2/3 在目标内；均不得有 invalid/HG quote violation；
- Q23/Q35/Q36 为 Human Gold；其余 7 条为 provisional，报告不得混算均值。

## 4. Judge-only 配置

| 项 | 值 |
|---|---|
| execution_mode | `judge_only_fixture` |
| execution_vehicle | production Service replay: rag_judge_service.judge_trace(session=None, trace=synthetic RagTrace, item=synthetic item, prompt_version='v1.2.0'); driver only aggregates JudgeOutcome; no reimplementation of F scoring |
| Service entrypoint | `rag_judge_service.judge_trace` |
| session / DB | `None` / 不写 DB |
| scoring | C3 Service；driver 不重新实现计分 |
| outputs | faithfulness, faithfulness_strict, answer_correctness, answer_relevancy |
| adapter | 不适用（`None`；不调用 WeKnora/检索） |
| top_k | 不适用（`None`；contexts 固定来自 fixture） |
| end_to_end | `false` |
| no_rag_call / no_platform_run | `true` / `true` |
| fixture | `docs/repair/phase3e/pilot-10-v1.1.5-gate.json`，10 cases，fixed inputs |
| judge_metrics | `faithfulness, answer_correctness, answer_relevancy` |
| derived_metrics | `faithfulness_strict` |
| judge_prompt_version | `v1.2.0`（显式指定，不改默认） |
| model | `qwen-max` |
| temperature | `0.0` |
| max_tokens | `8192` |
| schema / metric | `rag_judge_schema_v3` / `v3` |

### 4.1 Synthetic RagTrace

| 字段 | 值 |
|---|---|
| `id` | stable UUID per case |
| `user_id` | fixed UUID for all 10 cases |
| `task_id` / `dataset_item_id` | `None` / `None` |
| `adapter` / `mode` | `fixture` / `query` |
| `context_source` | `agent_chat`（F 的 `_skip_reason` 要求） |
| `query` / `answer` | fixture `question` / `answer` |
| `retrieved_contexts` | `[{"content": "fixture contexts[].content"}]` |
| `status` | `success` |
| item | `{"gold_answer": "fixture gold_answer"}` |

### 4.2 关键环境变量（不包含密钥）

```text
DEFAULT_LLM_MODEL=qwen-max
DEFAULT_TEMPERATURE=0.0
RAG_JUDGE_MAX_TOKENS=8192
RAG_JUDGE_PROMPT_VERSION=v1.0.0
```

- Judge endpoint：existing DashScope-compatible endpoint used by prior qwen-max gates; no key in repo；
- 凭证：existing runtime LLM credential (BYOK or server-key fallback); preflight must verify; no key in repo；
- 环境作用域：process-local for this Judge-only replay only; do not write to repo/.env; restore after replay；
- 不创建 `RagEvaluationRun`；通过 `judge_trace` 走 C3 Service，driver 只汇总 JudgeOutcome。

## 5. 方法与解释边界

- 方法 A：固定 pilot answer/contexts/gold，只切换 Judge Prompt 到 v1.2.0；
- 执行载体：`rag_judge_service.judge_trace(session=None, ...)`，真实走 `_faithfulness_score_v3`、strict 派生、invalid/failed/credential 分类与 metric v3；
- driver 只把 JudgeOutcome 汇总成报告，不重新实现 F 计分，不写 DB，不创建 Run；
- 不调用 WeKnora、不做检索、不生成新答案，adapter/top_k 不参与；
- Q35/Q36 的 fixture 输入来自旧 run；本次只评 Judge 输出，不宣称端到端效果；
- 报告不得把 v1.1.5 旧值写成 v1.2.0 实测，也不得把 Q17/Q32 的预期标签写成实测。

## 6. 预算与调用量（可复算）

| 项 | 值 |
|---|---:|
| 主运行 case 数 | 10 |
| 主运行 Judge 调用 | 30（10 × 3 指标） |
| HG 固定重复 | Q23/Q35/Q36，每条 3 次 |
| HG 额外 case-run | 6 |
| 执行重试 reserve case-run | 1 |
| 最大 case-run | 17 |
| 最大 Judge 调用 | 51 |
| 主运行 input tokens | 117,000 |
| 主运行 output tokens | 17,300 |
| 最大 input tokens | 198,900 |
| 最大 output tokens | 29,410 |
| 预计成本 | CNY 0.45 |
| 上限 | CNY 0.760 |
| **批准 ceiling** | **CNY 1.00** |

Token 估算（保守）：

| 指标 | prompt tokens | fixture tokens | output tokens |
|---|---:|---:|---:|
| faithfulness | 3,200 | 3,500 | 1,500 |
| answer_correctness | 1,000 | 1,800 | 150 |
| answer_relevancy | 700 | 1,500 | 80 |

注：`faithfulness.txt` 为 9,198 bytes（约 3,000 汉字），3,200 tokens 是保守的 prompt 估算，不是 16k tokens；实际以 LLMUsage 为准。

计算过程：

```text
per-case input  = (3200+3500) + (1000+1800) + (700+1500) = 11,700
per-case output = 1500 + 150 + 80 = 1,730
primary calls   = 10 cases * 3 metrics = 30
max calls       = 17 case-runs * 3 metrics = 51
                  (48 planned + 3 execution-retry reserve)
10 cases        = 117,000 input / 17,300 output
17 case-runs    = 198,900 input / 29,410 output
primary cost    = 117000/1000*0.0024 + 17300/1000*0.0096 = 0.44688
max cost        = 198900/1000*0.0024 + 29410/1000*0.0096 = 0.759696
buffered upper  = 0.759696 * 1.20 = 0.9116352 -> ceiling 1.00
```

单价来源：qwen-max public price used by prior project docs (pilot-10-v1.0.0-vs-v1.1.1.md; pilot-10-v1.1.2-gate-final2.md); actual DashScope bill is authoritative。
硬停止：After each case, read actual usage; if cumulative or projected cost exceeds CNY 1.00, or calls exceed 51, stop immediately; no further calls。

## 7. 停止条件与失败处理

| code | 条件 | 动作 |
|---|---|---|
| `preflight_failure` | fixture SHA、10 个 case/answer/contexts/gold、LLM endpoint/model/credential、Prompt/MANIFEST SHA 或 22/22 validation 任一不满足 | 拒绝启动 Judge-only replay；不得跳过 preflight |
| `invalid_contract` | 任一 case/metric 出现 invalid(contract_violation)，包括 schema/subtype/evidence/quote/conflict 违约 | 立即停止；保留已完成结果；不得改 Prompt 或放宽契约后重跑 |
| `failed_execution` | 任一 case/metric 出现 failed(execution) | 同配置最多重试一次；再次失败立即停止 |
| `hg_supported_quote_invalid` | Q23/Q35/Q36 任一 supported claim 的 quote 非逐字、跨片段拼接或引用 answer | 立即停止；不得把 HG quote invalid 当 known diagnostic 放行 |
| `q29_not_skipped` | Q29 的 F 不是 skipped(no_scorable_claims) | 立即停止；不得用 0.0 或其它 skipped 兜底 |
| `unexplained_drop` | 有 baseline 的 case 出现 old - new > 0.10 + 1e-9 的未解释下降 | 停止并人工复核；恰好 0.10 不停止 |
| `second_typo_or_number_change` | 第二次出现 evidence typo、数字/日期/金额改动 | 立即停止 |
| `missing_case_output` | 10 个 case 未全部产出 3 个指标结果，或任一 case 缺 F/C/R | 停止；不得把缺失 case 当 skipped |
| `budget_ceiling` | 累计或预估成本超过 CNY 1.00，或 Judge 调用超过 51 次 | 立即停止；不得追加调用 |
| `fingerprint_mismatch` | prompt SHA / MANIFEST SHA / fixture SHA / schema / metric / model / temperature / max_tokens 与申请不一致 | 拒绝启动或立即停止；不得静默换版本 |
| `activation_drift` | v1.2.0 被设为默认、active=true 或 runtime_active=true | 立即停止；回到 frozen / active=false |

失败处理：

- **invalid**：不重试；保留 invalid_reason 与 validation_errors；停止并复审
- **failed_execution**：同配置最多重试一次；不得改 Prompt/Schema/model
- **skipped**：按 case 语义单独记录；不得把 skipped 当 PASS
- **budget**：达到 CNY 1.00 或 51 次调用即停止；不得追加预算
- **stop**：保留已完成结果与配置快照；不启动 40；重新申请后才可继续
- **no_prompt_tuning**：10 条期间不得改 Prompt、Schema、Service、目标或 stop conditions

## 8. 报告要求

- 使用 docs/repair/phase3e/m1c-c4-report-template.md
- 逐条报告 status、F_coverage、F_strict（仅诊断）、C、R、invalid/skipped/failed、insufficient_count/ratio、known issue
- 逐条写 PASS/FAIL/BLOCKED；Q29 只能按 skipped 语义判定
- HG 3 条（Q23/Q35/Q36）与 provisional 7 条分开，不混算均值
- Q17 标 policy_relationship_target_reapproval；Q35/Q36 标 old run only，不冒充端到端新答案
- 报告写 fixture SHA、target v1.0.2 SHA、final_labels SHA、Prompt SHA、MANIFEST SHA、schema/metric version
- 报告写 model/temperature/max_tokens 与 Judge-only fixture 方法；不写 adapter/top_k 为实测值
- Q23/Q35/Q36 报告 3 次全部结果、median/min/max，不报最好一次
- Q36 的 C 同时报 base 0.5–0.6 与 variant 0.9–1.0，只作诊断，不参与 PASS/FAIL
- 结论只能写 implemented/verified/blocked；不得自行写 accepted

## 9. 边界

- 本文件是申请材料，不是 Judge 运行；未调用模型、未创建 Run
- 方法 A：Judge-only 固定 pilot answer/contexts/gold；不调用 WeKnora、不做检索、不生成新答案
- adapter 与 top_k 不适用；不得把 Judge-only 结果解释为端到端 RAG 效果
- 不激活 v1.2.0；active 保持 false、runtime_active 保持 false
- 不修改默认 RAG_JUDGE_PROMPT_VERSION=v1.0.0
- qwen-max / max_tokens 只作本次 Judge-only replay 的临时进程环境，不写入仓库或长期 .env
- 不修改 Prompt、MANIFEST、Schema、Service、API、DB、migration 022
- 不运行 40 条；10 条通过后才可单独申请 40 条
- 不启动 M2/M3；不把 M1-C/M1-D 标 accepted
- 不把 Q17/Q32 的预期标签写成实测；本申请不含 Q32

## 10. 批准清单

- [ ] 确认方法 A：Judge-only 固定 pilot fixture，不使用端到端 query Run
- [ ] 确认 10 个 cases 与顺序：Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36
- [ ] 确认 v1.2.0 frozen Prompt SHA、MANIFEST SHA、fixture SHA、schema v3、metric v3
- [ ] 确认 Judge 配置：qwen-max / temperature=0.0 / max_tokens=8192 / prompt v1.2.0
- [ ] 确认预算：主运行 30 次、最大 51 次（48 planned + 3 retry reserve）、ceiling CNY 1.00
- [ ] 确认 HG 重复规则与 Q36 C 双报诊断规则
- [ ] 确认停止条件与失败处理
- [ ] 确认不会激活 v1.2.0、不会改默认版本、不会跑 40
- [ ] 批准后才执行 10 条；执行后停下报告

批准后只执行 10 条；执行完停下报告。10 条通过后才单独申请 40 条。
