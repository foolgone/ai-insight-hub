# v1.2.0 Schema / 子类型 / Service 设计

> 状态：设计草案；**P1-1 已关闭；P1-2 按 `16-m1b-decision-record.md`（M1-B-002）改为整条 metric `invalid`；目标影响待决策**。本文不创建/激活 v1.2.0，不修改 Prompt/Service/Schema/API/DB，不运行 Judge。
>
> **2026-11-19 更新：人工改选方案 B（F_strict + F_coverage）。本文的单 F 公式（§1.4、§3.1）作为历史设计保留；B 的指标定义、目标映射与待决项见 `18-m1b-dual-metric-design-evaluation.md`（`M1-B-003`，`proposed_pending_human`）。B 冻结前，本文不作为实现依据。**
>
> 依据：`12-judge-semantic-spec.md`（2026-11-18 frozen，原文未改）、`16-m1b-decision-record.md`（M1-B-002）、`pilot-40-final-labels.json`（SHA `f139623f…`）、`pilot-40-targets-v1.2.0.json`（SHA `34357b34…`）。

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
- 缺失 subtype → 整条 metric `invalid`，不默认 `policy`，不默认 supported；
- `policy_scope` / `policy_relationship` 必须保留为 factual；有 supported/unsupported 时进分母，合法 insufficient 时按 insufficient 规则处理，但不得改判 non_factual；Service 不得用“找不到 evidence → 改 non_factual”兜底；
- `doc_scope` / `doc_relationship` / `absence` / `uncertainty` 不进入分母；
- 旧 `scope` / `relationship` 字段只作为 v2 历史解析，不作为 v3 新输出。

### 1.4 实现前置决策（P1-2 定死）

| 决策 | 结果 |
|---|---|
| 缺 `claim_subtype` / 非法 subtype / type 不一致 | **整条 metric `invalid(contract_violation)`**；无分数、不进分母/均值；不默认 subtype、不默认 supported |
| `supported` 但无 evidence | **整条 metric `invalid(contract_violation)`**；不得降级为 `insufficient_evidence` |
| evidence `context_id` 不存在 / quote 非逐字 / 引用 answer | **整条 metric `invalid(contract_violation)`**；不得降级、不得 drop |
| evidence 真实存在但不支持 claim | 正常评价为 `unsupported`；这是语义判断，不是结构违约 |
| 合法的 `insufficient_evidence` | 正常评价；不进 F 分母，单独统计数量和比例 |
| 全部 factual 都 insufficient | `skipped(no_decidable_claims)`；不是 0.0，也不是 `invalid` |
| 全部 claim 都是 non_factual | `skipped(no_scorable_claims)` |
| Service 语义纠正 | **禁止**；Service 只校验 subtype/type/evidence，不猜 policy_scope 或自动改写 |
| 恰好 0.10 | 不停止；`>0.10 + 1e-9` 才停止 |

> F 公式（M1-B-002）：`F = supported / (supported + unsupported)`。`insufficient_evidence` 不进分母，但必须独立统计 `insufficient_count` / `insufficient_ratio`。
>
> 目标影响：该公式会改变 Q21/Q17 等含 insufficient claim 的 F 值，frozen target 尚未按新分母重算；详见 `16-m1b-decision-record.md` §4。目标未重算前，M1-B 只能记为 `implemented`，不能记为 `accepted`。

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

- `claim_id` 唯一；重复保留首条，记 `duplicate_claim_id`（不因重复整条 invalid）。
- `claim_type` 必填；`claim_subtype` 必填且必须在对应枚举内。
- factual 必须有 `support_status`；non_factual 必须 null；违反 → 整条 `invalid`。
- `supported` 必须至少一条有效 evidence；`insufficient_evidence` 的 `evidence_refs` 必须为空；`unsupported` 可带指向矛盾原文的 evidence。违反 → 整条 `invalid`。
- **v3 canonical evidence 字段是 `evidence_refs`（`{context_id, quote}`）**；`evidence`（字符串数组）只用于 v1/v2 解析。v1.2.0 输出 `supported` 但 `evidence_refs` 为空、只有 `evidence` → `invalid`，不得自动迁移。
- `conflict` 必须有两条互不为子串的 evidence；否则 `conflict_single_sided_evidence` → 整条 `invalid`。
- **缺 subtype / 非法 subtype / type 不一致：整条 metric `invalid(contract_violation)`，不产出分数、不进入分母/均值**；不得降级为默认 subtype，也不得默认 supported。
- **`supported` 无 evidence、evidence `context_id` 不存在、quote 非逐字、quote 引用 answer：整条 `invalid(contract_violation)`**；不得降级 `insufficient_evidence`，不得 drop 后继续计分。
- 合法的 `insufficient_evidence` 是正常评价结果，不是 invalid；它不进 F 分母，但必须计入 `insufficient_count` / `insufficient_ratio`。

## 3. Service 设计

### 3.1 分母

