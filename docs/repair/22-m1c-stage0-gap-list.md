# M1-C Stage 0：当前代码 vs r2 差距清单

> 状态：审计/设计，只读代码；**不修改业务代码、不创建 migration 022、不跑 Judge**。
> 版本：Stage 0 rev2（2026-11-19，按人工审核 7 项修订）。
> 依据：`19-m1b-003-freeze-draft.md`（r2，指标/生命周期/invalid 的唯一契约来源）、`21-m1b-003-r2-revision-record.md`、`12-judge-semantic-spec.md`（frozen）、`15-phase3e-v1.2.0-schema-service-design.md`（仅 §2.1 子类型表）、`README.md`。
> 目标：在写 M1-C 代码前，把“r2 契约 → 当前代码 → 差距 → M1-C 动作”逐项对齐。

## 0. 结论与审核关闭

### 0.1 结论

1. **Schema v3 必须纳入 M1-C（C1）**；当前代码仍是 Schema v2，不能先写 Service 再补 Schema。
2. **migration 022 采用 A**：独立 `invalid` + `invalid_reason` + `derived_from_result_id`；run 增加 `evaluated_items/invalid_items/unprocessed_items`；回填按 `failed > invalid > evaluated > skipped`。
3. **`completed_items` 采用 A**：022 回填为 `evaluated_items`，旧值备份，回滚恢复；不再一列两义。
4. **Stage 1 十二条核心测试 L01–L12** 对应审核 12 项；T07/T08 为 `invalid`；T11 拆 T11a/T11b；T12 浮点仅附加；v2 降级只在 V01。
5. 本轮仍**不批准** M1-C 启动、migration 022 创建/执行、v1.2.0 创建/激活、Judge 运行。

### 0.2 审核意见关闭表

| # | 审核意见 | 本版处理 | 位置 |
|---|---|---|---|
| 1 | T07/T08 必须是 `invalid`，不得沿用 P1-2 降级 | Stage 1 的 T07/T08 改为 `invalid(contract_violation)`；降级只放 v2 历史兼容测试 V01 | `23-...` §2 |
| 2 | migration 回填必须按 Item 优先级 | 回填按 `failed > invalid > evaluated > skipped`，并重算四类 Item 计数 | §3.1 |
| 3 | `completed_items` 不得一列两义 | 采用 A：022 回填 `completed_items = evaluated_items`；旧值备份，回滚恢复 | §3.1 / §3.2 |
| 4 | 目标 SHA 引用错误 | Stage 1 目标改为 `pilot-40-targets-v1.2.0-v1.0.2.json`（`3ee15dfc…`）；`34357b34…` 只读 | `23-...` §3 |
| 5 | Schema v3 子类型权威来源不清 | 新增 §1.1：子类型以 `12-judge-semantic-spec.md` §3.1/§3.2 为准，`15-...` §2.1 只做 Schema 映射；指标/生命周期冲突时 r2 优先 | §1.1 |
| 6 | retry 语义写反 | 明确：默认 Prompt/Schema 漂移**不阻止** retry；只有显式换配置或父快照不可用才拒绝 retry | G18 / `23-...` L01–L03 |
| 7 | 不得残留旧 A 口径 | 删除“supported 无 evidence 降级（已对齐 P1-2）”；v3 证据违约统一 `invalid`；不再用单指标作为目标口径 | §2 / §2.1 |

## 1. Schema v3 是否纳入 M1-C

**结论：是，必须纳入。**

| 依据 | 说明 |
|---|---|
| `README.md` §5.2 | M1-C 第一项就是 `Schema v3`：`claim_subtype` 枚举、`support_status` 必填、v1/v2 兼容 |
| r2 §2/§3 | 指标定义依赖 `factual/non_factual` 分桶；没有 Schema v3，Service 无法区分 `policy_scope`/`doc_scope` |
| r2 §4.7 | invalid 持久化依赖 `invalid_reason`/status；Schema 不升级会产生双重语义 |
| 当前代码 | `JUDGE_V2_PROMPT_VERSIONS` 只到 `v1.1.5`；`JUDGE_SCHEMA_V2` 是最高版本 |

