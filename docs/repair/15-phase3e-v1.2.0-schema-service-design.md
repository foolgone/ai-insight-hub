# v1.2.0 Schema / 子类型 / Service 设计

> 状态：设计草案，等待人工审核。
> 依据：`12-judge-semantic-spec.md`（2026-11-18 frozen）、`pilot-40-final-labels.json`（SHA `f139623f…`）、`pilot-40-targets-v1.2.0.json`（SHA `34357b34…`）。
> 本文不创建/激活 v1.2.0，不修改 Prompt/Service/Schema/API/DB，不运行 Judge。

## 1. 三个版本决策

### 1.1 Schema 版本：`rag_judge_schema_v3`

**决定：v1.2.0 使用 `rag_judge_schema_v3`，不静默复用 v2。**

原因：
- `claim_subtype` 的 Literal 已变化：新增 `fact` / `process` / `derived` / `policy_scope` / `policy_relationship` / `doc_scope` / `doc_relationship`；
- v1.2.0 要求 factual/non_factual 子类型显式；缺失 subtype 是 validation error，不是默认 supported；
- v2 的 `scope/relationship` 语义与 v1.2.0 不同，静默复用会让旧 payload 产生新语义；
- v3 允许 Service 明确分支：factual 进分母，non_factual 不进。

兼容：
- v1.0.0（schema v1）和 v1.1.x（schema v2）的旧 payload 继续可解析；
- v1.2.0 只接受 v3 输出；v3 输出不能回填 v2 聚合；
- 版本映射表：`v1.0.0 → v1`、`v1.1.1–v1.1.5 → v2`、`v1.2.0 → v3`。

### 1.2 Metric 版本：v3

**决定：v1.2.0 的 F/C/R 使用 `metric_version=v3`。**

原因：
- F 的 claim taxonomy、分母语义、non_factual 边界变化；
- 如果继续用 metric v2，v1.1.x 与 v1.2.0 会进入同一聚合；
- C/R 也随语义规范调整（直接回答/额外信息/absence），应同版本隔离。

版本表：

| Prompt | Schema | Metric | 聚合 |
|---|---|---|---|
| v1.0.0 | v1 | v1 | 只与 v1 聚合 |
| v1.1.1–v1.1.5 | v2 | v2 | 只与 v2 聚合 |
| v1.2.0 | v3 | v3 | 只与 v3 聚合 |

任何跨版本均值必须显式分开；报告必须写 `prompt_version + schema_version + metric_version`。

### 1.3 兼容层

- 旧 v1/v2 payload 可解析，但不得伪装成 v3；
- v1.2.0 输出必须显式 `claim_type` + `claim_subtype`；
- 缺失 subtype → validation error，不默认 `policy`，不默认 supported；
- `policy_scope` / `policy_relationship` 必须在分母；Service 不得用“找不到 evidence → 改 non_factual”兜底；
- `doc_scope` / `doc_relationship` / `absence` / `uncertainty` 不进入分母；
- 旧 `scope` / `relationship` 字段只作为 v2 历史解析，不作为 v3 新输出。

## 2. Schema 设计

### 2.1 claim_subtype

| factual_claim | non_factual |
|---|---|
| `policy` | `absence` |
| `condition` | `doc_scope` |
| `normative_requirement` | `doc_relationship` |
| `fact` | `uncertainty` |
| `process` | `meta` |
| `derived` | `advice` |
| `policy_scope` | `greeting` |
| `policy_relationship` | — |
| `conflict` | — |

规则：
- `claim_type` 仍只有 `factual_claim` / `non_factual`；
- `support_status` 仅 factual 有值；non_factual 为 null；
- `conflict` 只在回答披露文档冲突时出现；
- `derived` 证据引用其依据规则的最短连续子串；
- `policy_scope` / `policy_relationship` 无明确依据时 `insufficient_evidence`，不得转 non_factual。

### 2.2 输出示例（结构）

```json
{
  "claim_id": "cl1",
  "claim": "...",
  "claim_type": "factual_claim",
  "claim_subtype": "policy_scope",
  "support_status": "insufficient_evidence",
  "is_contradictory": false,
  "contradiction_with": [],
  "evidence_refs": [],
  "reason": "..."
}
```

### 2.3 必填与校验

- `claim_id` 唯一；重复保留首条，记 `duplicate_claim_id`。
- `claim_type` 必填；`claim_subtype` 必填且必须在对应枚举内。
- factual 必须有 `support_status`；non_factual 必须 null。
- `supported` 必须至少一条 evidence；`insufficient_evidence` 为空数组。
- `conflict` 必须有两条互不为子串的 evidence；否则 `conflict_single_sided_evidence`。
- 缺 subtype / 非法 subtype → `failed(schema)` 或该 claim validation error；不得默认 supported。

## 3. Service 设计

### 3.1 分母

- 只有 `factual_claim` 进入 F 分母。
- `non_factual` 全部排除，不因“看起来像政策”而进分母。
- `policy_scope` / `policy_relationship` 是 factual；Service 不得把它们当 meta。
- `absence` / `doc_scope` / `doc_relationship` / `uncertainty` / `meta` / `advice` / `greeting` 不进入分母。

### 3.2 状态边界