- 进入 F 分母：`factual_claim` 且 `support_status ∈ {supported, unsupported}`。
- `non_factual` 全部排除，不因“看起来像政策”而进分母。
- `insufficient_evidence` 是 factual，但**不进分母**；必须独立统计 `insufficient_count` / `insufficient_ratio`，并在报告中单列。不能把它当作 unsupported，也不能把它当作 0 分。
- `policy_scope` / `policy_relationship` 是 factual；**分类由 Prompt/Judge 负责，Service 不做语义纠正**：Service 只校验 subtype 枚举、claim_type 一致性与 evidence，不得用关键词猜“这其实是 policy_scope”并自动改回 factual。
- 如果 Judge 把 policy_scope 标成 meta，这是 Judge acceptance failure；Service 应按收到的 subtype 处理（non_factual 排除），但该 Run 必须在 Judge acceptance 负向测试中失败，不能当 PASS。
- `absence` / `doc_scope` / `doc_relationship` / `uncertainty` / `meta` / `advice` / `greeting` 不进入分母。
- F 公式：`F = supported / (supported + unsupported)`；分母为 0 时按 §3.2 的 skip 处理，不产出 0 分。

### 3.2 状态边界

| 状态 | 触发 | 聚合 |
|---|---|---|
| `evaluated` | 至少一条可判定 factual（supported 或 unsupported） | 进入 |
| `skipped(no_scorable_claims)` | 全部 non_factual | 不进入，单独列 |
| `skipped(no_decidable_claims)` | 全部 factual 都是 `insufficient_evidence` | 不进入，单独列；不是 0.0 |
| `skipped(context_unavailable)` | 无上下文 | 不进入，单独列 F unavailable |
| `invalid(contract_violation)` | 缺/非法 subtype、type 不一致、supported 无 evidence、context_id 不存在、quote 非逐字/引用 answer、conflict 单边 | 不进入，无分数；不得降级后继续计分 |
| `failed(execution)` | Judge 调用失败且重试耗尽 | 不进入，无分数 |

**定死行为**：
- 任何 evidence 契约违约（supported 无 evidence、context_id 不存在、quote 非逐字、引用 answer）→ 整条 `invalid(contract_violation)`；不降级、不 drop、不保留分母。
- 全部 factual 都 `insufficient_evidence` → `skipped(no_decidable_claims)`；不是 0.0，也不是 `invalid`。
- 全部 claim 都结构性无效 → `invalid(contract_violation)`；不再单独保留 `failed(all_invalid)`。
- `unsupported` 是合法评价结果，必须进入分母；`insufficient_evidence` 是合法评价结果，但不进分母。
- `invalid` 与 `failed(execution)` 必须分开：前者是输出违约，后者是执行失败。

### 3.3 Evidence

- quote 必须来自 contexts 的逐字连续子串；允许保留原文标点；不得引用 answer。
- `context_id` 必须存在；不存在 → 整条 `invalid`。
- quote 非逐字或引用 answer → 整条 `invalid`。
- 最短子串优先；跨行保留换行；不得拼主语+谓词。
- `supported` 必须有至少一条有效 evidence；无效 → 整条 `invalid`，不降级。
- evidence 真实存在但不支持 claim → 正常评价为 `unsupported`。
- `conflict` 两侧证据去重且互不为子串；单边/嵌套 → 整条 `invalid`。
- 重复 `claim_id` 保留首条，后续跳过并记 `duplicate_claim_id`；这是记录项，不单独触发 invalid。
- 不允许“找不到证据 → 改 non_factual”兜底。

### 3.4 浮点与停止

- `>0.10` 使用 `old - new > 0.10 + 1e-9`；恰好 0.10 不停止。
- 高方差案例按 `13-phase3e-acceptance-plan.md` 重复 3 次。
- 停止条件：`invalid(contract_violation)`、`failed(execution)`、HG supported quote invalid、重复 claim_id/冲突单边、未解释下降 >0.10、第二次 typo/数字改动。

### 3.5 统计与报告

- 分组：Human Gold 13 / provisional 27；不得混算均值。
- `context_unavailable`、C1-only 单独列。
- `invalid(contract_violation)`、`failed(execution)`、`skipped(no_scorable_claims)`、`skipped(no_decidable_claims)` 分别计数，不得合并成“失败”。
- 每条 evaluated 的 F 必须同时报告 `supported`、`unsupported`、`insufficient` 数量和 `insufficient_ratio`；不得只报 F 分数。
- 报告必须写 `final_labels` SHA、`active target` SHA、F/C/R prompt SHA、schema/metric version。
- Q32 若因 3 个 factual 点被归为 uncertainty/absence 而 F=skipped：按目标未命中处理，不得 skipped 兜底。

## 4. 测试矩阵

### 4.1 Service unit negative（不跑模型）