建议 M1-C 内部拆成四个子阶段（仍属 M1-C，不另立里程碑）：

| 子阶段 | 内容 | 退出条件 |
|---|---|---|
| C1 | Schema v3 + loader + v1/v2 兼容 | Schema/loader 单测通过 |
| C2 | Service 双指标 + invalid 契约 | Stage 1 十二条核心测试 + 附加契约测试通过 |
| C3 | migration 022 + 聚合/retry/Item 计数 | migration upgrade/rollback 测试通过 |
| C4 | 目标回归 + 10 条/40 条准备 | 静态目标回归通过；不跑 Judge |

**如果 M1-C 不包含 Schema v3，则 C2/C3 无法实现，应直接阻塞，不允许“先写 Service 再补 Schema”。**

### 1.1 Schema v3 子类型冻结说明（M1-C 实现依据）

> 本节回答审核第 5 项：`condition` / `normative_requirement` 等子类型是否已批准。
> **本节即 M1-C 的 Schema v3 子类型冻结说明**：子类型语义来自已 frozen 的 `12-judge-semantic-spec.md`，`15-...` §2.1 只提供同一份表的 Schema 映射，不引入新语义；不依赖 `15-...` 的历史指标段落。

**权威来源（按主题）：**

| 主题 | 权威来源 |
|---|---|
| 子类型语义 | `12-judge-semantic-spec.md` §3.1 / §3.2（2026-11-18 frozen） |
| Schema v3 枚举映射 | `15-phase3e-v1.2.0-schema-service-design.md` §2.1（只做映射，不引入新语义） |
| 指标公式 / 生命周期 / invalid / Item 计数 | `19-m1b-003-freeze-draft.md`（r2）§3/§4 |

**冲突处理：**

- 子类型名称/归属以 `12` 为准，`15` §2.1 只负责 Schema 映射；
- 指标公式、分母、状态、invalid、Item 计数以 r2 为准；
- `15-...` §1.3/§1.4/§3.1 的单指标公式、“insufficient 不进 F 分母”等文字是 **M1-B-002 历史设计**，**不是 v3 实现依据**；v3 必须使用 r2 的 `F_coverage = S/(S+U+I)` 与 `F_strict = S/(S+U)`；
- `12-judge-semantic-spec.md` §9/§10 的状态表仍使用历史标签 `failed(schema)` / `supported_without_evidence` 降级；**v3 状态与 invalid 契约以 r2 §3.3/§4.5/§4.7 为准**，`12` 只用于子类型语义与判定顺序。

**Schema v3 子类型表（冻结）：**

| `claim_type` | `claim_subtype` | 是否进 F_coverage 分母 |
|---|---|---|
| `factual_claim` | `policy` | 是（有 factual 断言时） |
| `factual_claim` | `condition` | 是 |
| `factual_claim` | `normative_requirement` | 是 |
| `factual_claim` | `fact` | 是 |
| `factual_claim` | `process` | 是 |
| `factual_claim` | `derived` | 是 |
| `factual_claim` | `policy_scope` | 是；无依据时 `insufficient_evidence`，不得转 non_factual |
| `factual_claim` | `policy_relationship` | 是；无依据时 `insufficient_evidence`，不得转 non_factual |
| `factual_claim` | `conflict` | 是（只在回答披露文档冲突时） |
| `non_factual` | `absence` | 否 |
| `non_factual` | `doc_scope` | 否 |
| `non_factual` | `doc_relationship` | 否 |
| `non_factual` | `uncertainty` | 否 |
| `non_factual` | `meta` | 否 |
| `non_factual` | `advice` | 否 |
| `non_factual` | `greeting` | 否 |

> **分母提醒**：`insufficient_evidence` 是 factual，仍进 `F_coverage = S/(S+U+I)` 的 I 桶；只是不进 `F_strict = S/(S+U)`。这正是 r2 与旧 M1-B-002 的差异，不得沿用“insufficient 不进 F 分母”的旧口径。

**硬规则：**