| 状态 | 触发 | 聚合 |
|---|---|---|
| `evaluated` | 有 scorable factual | 进入 |
| `skipped(no_scorable_claims)` | 全部 non_factual | 不进入，单独列 |
| `skipped(context_unavailable)` | 无上下文 | 不进入，单独列 F unavailable |
| `failed(schema)` | 结构化失败 | 不进入 |
| `failed(all_invalid)` | 全部 claim 校验失败 | 不进入 |
| `supported_without_evidence` | supported 无 evidence | 该 claim 失败/降级，按规则 |
| `evidence_validation_failed` | quote 非逐字 | 降级 insufficient，记错误 |

### 3.3 Evidence

- quote 必须来自 contexts，逐字连续子串；允许保留原文标点；不得引用 answer。
- 最短子串优先；跨行保留换行；不得拼主语+谓词。
- `supported` 必须有有效 evidence；无效则降级 `insufficient_evidence`。
- `conflict` 两侧证据去重且互不为子串。
- 重复 `claim_id` 保留首条，后续跳过并记错误。
- 不允许“找不到证据 → 改 non_factual”兜底。

### 3.4 浮点与停止

- `>0.10` 使用 `old - new > 0.10 + 1e-9`；恰好 0.10 不停止。
- 高方差案例按 `13-phase3e-acceptance-plan.md` 重复 3 次。
- 停止条件：schema failed、all invalid、HG supported quote 降级、supported_without_evidence、重复 claim_id/冲突单边、未解释下降 >0.10、第二次 typo/数字改动。

### 3.5 统计与报告

- 分组：Human Gold 13 / provisional 27；不得混算均值。
- `context_unavailable`、C1-only 单独列。
- 报告必须写 `final_labels` SHA、`active target` SHA、F/C/R prompt SHA、schema/metric version。
- Q32 若因 3 个 factual 点被归为 uncertainty/absence 而 F=skipped：按目标未命中处理，不得 skipped 兜底。

## 4. 测试矩阵

### 4.1 负向测试（先写）

1. `policy_scope` 被标 `meta` → validation error / 不得通过。
2. `policy_relationship` 被标 `doc_relationship` → validation error。
3. Q36 “能否退款取决于……”被标 `meta` → 不得通过。
4. `absence` / `uncertainty` 进入 F 分母 → 失败。
5. `doc_scope` / `doc_relationship` 进入分母 → 失败。
6. 缺 `claim_subtype` → validation error，不默认 supported。
7. `supported` 无 evidence → 失败/降级。
8. quote 引用 answer 自身 → `quote_not_found`。
9. quote 跨行拼接/主语+谓词合成 → `quote_not_found`。
10. conflict 单边证据/嵌套 → `conflict_single_sided_evidence`。
11. duplicate claim_id → 保留首条 + 错误。
12. context_unavailable 输出 0 → 失败；应 skipped(context_unavailable)。
13. all invalid 输出 skipped → 失败；应 failed(all_invalid)。
14. 恰好 0.10 触发停止 → 失败；应不停止。
15. Q32 3 个 factual 点被归 uncertainty → 目标未命中，不得 skipped 兜底。

### 4.2 单案例

- Q17：policy_relationship factual → F 0.7–0.9。
- Q30：policy_scope factual → F 0.4–1.0（expected 0.5）。
- Q32：3 factual + uncertainty → F 0.9–1.0；不得 skipped。
- Q36：condition sentence factual + conflict → F 0.8–1.0；variant C 0.9–1.0。

### 4.3 分层与整体

- 先 10 条闸门：Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36。
- 再补 Q33–Q40 与 6 条 baseline；完成 40 条。
- 最后 40 条规模/回归报告；13 HG / 27 provisional 分组；不写 40 条 Human Gold 通过。

## 5. 实施边界

- 本文只设计，不修改 `app/schemas` / `app/services` / `app/agents` / Prompt / API / DB。
- 不创建 `backend/app/prompts/rag_judge/v1.2.0`。
- 不把 v1.2.0 加入运行时版本枚举，不设置默认版本。
- 不运行单案例/10 条/40 条 Judge。
- 任何实现必须等本设计与目标表复核通过。

## 6. 风险与未解决问题

| 风险 | 影响 | 处理 |
|---|---|---|
| Schema v3 迁移 | 旧 payload 误当 v3 | 显式 schema_version 校验；v1/v2 只读解析 |
| Metric v3 聚合 | 与 v1/v2 混算 | 聚合 key 加 prompt/schema/metric version |
| 缺 subtype 默认 supported | 分类漏洞 | validation error；负向测试 |
| policy_scope/relationship 被转 non_factual | F 分母漏项 | Service 禁止 fallback；负向测试 |
| Q32 前提不成立 | 目标未命中 | 按 target miss 记录，不 skipped 兜底 |
| Q14 key_facts 未启用 | C 仍 known non-pass | 保留 non-pass；key_facts 另开设计 |
| Q36 冲突口径未选边 | canonical 不明确 | 只验证披露；业务确认后再选边 |
| 6 条 baseline 缺失 | 40 条不完整 | 先补 baseline；报告注明 |
| 成本/时间 | 无法完成 | 负向测试 → 单案例 → 10 → 40，分阶段签字 |

## 7. 结论

**v1.2.0 的 Schema 应是 v3、Metric 应是 v3；v2 扩展不能承载新的 claim taxonomy 和 non_factual 边界。Service 必须以“factual 进分母、non_factual 排除、缺 subtype 报错、policy scope/relationship 不回退”为硬规则。**
