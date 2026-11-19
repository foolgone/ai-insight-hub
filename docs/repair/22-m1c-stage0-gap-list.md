# M1-C Stage 0：当前代码 vs r2 差距清单

> 状态：审计/设计，只读代码；**不修改业务代码、不创建 migration 022、不跑 Judge**。
> 依据：`19-m1b-003-freeze-draft.md`（r2）、`21-m1b-003-r2-revision-record.md`、`README.md`、`15-phase3e-v1.2.0-schema-service-design.md`。
> 目标：在写 M1-C 代码前，把“r2 契约 → 当前代码 → 差距 → M1-C 动作”逐项对齐。

## 0. 结论

1. **Schema v3 必须纳入 M1-C**，不能留给 M1-B 或另开旁路。当前代码仍是 Schema v2；没有 v1.2.0 版本、没有新 subtype、没有 invalid 状态。
2. **migration 022 是 M1-C 的强制项**：需要新增 `invalid_reason`、`derived_from_result_id`、`invalid` 状态、run 级 `evaluated_items/invalid_items/unprocessed_items`，并提供可回滚路径。
3. **当前代码只有单 F**（`S/(S+U+I)`），没有 `faithfulness_strict`、没有双 result row、没有 invalid 生命周期；`completed_items` 仍把 skipped 算作 completed。
4. 当前测试覆盖 v2 单 F/旧状态；没有 v3、双指标、invalid、双行生命周期、retry 快照、Item 计数测试。
5. 本文件只给差距和方案；Stage 1 测试清单见 `23-m1c-stage1-test-list.md`。

## 1. Schema v3 是否纳入 M1-C

**结论：是，必须纳入。**

| 依据 | 说明 |
|---|---|
| `README.md` §5.2 | M1-C 第一项就是 `Schema v3`：`claim_subtype` 枚举、`support_status` 必填、v1/v2 兼容 |
| r2 §2/§3 | 指标定义依赖 `factual/non_factual` 新子类型；没有 Schema v3，Service 无法区分 `policy_scope`/`doc_scope` |
| r2 §4.7 | invalid 持久化依赖 `invalid_reason`/status；Schema 不升级会产生双重语义 |
| 当前代码 | `JUDGE_V2_PROMPT_VERSIONS` 只到 `v1.1.5`；`JUDGE_SCHEMA_V2` 是最高版本 |

建议 M1-C 内部拆成四个子阶段（仍属 M1-C，不另立里程碑）：

| 子阶段 | 内容 | 退出条件 |
|---|---|---|
| C1 | Schema v3 + loader + v1/v2 兼容 | Schema/loader 单测通过 |
| C2 | Service 双指标 + invalid 契约 | Stage 1 12 条核心测试通过 |
| C3 | migration 022 + 聚合/retry/Item 计数 | migration upgrade/rollback 测试通过 |
| C4 | 目标回归 + 10 条/40 条准备 | 静态目标回归通过；不跑 Judge |

**如果 M1-C 不包含 Schema v3，则 C2/C3 无法实现，应直接阻塞，不允许“先写 Service 再补 Schema”。**

## 2. 逐项差距