- `claim_type` 必填；`claim_subtype` 必填且必须在对应枚举内；
- factual 必须有 `support_status`；non_factual 必须为 null；
- v3 canonical evidence 字段是 `evidence_refs`（`{context_id, quote}`）；`evidence` 字符串数组只用于 v1/v2 解析；
- 缺 subtype / 非法 subtype / type 不一致 / `supported` 无 evidence / `context_id` 不存在 / quote 非逐字 / quote 引用 answer → **整条 metric `invalid(contract_violation)`**，无分数；
- `conflict` 必须有两条互不为子串的 evidence；否则 `conflict_single_sided_evidence` → 整条 invalid；
- 重复 `claim_id` 保留首条并记 `duplicate_claim_id`，不因重复整条 invalid；
- Service 禁止语义纠正（不得把 `policy_scope` 猜成 `meta`，也不得把 factual 改成 non_factual）。

## 2. 逐项差距

| ID | r2 契约 | 当前代码 | 差距 | M1-C 动作 |
|---|---|---|---|---|
| G01 | Schema v3，显式 `schema_version` | `JUDGE_SCHEMA_V2`；`JUDGE_V2_PROMPT_VERSIONS` 到 `v1.1.5` | 无 v3、无 v1.2.0 映射 | 新增 `JUDGE_SCHEMA_V3`、v1.2.0 版本映射；v1/v2 只读解析 |
| G02 | `claim_subtype` 使用 §1.1 冻结表 | `FaithfulnessClaim.claim_subtype` 仅 `policy/absence/conflict/advice/meta` | 缺 `condition/normative_requirement/fact/process/derived/policy_scope/policy_relationship/doc_scope/doc_relationship/uncertainty/greeting`；已有类型语义也需复核 | 按 §1.1 扩展 Literal；校验 type/subtype 一致性 |
| G03 | 缺/非法 subtype / type 不一致 → `invalid(contract_violation)` | `_validate_claims` 把非法 subtype 归一为 `policy`/`meta`，记 error 但不失败 | 默认兜底，契约不硬 | 去掉默认；缺/非法/type 不一致直接 `invalid(contract_violation)`，无分数、不进均值 |
| G04 | Metric v3；v1/v2/v3 不混聚合 | `RAG_JUDGE_METRIC_VERSION_V2` 全 v2；无 v3 | 无 metric v3 | 新增 v3；聚合键含 prompt/schema/metric version |
| G05 | `faithfulness` = F_coverage = `S/(S+U+I)` | 只有 `faithfulness` 一条指标，按 `supported/scorable` 计分 | 公式数值一致，但未命名/未版本化 F_coverage | 保留公式；命名为 coverage；补字段/文档 |
| G06 | `faithfulness_strict` = `S/(S+U)` | 不存在 | 无双指标 | 从同一 claims 派生 strict；不额外调 Judge |
| G07 | S/U/I/N 计数 + strict/coverage | details 有 supported/unsupported/insufficient/non_factual 计数；无 strict | 无双指标 details | 增加 `strict_score`、`insufficient_ratio`、`strict_gap` 等 |
| G08 | 全 insufficient：coverage evaluated 0.0 + all_insufficient；strict skipped(no_decidable_claims) | 单指标返回 0.0 + `all_insufficient=true`；无 strict | strict 语义缺失 | 增加 strict skip；Item 状态仍 evaluated |
| G09 | 全 non_factual：both skipped(no_scorable_claims) | 单指标 skip `no_scorable_claims` | strict 同 skip 未实现 | 两 metric 同 skip |
| G10 | context_unavailable：both skipped | 单指标 skip `context_unavailable` | strict 同 skip 未实现 | 两 metric 同 skip；F unavailable |
| G11 | 契约违约：both `invalid(contract_violation)` | 无 invalid；validation error 可能降级/跳过 | 无 invalid 状态 | 新增 invalid；不进入均值 |
| G12 | result status: evaluated/skipped/invalid/failed | CHECK 只有 evaluated/skipped/failed | 缺 invalid | migration 022 扩展 CHECK |
| G13 | `invalid_reason` 结构化 code | 无该列 | 缺列 | migration 022 增加 `invalid_reason` |
| G14 | strict 行 `derived_from_result_id` | 无该列/无 strict 行 | 缺列/缺生命周期 | migration 022 增加自 FK；先写 coverage 再派生 strict |
| G15 | run 计数：evaluated/invalid/unprocessed；completed=evaluated | run 只有 total/completed/skipped/failed；completed 含 skipped | 计数语义错误 | 增加 evaluated/invalid/unprocessed；completed 由 evaluated 驱动 |
| G16 | finalize：completed=evaluated；invalid 独立；completion/success 分开 | `finalize_run` 的 completed = all_present and not failed（含全 skipped） | 完成率虚高 | 重写 finalize；invalid 优先于 evaluated；unprocessed 单列 |
| G17 | aggregate：invalid 独立；双 metric；Item 不按 row 翻倍 | `build_aggregate` 只 evaluated/skipped/failed；无 invalid/strict | 聚合缺项 | 增加 invalid/strict；按 dataset_item_id 分组 |
| G18 | retry 复制父快照；**默认 Prompt/Schema 漂移不影响 retry**；显式换配置或父快照不可用才拒绝 retry | `retry_run` 调 `build_judge_config` 当前指纹，可能取到新默认 | 与 Run 不可变冲突 | 复制父 `judge_config/config_snapshot/retrieval_config/item_selection`；显式换配置/父快照不可用 → 拒绝 retry，新建 Run |
| G19 | API：invalid_reason/derived_from/evaluated/invalid/unprocessed/strict | `RagEvaluationResultRead`/`RunRead`/`MetricAggregate` 缺字段 | API 缺契约 | 扩展 response schema；不破坏旧字段 |
| G20 | expected_metrics 含 strict；retry 候选检查 strict | `expected_metrics` 只有 retrieval+judge；retry 不检查 strict | 缺 strict 预期 | 加 strict 派生预期；retry 缺 strict 也重试 |
| G21 | migration 022 | 最新 021 `d4e8b1c6f902` | 022 不存在 | 见 §3 |
| G22 | Stage 1 测试 | 现有 v2 测试：单指标、旧 subtype、无效 subtype 归一 | 无 v3/dual/invalid/lifecycle | 按 `23-...` 写测试 |
| G23 | v1.2.0 Prompt/Schema 版本 | 无 v1.2.0 目录/版本 | 无版本 | M1-C 创建（仅 design_draft，不激活） |
| G24 | 目标映射 F→coverage | active target v1.0.2 存在；代码未读取 target | 不是 runtime 输入 | 测试 fixture 使用 target 表；不写进 Service |
| G25 | 证据契约违约 → `invalid(contract_violation)` | v2 历史：`supported` 无 evidence、quote 非逐字、context 不存在、引用 answer 会降级为 `insufficient_evidence` 并继续计分 | 若只加 v3 版本号而不改证据校验，v3 仍会降级，契约不硬 | v3 去掉降级；整条 invalid，无分数、不进均值；降级只允许出现在 v2 历史兼容测试 |