1. 缺 `claim_subtype` → 整条 `invalid(contract_violation)`，无分数。
2. 非法 `claim_subtype` → `invalid`。
3. `claim_type` 与 subtype 不一致 → `invalid`。
4. `supported` 无 `evidence_refs`（空数组或只有 v1 `evidence`）→ `invalid`，不得降级、不得迁移。
5. evidence `context_id` 不存在 → `invalid`。
6. quote 非逐字 / 引用 answer → `invalid`。
7. conflict 单边/嵌套证据 → `invalid`。
8. 重复 `claim_id` → 保留首条，记 `duplicate_claim_id`；不单独 invalid。
9. `context_unavailable` 输出 0 → 失败；应 `skipped(context_unavailable)`。
10. 全 claim 结构性无效 → `invalid`；不得输出 `skipped` 或 `failed(all_invalid)`。
11. 全部 factual 都 insufficient → `skipped(no_decidable_claims)`；不是 0.0，也不是 invalid。
12. 有 supported + unsupported + insufficient → F 只按 supported/(supported+unsupported) 计算，insufficient 不进分母，但计数/比例必须输出。
13. 恰好 0.10 → 不停止；`>0.10 + 1e-9` 才停止。
14. non_factual 进入分母 → 失败。
15. factual 的 `policy_scope`/`policy_relationship` 被 Service 自动改写成 meta → 失败（Service 不得做语义纠正）。

### 4.2 Judge acceptance negative（跑模型，比对标签）

1. `policy_scope` 被标 `meta` → acceptance fail。
2. `policy_relationship` 被标 `doc_relationship` → acceptance fail。
3. Q36 “能否退款取决于……”被标 `meta` → acceptance fail。
4. `absence` / `uncertainty` 被标 factual → acceptance fail。
5. Q32 三个 factual 点被归 uncertainty → 目标未命中，不得 skipped 兜底。
6. Q17 policy_relationship 被标 non_factual（meta/doc_relationship）→ acceptance fail；合法 insufficient 记录但不改判。
7. Q30 policy_scope 被标 non_factual → acceptance fail；合法 insufficient 记录但不改判。
8. Q21#3 合法 insufficient 必须被保留为 insufficient，不得被 Service 当 invalid 或 unsupported；F 的 insufficient 计数/比例必须出现。

> 这些不是 Service 单测：Service 只看到 `claim_subtype`，无法从文本判断“这句话原本是 policy_scope”。语义标签正确性由 Judge acceptance test 负责。

### 4.3 单案例

> 下列目标来自 frozen target 表；但 F 分母已改为排除 insufficient，Q17/Q21 等目标需按 `16-m1b-decision-record.md` §4 重算后再作为硬门禁。重算前只做观察，不写 PASS/FAIL。
>
> **2026-11-19 注：以上为 A 方案（单 F 排除 insufficient）的说明。B 方案下 `F_coverage` 恢复旧分母，Q21=0.6、Q17=0.8 可复现，目标不需要重算；`F_strict` 只作诊断。见 `18-m1b-dual-metric-design-evaluation.md`。**

- Q17：policy_relationship factual → 旧口径 F 0.7–0.9；新分母下预计 1.0（4 supported / 4 decidable），目标待重算。
- Q21：2 条合法 insufficient → 旧口径 F 0.6（3/5）；新分母下 3/3=1.0，frozen 目标 0.6–0.7 不可达，必须先决策。
- Q30：policy_scope factual → F 0.4–1.0（expected 0.5）。
- Q32：3 factual + uncertainty → F 0.9–1.0；不得 skipped；insufficient 不计入分母，但必须报数量。
- Q36：condition sentence factual + conflict → F 0.8–1.0；variant C 0.9–1.0。

### 4.4 分层与整体

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
| 缺 subtype 默认 supported | 分类漏洞 | 整条 invalid；负向测试 |
| policy_scope/relationship 被转 non_factual | F 分母漏项 | Service 禁止 fallback；负向测试 |
| **F 分母改为排除 insufficient** | **Q21/Q17 frozen target 不可达或越界** | **先按决策记录 §4 重算目标；未重算前不把目标当硬门禁** |
| Q32 前提不成立 | 目标未命中 | 按 target miss 记录，不 skipped 兜底 |
| Q14 key_facts 未启用 | C 仍 known non-pass | 保留 non-pass；key_facts 另开设计 |
| Q36 冲突口径未选边 | canonical 不明确 | 只验证披露；业务确认后再选边 |
| 6 条 baseline 缺失 | 40 条不完整 | 先补 baseline；报告注明 |
| 成本/时间 | 无法完成 | 负向测试 → 单案例 → 10 → 40，分阶段签字 |

## 7. 结论

**v1.2.0 的 Schema 应是 v3、Metric 应是 v3；v2 扩展不能承载新的 claim taxonomy 和 non_factual 边界。Service 必须以“factual 中 supported/unsupported 进分母、insufficient 排除并单独统计、non_factual 排除、缺 subtype/证据违约整条 invalid、policy scope/relationship 不回退”为硬规则。**

**当前状态：设计已按 M1-B-002 改完，但目标表尚未按新 F 分母重算；M1-B 只能记为 `implemented`，不能记为 `accepted`。**