| ID | r2 契约 | 当前代码 | 差距 | M1-C 动作 |
|---|---|---|---|---|
| G01 | Schema v3，显式 `schema_version` | `JUDGE_SCHEMA_V2`；`JUDGE_V2_PROMPT_VERSIONS` 到 `v1.1.5` | 无 v3、无 v1.2.0 映射 | 新增 `JUDGE_SCHEMA_V3`、v1.2.0 版本映射；v1/v2 只读解析 |
| G02 | `claim_subtype` 新枚举：fact/process/derived/policy_scope/policy_relationship/doc_scope/doc_relationship/condition/normative_requirement | `FaithfulnessClaim.claim_subtype` 仅 `policy/absence/conflict/advice/meta` | 新类型全部缺失 | 扩展 Literal；明确 factual/non_factual 映射 |
| G03 | 缺/非法 subtype → 整条 `failed(schema)` | `_validate_claims` 把非法 subtype 归一为 `policy`/`meta`，记 error 但不失败 | 默认兜底，契约不硬 | 去掉默认；缺/非法/type 不一致直接 `invalid(contract_violation)` |
| G04 | Metric v3；v1/v2/v3 不混聚合 | `RAG_JUDGE_METRIC_VERSION_V2` 全 v2；无 v3 | 无 metric v3 | 新增 v3；聚合键含 prompt/schema/metric version |
| G05 | `faithfulness` = F_coverage = `S/(S+U+I)` | `rag_judge_service` 单 F = `supported/scorable` | 公式一致，但未命名/未版本化 F_coverage | 保留公式；命名为 coverage；补字段/文档 |
| G06 | `faithfulness_strict` = `S/(S+U)` | 不存在 | 无双指标 | 从同一 claims 派生 strict；不额外调 Judge |
| G07 | S/U/I/N 计数 + strict/coverage | details 有 supported/unsupported/insufficient/non_factual 计数；无 strict | 无双指标 details | 增加 `strict_score`、`insufficient_ratio`、`strict_gap` 等 |
| G08 | 全 insufficient：coverage evaluated 0.0 + all_insufficient；strict skipped(no_decidable_claims) | 单 F 返回 0.0 + `all_insufficient=true`；无 strict | strict 语义缺失 | 增加 strict skip；Item 状态仍 evaluated |
| G09 | 全 non_factual：both skipped(no_scorable_claims) | 单 F skip `no_scorable_claims` | strict 同 skip 未实现 | 两 metric 同 skip |
| G10 | context_unavailable：both skipped | 单 F skip `context_unavailable` | strict 同 skip 未实现 | 两 metric 同 skip；F unavailable |
| G11 | 契约违约：both `invalid(contract_violation)` | 无 invalid；validation error 可能降级/跳过 | 无 invalid 状态 | 新增 invalid；不进入均值 |
| G12 | result status: evaluated/skipped/invalid/failed | CHECK 只有 evaluated/skipped/failed | 缺 invalid | migration 022 扩展 CHECK |
| G13 | `invalid_reason` 结构化 code | 无该列 | 缺列 | migration 022 增加 `invalid_reason` |
| G14 | strict 行 `derived_from_result_id` | 无该列/无 strict 行 | 缺列/缺生命周期 | migration 022 增加自 FK；先写 coverage 再派生 strict |
| G15 | run 计数：evaluated/invalid/unprocessed；completed=evaluated | run 只有 total/completed/skipped/failed；completed 含 skipped | 计数语义错误 | 增加 evaluated/invalid/unprocessed；completed 由 evaluated 驱动 |
| G16 | finalize：completed=evaluated；invalid 独立；completion/success 分开 | `finalize_run` 的 completed = all_present and not failed（含全 skipped） | 完成率虚高 | 重写 finalize；invalid 优先于 evaluated；unprocessed 单列 |
| G17 | aggregate：invalid 独立；双 metric；Item 不按 row 翻倍 | `build_aggregate` 只 evaluated/skipped/failed；无 invalid/strict | 聚合缺项 | 增加 invalid/strict；按 dataset_item_id 分组 |
| G18 | retry 复制父快照；Prompt/Schema 变化拒绝 retry | `retry_run` 调 `build_judge_config` 当前指纹，并更新 retrieval env | 与 Run 不可变冲突 | 复制父 `judge_config/config_snapshot`；版本变化拒绝 retry |
| G19 | API：invalid_reason/derived_from/evaluated/invalid/unprocessed/strict | `RagEvaluationResultRead`/`RunRead`/`MetricAggregate` 缺字段 | API 缺契约 | 扩展 response schema；不破坏旧字段 |
| G20 | expected_metrics 含 strict；retry 候选检查 strict | `expected_metrics` 只有 retrieval+judge；retry 不检查 strict | 缺 strict 预期 | 加 strict 派生预期；retry 缺 strict 也重试 |
| G21 | migration 022 | 最新 021 `d4e8b1c6f902` | 022 不存在 | 见 §3 |
| G22 | Stage 1 测试 | 现有 v2 测试：单 F、旧 subtype、无效 subtype 归一 | 无 v3/dual/invalid/lifecycle | 按 `23-...` 写测试 |
| G23 | v1.2.0 Prompt/Schema 版本 | 无 v1.2.0 目录/版本 | 无版本 | M1-C 创建（仅 design_draft，不激活） |
| G24 | 目标映射 F→coverage | active target v1.0.2 存在；代码未读取 target | 不是 runtime 输入 | 测试 fixture 使用 target 表；不写进 Service |

### 2.1 代码证据（只读审计）