> **Retry 语义澄清**：r2 §4.6.3 的“若 Prompt/Schema 已变化，拒绝 retry”指**父快照版本不可用**或**调用方显式换配置**，不是“当前默认值发生漂移”。默认漂移时 retry 仍复制父快照（r2 §4.2）；只有父快照不可用/显式换配置才拒绝 retry、要求新建 Run。

### 2.1 代码证据（只读审计）

| 证据 | 位置 |
|---|---|
| Schema v2；版本只到 v1.1.5 | `backend/app/schemas/agents/rag_judge.py:33-43` |
| 旧 `claim_subtype` 枚举 | `backend/app/schemas/agents/rag_judge.py:92` |
| `claim_type` 空值默认 factual | `backend/app/schemas/agents/rag_judge.py:122-125` |
| 旧 factual/non_factual subtype 集合 | `backend/app/services/rag_judge_service.py:41-44` |
| 非法 subtype 归一为 policy/meta | `backend/app/services/rag_judge_service.py:207-232` |
| v2 历史：`supported` 无 evidence 会被降级为 insufficient（v3 禁止沿用） | `backend/app/services/rag_judge_service.py:373-385` |
| 只有 `faithfulness` 一条指标，按 `supported/scorable` 计分；无 strict | `backend/app/services/rag_judge_service.py:581-601` |
| result status 只有三个 | `backend/app/models/rag_evaluation.py:124` |
| result 无 invalid_reason/derived_from_result_id | `backend/app/models/rag_evaluation.py:155-174` |
| run 计数无 evaluated/invalid/unprocessed | `backend/app/models/rag_evaluation.py:102-105` |
| retry 用当前指纹 | `backend/app/services/rag_evaluation_service.py:100-128, 357-405` |
| finalize completed 含 skipped | `backend/app/services/rag_evaluation_service.py:545-605` |
| aggregate 无 invalid/strict | `backend/app/services/rag_evaluation_service.py:450-540` |
| API 缺新字段 | `backend/app/schemas/rag_evaluation.py:86-163` |
| 021 status CHECK | `backend/migrations/versions/20261114_1800_d4e8b1c6f902_021_rag_evaluation.py:211-232` |
| 当前 v2 测试覆盖 | `backend/tests/unit/test_rag_judge_v2_scoring.py`、`test_rag_evaluation_rules.py` |

## 3. Migration 022：升级 / 回滚方案

> 当前最新 migration：`d4e8b1c6f902`（021）。022 为**设计**，本轮不创建文件、不执行。
> 采用 r2 §4.7 的 **A 方案**：独立 `invalid` 状态 + `invalid_reason`。
> `completed_items` 采用 **A 方案**：022 回填为 `evaluated_items`，全库统一语义；旧值备份，回滚恢复。

### 3.1 升级（upgrade）

Revision：`022_m1c_dual_faithfulness`，`down_revision="d4e8b1c6f902"`。

**Step 1：result 表**

1. drop 旧 CHECK `rag_eval_result_status_valid`（`IF EXISTS`）。
2. add `invalid_reason VARCHAR(80) NULL`。
3. add `derived_from_result_id UUID NULL`，自 FK → `rag_evaluation_results.id`，`ON DELETE CASCADE`。
4. add 新 CHECK `rag_eval_result_status_m1c`：
   - `status IN ('evaluated','skipped','invalid','failed')`
   - `status <> 'invalid' OR invalid_reason IS NOT NULL`
   - `invalid_reason IS NULL OR status IN ('invalid','failed')`
5. create index `idx_rag_evaluation_results_derived_from`。

> 同步更新 ORM `RagEvaluationResult.__table_args__` 的 status CHECK；建议模型侧与 DB 侧统一使用新约束名 `rag_eval_result_status_m1c`（021 的 DB 约束名是 `rag_eval_result_status_valid`，模型侧原是 `status_valid`），避免 `metadata.create_all` 与 Alembic 产生两套约束。

**Step 2：run 表**

1. add `evaluated_items INTEGER NOT NULL DEFAULT 0`。
2. add `invalid_items INTEGER NOT NULL DEFAULT 0`。
3. add `unprocessed_items INTEGER NOT NULL DEFAULT 0`。
4. 备份旧 `completed_items`：
   ```sql
   CREATE TABLE rag_evaluation_runs_022_completed_backup AS
   SELECT id, completed_items FROM rag_evaluation_runs;
   ```