| 证据 | 位置 |
|---|---|
| Schema v2；版本只到 v1.1.5 | `backend/app/schemas/agents/rag_judge.py:33-43` |
| 旧 `claim_subtype` 枚举 | `backend/app/schemas/agents/rag_judge.py:92` |
| `claim_type` 空值默认 factual | `backend/app/schemas/agents/rag_judge.py:122-125` |
| 旧 factual/non_factual subtype 集合 | `backend/app/services/rag_judge_service.py:41-44` |
| 非法 subtype 归一为 policy/meta | `backend/app/services/rag_judge_service.py:207-232` |
| supported 无 evidence 降级（已对齐 P1-2） | `backend/app/services/rag_judge_service.py:373-385` |
| 单 F = supported/scorable；无 strict | `backend/app/services/rag_judge_service.py:581-601` |
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

### 3.1 升级（upgrade）

Revision：`022_m1c_dual_faithfulness`，`down_revision="d4e8b1c6f902"`。

**Step 1：result 表**

1. drop 旧 CHECK `rag_eval_result_status_valid`。
2. add `invalid_reason VARCHAR(80) NULL`。
3. add `derived_from_result_id UUID NULL`，自 FK → `rag_evaluation_results.id`，`ON DELETE CASCADE`。
4. add 新 CHECK：
   - `status IN ('evaluated','skipped','invalid','failed')`
   - `status <> 'invalid' OR invalid_reason IS NOT NULL`
5. create index `idx_rag_evaluation_results_derived_from`。

**Step 2：run 表**

1. add `evaluated_items INTEGER NOT NULL DEFAULT 0`。
2. add `invalid_items INTEGER NOT NULL DEFAULT 0`。
3. add `unprocessed_items INTEGER NOT NULL DEFAULT 0`。
4. 回填（只回填新列，**不改写旧 `completed_items`**）：
   - `invalid_items = 0`（旧数据无 invalid）；
   - `unprocessed_items = GREATEST(total_items - distinct_item_count, 0)`；
   - `evaluated_items =` 无 failed 且至少一条 evaluated 的 distinct item 数。
5. `completed_items` 保持历史值，标记 legacy；新 Service 对新 Run 写入 `completed_items = evaluated_items`。报告/API 以 `evaluated_items` 为准。

**Step 3：不回填 strict**

- 022 不生成历史 strict 行；strict 只在新 Run 或显式派生时创建。
- 不回填避免旧 claims 被重新解释；旧 Run 保持 v2 历史。

**Step 4：验证**

- `alembic upgrade head` 后执行：
  - count status 分布；
  - 检查 `invalid_reason` 仅在 invalid 行；
  - 检查无 orphan strict；
  - 检查 run 计数守恒：`total = evaluated + invalid + failed + skipped + unprocessed`（新 Run）。

### 3.2 回滚（downgrade）

**安全回滚（默认）**：

1. preflight：若存在 `status='invalid'` 或 `metric_name='faithfulness_strict'` 的行，**直接 RAISE EXCEPTION，拒绝回滚**。
2. 无上述行时：
   - drop index/FK；
   - drop `invalid_reason`、`derived_from_result_id`；
   - drop `evaluated_items`、`invalid_items`、`unprocessed_items`；
   - 恢复旧 CHECK `status IN ('evaluated','skipped','failed')`。
3. `completed_items` 未改写，旧数据不丢。

**强制回滚（人工脚本，不在 Alembic 自动执行）**：

1. 先备份：
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
4. 再执行安全回滚步骤。

**回滚风险**：
- 强制回滚会把 invalid 语义降级为 failed；报告不再区分“输出契约无效”和“执行失败”。
- strict 行被删除；F_strict 历史不可恢复（已备份可人工查）。
- 新 Run 的 `completed_items=evaluated` 不会回退为旧语义；这是新语义，不是数据丢失。

## 4. Stage 0 退出条件

- [ ] Schema v3 纳入 M1-C 的 C1，且版本映射明确。
- [ ] migration 022 的 upgrade/downgrade 方案经人工审核。
- [ ] invalid A 方案确认（status=invalid + invalid_reason）。
- [ ] run 计数采用 `evaluated/invalid/unprocessed`，`completed` legacy 说明确认。
- [ ] Stage 1 12 条测试预期结果确认（见 `23-...`）。
- [ ] 仍未创建/激活 v1.2.0，未改业务代码，未跑 Judge。

## 5. 不做

- 不修改 `app/schemas` / `app/services` / `app/agents` / Prompt / API / DB。
- 不创建 022 migration 文件。
- 不创建/激活 v1.2.0。
- 不运行单案例/10/40 Judge。
- 不把本审计当作 M1-C 启动批准。