5. 按 **Item 优先级**回填四类计数：
   ```sql
   WITH run_expected AS (
       SELECT
           id AS run_id,
           (
               CASE WHEN jsonb_typeof(config_snapshot -> 'metrics') = 'array'
                    THEN jsonb_array_length(config_snapshot -> 'metrics') ELSE 0 END
               +
               CASE WHEN jsonb_typeof(config_snapshot -> 'judge_metrics') = 'array'
                    THEN jsonb_array_length(config_snapshot -> 'judge_metrics') ELSE 0 END
           ) AS expected_metric_count
       FROM rag_evaluation_runs
   ),
   item_state AS (
       SELECT
           r.run_id,
           r.dataset_item_id,
           count(*) AS row_count,
           bool_or(r.status = 'failed')    AS has_failed,
           bool_or(r.status = 'invalid')   AS has_invalid,
           bool_or(r.status = 'evaluated') AS has_evaluated
       FROM rag_evaluation_results AS r
       GROUP BY r.run_id, r.dataset_item_id
   ),
   item_bucket AS (
       SELECT
           s.run_id,
           s.dataset_item_id,
           CASE
               WHEN s.has_failed THEN 'failed'
               WHEN s.has_invalid THEN 'invalid'
               WHEN s.has_evaluated THEN 'evaluated'
               WHEN (
                   e.expected_metric_count = 0
                   AND s.row_count >= 1
               ) OR (
                   e.expected_metric_count > 0
                   AND s.row_count >= e.expected_metric_count
               ) THEN 'skipped'
               ELSE 'unprocessed'
           END AS bucket
       FROM item_state AS s
       JOIN run_expected AS e ON e.run_id = s.run_id
   ),
   run_counts AS (
       SELECT
           run_id,
           count(*) FILTER (WHERE bucket = 'evaluated')   AS evaluated_items,
           count(*) FILTER (WHERE bucket = 'invalid')     AS invalid_items,
           count(*) FILTER (WHERE bucket = 'failed')      AS failed_items,
           count(*) FILTER (WHERE bucket = 'skipped')     AS skipped_items,
           count(*) FILTER (WHERE bucket = 'unprocessed') AS partial_unprocessed,
           count(*) AS distinct_items
       FROM item_bucket
       GROUP BY run_id
   )
   UPDATE rag_evaluation_runs AS run
   SET evaluated_items   = COALESCE(c.evaluated_items, 0),
       invalid_items     = COALESCE(c.invalid_items, 0),
       failed_items      = COALESCE(c.failed_items, 0),
       skipped_items     = COALESCE(c.skipped_items, 0),
       unprocessed_items = GREATEST(run.total_items - COALESCE(c.distinct_items, 0), 0)
                           + COALESCE(c.partial_unprocessed, 0),
       completed_items   = COALESCE(c.evaluated_items, 0)
   FROM run_counts AS c
   WHERE c.run_id = run.id;
   ```
6. 没有任何 result 的 Run：
   ```sql
   UPDATE rag_evaluation_runs AS run
   SET evaluated_items   = 0,
       invalid_items     = 0,
       failed_items      = 0,
       skipped_items     = 0,
       unprocessed_items = run.total_items,
       completed_items   = 0
   WHERE NOT EXISTS (
       SELECT 1 FROM rag_evaluation_results AS r WHERE r.run_id = run.id
   );
   ```

**回填语义（必须按优先级）：**

| 优先级 | Item 状态 | 条件 |
|---|---|---|
| 1 | `failed` | 任一 result 为 `failed` |
| 2 | `invalid` | 无 failed，任一 result 为 `invalid` |
| 3 | `evaluated` | 无 failed/invalid，任一 result 为 `evaluated` |
| 4 | `skipped` | 无 failed/invalid/evaluated，且 `row_count >= expected_metric_count`（全部 expected metric 为 skipped） |
| 5 | `unprocessed` | 没有任何 result row，或 `row_count < expected_metric_count`（缺少终态行；pending/running/cancelled） |

- `expected_metric_count = jsonb_array_length(config_snapshot.metrics) + jsonb_array_length(config_snapshot.judge_metrics)`；配置缺失时退回“有任意 row 即视为全覆盖”的保守规则。
- 部分行（例如 coverage skipped、strict 缺失）属于 `unprocessed`，不得因为“已有 skipped 行”就算 `skipped`。
- 旧数据没有 `invalid`，所以 `invalid_items = 0`；但 SQL 仍按优先级写，保证 022 之后可重复执行/可验证。
- `failed_items` / `skipped_items` 也按 Item 优先级重算，保证守恒关系成立。
- `completed_items = evaluated_items`（A 方案），不再保留“含 skipped 的已处理数”语义。
- API 可同时暴露 `completed_items` 与 `evaluated_items`，但二者必须相等；不得一个含 skipped、一个不含。
- 旧值保存在 `rag_evaluation_runs_022_completed_backup`，只用于回滚。

**Step 3：不回填 strict**

- 022 不生成历史 strict 行；strict 只在新 Run 或显式派生时创建。
- 不回填避免旧 claims 被重新解释；旧 Run 保持 v2 历史。

**Step 4：验证**

- `alembic upgrade head` 后执行：
  - 检查 `invalid_reason` 仅在 invalid 行；
  - 检查无 orphan strict；
  - 检查每个 Run：`total_items = evaluated_items + invalid_items + failed_items + skipped_items + unprocessed_items`；
  - 检查每个 Run：`completed_items = evaluated_items`；
  - 检查旧 v1/v2 行的 `metric_version` 未被改写。

### 3.2 回滚（downgrade）

**安全回滚（默认）：**

1. preflight：
   - 若存在 `status='invalid'` 或 `metric_name='faithfulness_strict'` 的行，**直接 RAISE EXCEPTION，拒绝回滚**；
   - 若 `rag_evaluation_runs_022_completed_backup` 不存在，RAISE EXCEPTION（无法恢复旧 `completed_items`）。
2. 恢复旧 `completed_items`：
   ```sql
   UPDATE rag_evaluation_runs AS run
   SET completed_items = backup.completed_items
   FROM rag_evaluation_runs_022_completed_backup AS backup
   WHERE backup.id = run.id;
   ```
3. drop index/FK；
4. drop 新 CHECK `rag_eval_result_status_m1c`；
5. drop `invalid_reason`、`derived_from_result_id`；
6. drop `evaluated_items`、`invalid_items`、`unprocessed_items`；
7. 恢复旧 CHECK `status IN ('evaluated','skipped','failed')`（name `rag_eval_result_status_valid`）；
8. drop `rag_evaluation_runs_022_completed_backup`。

**强制回滚（人工脚本，不在 Alembic 自动执行）：**

1. 先备份 invalid/strict 行：
   ```sql
   CREATE TABLE rag_evaluation_results_022_archive AS
   SELECT * FROM rag_evaluation_results
   WHERE status = 'invalid' OR metric_name = 'faithfulness_strict';
   ```
2. `invalid` → `failed`：
   ```sql
   UPDATE rag_evaluation_results
   SET status = 'failed',
       error_message = COALESCE(error_message, 'invalid:' || invalid_reason)
   WHERE status = 'invalid';
   ```
3. 删除 strict 行（已备份）：
   ```sql
   DELETE FROM rag_evaluation_results WHERE metric_name = 'faithfulness_strict';
   ```
4. 再执行安全回滚步骤（含 `completed_items` 备份恢复）。

**回滚风险：**

- 强制回滚会把 invalid 语义降级为 failed；报告不再区分“输出契约无效”和“执行失败”。
- strict 行被删除；F_strict 历史不可恢复（已备份可人工查）。
- `completed_items` 从 A 语义恢复为旧值（含 skipped）；这是回滚预期，不是新语义。

## 4. Stage 0 退出条件

- [ ] Schema v3 纳入 M1-C 的 C1，且 §1.1 子类型权威来源确认。
- [ ] migration 022 的 upgrade/downgrade 方案经人工审核。
- [ ] invalid A 方案确认（status=invalid + invalid_reason）。
- [ ] 回填按 `failed > invalid > evaluated > skipped`，并覆盖 `unprocessed`。
- [ ] `completed_items` 采用 A 方案（回填 = evaluated；旧值备份；回滚恢复）。
- [ ] Stage 1 十二条核心测试 + 附加契约测试预期确认（见 `23-...`）。
- [ ] 全文无旧 A 口径：契约违约统一 `invalid`，不把 v2 降级写成 v3 契约，不用单指标作为目标口径。
- [ ] 仍未创建/激活 v1.2.0，未改业务代码，未跑 Judge。

## 5. 不做

- 不修改 `app/schemas` / `app/services` / `app/agents` / Prompt / API / DB。
- 不创建 022 migration 文件。
- 不创建/激活 v1.2.0。
- 不运行单案例/10/40 Judge。
- 不把本审计当作 M1-C 启动批准。
