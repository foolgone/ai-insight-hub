# M1-C C3：Service 双指标 / invalid / 聚合 / retry 设计与变更范围

> 状态：C3 设计/范围报告，待人工审核；**不写代码、不改 Service、不跑 Judge、不创建/激活 v1.2.0**。
> 实现状态：C3 已按本设计完成实现并本地验证（2026-11-20，`implemented/verified`）；本文件仍作为设计与验收依据。
> 版本：C3 设计 rev2.1（2026-11-20，补 credential 异常边界与 failure_kind 枚举）。
> 依据：`19-m1b-003-freeze-draft.md`（r2）、`22-m1c-stage0-gap-list.md`（rev2.1）、`23-m1c-stage1-test-list.md`（rev2.1）、`12-judge-semantic-spec.md`、`15-phase3e-v1.2.0-schema-service-design.md` §2.1。
> 范围：**仅 C3**（Service 双指标、invalid、Item 聚合、retry、聚合/API 映射）。C2 migration 022 已完成；C4 目标回归不在本轮。

## 0. 结论与范围

1. C3 实现 `faithfulness`（F_coverage）+ `faithfulness_strict`（F_strict），strict 从同一 claims 派生，**不额外调用 LLM**。
2. C3 实现 v3 invalid 契约：契约违约 → `invalid(contract_violation)`；执行失败 → `failed(execution)`；两者不混。
3. C3 实现 Item 级聚合：`failed > invalid > evaluated > skipped`，`unprocessed` 只算无任何 row，`completed=evaluated`，五类守恒。
4. C3 实现 retry：复制父 Run 快照；默认 Prompt/Schema 漂移不拒绝；显式换配置或父快照不可用 → 拒绝 retry、新建 Run。
5. C3 不改 Judge Prompt、不创建/激活 v1.2.0、不跑 Judge、不改 C2 migration。

### 0.1 本轮 P0/P1 关闭

| # | 问题 | 处理 |
|---|---|---|
| P0 | invalid/failed 只能解析 errors 字符串 | `AgentResult` 新增 `error_type: str \| None`；`BaseAgent.run` 失败时写入 `type(exc).__name__`；Service 按类型映射 invalid/failed，不再解析字符串 |
| P1-1 | 显式 `judge_prompt_version=v1.2.0` 在 C3 不可运行 | create 时先校验 MANIFEST/Prompt；缺失 → 400/409，不创建 Run；C3 测试只用 tmp fixture/mock |
| P1-2 | `config_snapshot` 未记录 strict | 写入 `derived_metrics=[faithfulness_strict]` 与 `metric_versions[faithfulness_strict]=v3` |
| P1-3 | 聚合缺 insufficient 口径 | `build_aggregate`/`MetricAggregate` 增加 `insufficient_count`、`insufficient_ratio`、`all_insufficient_count` |
| P1-4 | retry 只按 metric 选，可能重跑 invalid F | 改为 **Item 级**：任一 invalid（A/B）→ 整个 Item 不 retry；strict-only → retry 但 Judge 调用 0 |
| P1-5 | credential 异常不经过 AgentResult | `judge_trace` 边界单独 catch `LLMCredentialNotConfiguredError` / `LLMCredentialInvalidError`，生成 failed outcome，不冒泡 500 |

## 1. 当前代码基线

| 位置 | 现状 |
|---|---|
| `app/services/rag_judge_service.py:508-604` | `_faithfulness_score` 只有 v1/v2；v3 在 C1 直接抛 `RagJudgePromptError` |
| `app/services/rag_judge_service.py:607-767` | `judge_trace` 每个请求 metric 调一次 Agent；F 只返回一条 outcome |
| `app/services/rag_evaluation_service.py:136-140` | `expected_metrics = metrics + judge_metrics`，不含 strict |
| `app/services/rag_evaluation_service.py:357-456` | `retry_run` 调 `build_judge_config` 当前指纹，且会刷新 weknora 配置 |
| `app/services/rag_evaluation_service.py:489-542` | `build_aggregate` 只有 evaluated/skipped/failed，无 invalid |
| `app/services/rag_evaluation_service.py:545-606` | `finalize_run` 用 `all_present` 判 skipped/completed；无 invalid/unprocessed 计数 |
| `app/services/rag_evaluation_runner.py:153-332` | 结果行一次性批量写入；没有 coverage ID → strict `derived_from_result_id` |
| `app/services/rag_evaluation_runner.py:335-454` | 父结果复用按 metric；strict 没有派生逻辑 |
| `app/schemas/rag_evaluation.py:155-163` | `MetricAggregate` 无 invalid |
| `app/api/v1/rag_evaluations.py` | Run/Result 新字段已透出（C2）；MetricAggregate 未加 invalid |
| `app/agents/base.py:132-148` | `AgentResult` 无 `error_type`；失败只写 `errors=[type: msg]` |
| `app/agents/base.py:414-430` | 所有异常统一收敛为 `AgentResult(success=False)`，无结构化失败类型 |

## 2. C3 设计

### 2.1 指标与版本

新增派生指标常量：

```python
FAITHFULNESS_STRICT_METRIC = "faithfulness_strict"
RAG_JUDGE_DERIVED_METRICS = (FAITHFULNESS_STRICT_METRIC,)
```

规则：

- `RAG_JUDGE_METRICS` 仍是 `faithfulness/answer_correctness/answer_relevancy`（真正调用 LLM 的指标）；
- `faithfulness_strict` 是派生指标，不加入 `RAG_JUDGE_METRICS`，不进入 Judge Agent 调用；
- `RAG_JUDGE_METRIC_VERSION_V3` 增加 `faithfulness_strict: v3`；
- `metric_version_for_prompt` / `rag_evaluation_service.metric_version_for` 识别 strict，返回 v3；
- v1/v2 不产生 strict；只有 v3 Run 且 `faithfulness` 在 judge_metrics 中才产生。

### 2.2 v3 Faithfulness 计分

C3 新增 `_faithfulness_score_v3(data, contexts)`，返回 coverage + strict 两个结构化结果：

| S | U | I | N | coverage | strict |
|---|---|---|---|---|---|
| >0 | ≥0 | ≥0 | ≥0 | evaluated `S/(S+U+I)` | evaluated `S/(S+U)` |
| 0 | >0 | 0 | ≥0 | evaluated 0.0 | evaluated 0.0 |
| 0 | >0 | >0 | ≥0 | evaluated 0.0 + `unsupported_count>0` | evaluated 0.0 |
| 0 | 0 | >0 | ≥0 | evaluated 0.0 + `all_insufficient=true` | skipped(`no_decidable_claims`) |
| 0 | 0 | 0 | >0 | skipped(`no_scorable_claims`) | skipped(`no_scorable_claims`) |
| 0 | 0 | 0 | 0 | skipped(`no_scorable_claims`) | skipped(`no_scorable_claims`) |
| — | — | — | — | skipped(`context_unavailable`) | skipped(`context_unavailable`) |
| — | — | — | — | invalid(`contract_violation`) | invalid(`contract_violation`) |
| — | — | — | — | failed(`execution`) | failed(`execution`) |

`details` 必须包含：

- `claims`（coverage 行完整；strict 行不重复完整 claims/evidence/raw_output）；
- `supported_count` / `unsupported_count` / `insufficient_evidence_count` / `non_factual_count`；
- `insufficient_ratio`；
- `all_insufficient`；
- `validation_errors` / `evidence_validation`（coverage）；
- `strict_score`、`strict_gap`（coverage-strict，二者 evaluated 时）。

硬规则：

- v3 不做 v2 的“降级”兜底：
  - `supported` 无 evidence → invalid；
  - `context_id` 不存在 → invalid；
  - quote 非逐字/引用 answer → invalid；
  - `conflict` 单边/嵌套 evidence → invalid；
  - 缺/非法 subtype、type 不一致 → invalid（C1 Schema 已拦，Service 再兜）；
  - 重复 `claim_id` → 保留首条 + 记录 `duplicate_claim_id`，不整条 invalid。
- `insufficient_evidence` 是 factual，进 F_coverage 分母（I 桶），不进 F_strict 分母；
- `non_factual` 不进任何分母；
- v1/v2 分支完全不变。

### 2.3 invalid 契约（A/B 共同语义）

Service 新写入统一用 **A**：

```python
status = "invalid"
invalid_reason = "contract_violation"
```

B 作为历史/兼容读取：

```python
status == "failed" and invalid_reason is not None  # 聚合层归 invalid
```

实现要点：

- `AgentResult` 新增 `error_type: str | None`；
- `BaseAgent.run` 失败返回时写入 `error_type=type(exc).__name__`，成功为 `None`；
- `JudgeOutcome.status` 增加 `"invalid"`；
- `JudgeOutcome` 增加 `invalid_reason: str | None` 与 `error_type: str | None`；
- `judge_trace` 只按 `error_type` 分类，不解析 `errors` 字符串；下表同时列出 `AgentResult.error_type` 与 `judge_trace` 边界捕获的 credential 异常类型（后两行不经过 AgentResult）：

| `error_type` | status | `failure_kind` | `invalid_reason` |
|---|---|---|---|
| `AgentOutputError` | `invalid` | `contract` | `contract_violation` |
| `StructuredOutputError` | `invalid` | `contract` | `contract_violation` |
| `AgentInputError` | `failed` | `input_error` | `None` |
| `AgentTimeoutError` | `failed` | `timeout` | `None` |
| `AgentExecutionError` / `AgentDegradedError` | `failed` | `execution` | `None` |
| `LLMCredentialNotConfiguredError` | `failed` | `credential` | `None` |
| `LLMCredentialInvalidError` | `failed` | `credential` | `None` |
| 其它/未知 | `failed` | `unknown` | `None` |

**`failure_kind` 固定枚举**：`contract` / `execution` / `timeout` / `input_error` / `credential` / `unknown`。

**`AgentInputError` 说明**：输入错误不是输出契约违约，因此归 `failed + input_error`，不归 `invalid`；必须在 details 明确记录，不能静默当普通 execution failed。

#### credential 异常边界

`LLMCredentialNotConfiguredError` 与 `LLMCredentialInvalidError` **不会**经过 `AgentResult`：

- `LLMCredentialNotConfiguredError` 在 `BaseAgent.run` 的 try 之前抛出；
- `LLMCredentialInvalidError` 在 BYOK 异常分支 mark_invalid 后直接 re-raise。

因此 C3 必须在 `judge_trace` 调用 Agent 的边界单独 catch：

```python
judge_config = _judge_config(agent, model=None)  # agent 已构造；不依赖 LLM 调用
try:
    result = await agent.judge(...)
except (LLMCredentialNotConfiguredError, LLMCredentialInvalidError) as exc:
    outcomes.append(
        JudgeOutcome(
            metric_name=metric,
            metric_version=agent.metric_version,
            status="failed",
            error_type=type(exc).__name__,
            details={
                "failure_kind": "credential",
                "agent_error_type": type(exc).__name__,
            },
            judge_config=judge_config,
            error_message=str(exc)[:2000],
        )
    )
    continue
```

规则：

- 两种 credential 异常都归 `failed(execution)`，**不是 invalid**；
- 不抛 500/不让任务直接崩；生成 failed outcome，后续 Item/Run 按 failed 计数；
- `failure_kind=credential`、`agent_error_type` 写 result details；
- 不新增 DB 列；
- 测试必须覆盖“未配置 Key”和“Key 失效”两条路径。

- `_invalid_row` 写 `status=invalid` + reason；
- `_failed_row` 只写 execution/timeout/input/credential/unknown failed，不带 invalid_reason；
- `RagEvaluationResult.details` 记录 `failure_kind` 与 `agent_error_type`，不新增 DB 列；
- 聚合/API 识别 A+B，均归 `invalid_items`，不归 `failed_items`。

### 2.4 双指标写入顺序与 derived_from_result_id

一次 Judge → 两条 row：

1. coverage row（`faithfulness`）先写；
2. `flush` 后拿到 coverage `id`；
3. strict row（`faithfulness_strict`）写入：
   - `derived_from_result_id = coverage.id`；
   - 同 `run_id` / `dataset_item_id` / `metric_version` / `schema_version` / `prompt_sha256`；
   - 只存 S/U/I、strict score、reason、judge_config 摘要；
   - 不重复完整 claims/evidence/raw_output；
4. 两条必须在同一事务；
5. 失败传播：
   - coverage invalid → strict invalid，同 reason；
   - coverage failed → strict failed；
   - coverage skipped(context/no_scorable) → strict 同 skip；
   - coverage evaluated all insufficient → strict skipped(no_decidable)；
   - coverage evaluated S/U>0 → strict evaluated。

Runner 落库方案（推荐）：

- `judge_trace` 返回 coverage + strict 两个 `JudgeOutcome`；
- **runner 的 `judge_metrics` 循环只传 F/C/R**，strict 不进入 `judge_trace` 的 metrics；
- runner 先批量写非 strict 行（含 coverage），flush；
- 按 `(run_id, item, 'faithfulness', metric_version)` 查 coverage id；
- 构造 strict row，设置 `derived_from_result_id`，再批量写 strict；
- 幂等：唯一键 + `ON CONFLICT DO NOTHING`；
- 只缺 strict 时：从当前 coverage 派生 strict，不调用 Judge；
- 测试必须断言 strict 不会作为 LLM metric 重复写、Judge 调用次数不增加。

### 2.5 expected_metrics 包含 strict

Run 创建时写：

```json
{
  "judge_metrics": ["faithfulness", "answer_correctness", "answer_relevancy"],
  "derived_metrics": ["faithfulness_strict"],
  "metric_versions": {
    "faithfulness": "v3",
    "faithfulness_strict": "v3",
    "answer_correctness": "v3",
    "answer_relevancy": "v3"
  }
}
```

规则：

- 仅当 `schema_version=v3` 且 `faithfulness` 在 `judge_metrics` 中，才加入 `faithfulness_strict`；
- `derived_metrics` 与 `metric_versions[faithfulness_strict]` **必须写入 config_snapshot**，供 summary/报告/retry 追溯；
- `expected_metrics(run)` = `metrics + judge_metrics + derived_metrics`；
- 兼容旧 v3 快照：如果没有 `derived_metrics`，但 v3 + F，则运行时补 strict；
- `faithfulness_strict` **不写入** `judge_metrics`，避免被当成 LLM 指标；
- `retry_run` / `finalize_run` / `build_aggregate` 全部使用同一 `expected_metrics`；
- 测试必须断言 `config_snapshot.derived_metrics` 和 `metric_versions["faithfulness_strict"]`。

### 2.6 Item 聚合与 Run 计数

Item 状态：

```text
failed   = 任一 row status=failed 且 invalid_reason IS NULL
invalid  = 无 failed，任一 row status=invalid 或 (failed 且 invalid_reason IS NOT NULL)
evaluated = 无 failed/invalid，任一 row status=evaluated
skipped  = 其余（有 row，但无 failed/invalid/evaluated）
unprocessed = 没有任何 row
```

优先级：`failed > invalid > evaluated > skipped`；`unprocessed` 不在优先级内。

计数：

- `total_items` = distinct dataset_item_id；
- `evaluated_items` / `invalid_items` / `failed_items` / `skipped_items` 按上述 Item 状态；
- `unprocessed_items = max(total_items - distinct_items_with_rows, 0)`；
- `processed_items = evaluated + invalid + failed + skipped`；
- `completed_items = evaluated_items`；
- `completion_rate = processed / total`；
- `success_rate = evaluated / total`；
- 守恒：`total = evaluated + invalid + failed + skipped + unprocessed`。

`finalize_run`：

- 不再用 `all_present` 判 skipped；有任一 row 且无 failed/invalid/evaluated → skipped；
- `completed_items = evaluated_items`；
- `invalid_items` 独立；
- Run 状态建议：
  - `cancelled` 保持；
  - `unprocessed>0` → `partial_failed`（time budget 也 partial_failed）；
  - 全部 expected result 都是 execution failed → `failed`；
  - 存在 execution failed 或 invalid → `partial_failed`；
  - 否则 `completed`（允许 skipped）。

`build_aggregate`：

- 每个 metric 行分 evaluated / skipped / invalid / failed；
- mean 只取 `status=evaluated` 且 score 非空；
- 增加 `invalid` 计数；
- F_coverage 额外增加：
  - `supported_count` / `unsupported_count` / `insufficient_count`（所有 evaluated coverage 行的计数之和）；
  - `insufficient_ratio` = `insufficient_count / (supported_count + unsupported_count + insufficient_count)`；分母为 0 → `null`；
  - `all_insufficient_count` = `all_insufficient=true` 的 evaluated 行数；
- `coverage = evaluated / total_items`；
- `items` 增加 `evaluated/invalid/unprocessed/processed/completion_rate/success_rate`；
- B 行在聚合层归 invalid；
- 测试：S=3/U=0/I=2 的单 Item → `insufficient_count=2`、`insufficient_ratio=0.4`、mean 只算 evaluated。

`summary`：

- 每个 metric slot 增加 `invalid`、`insufficient_count`、`insufficient_ratio`、`all_insufficient_count`；
- 同时累计 `supported_count` / `unsupported_count` / `insufficient_count`；ratio 用累计值重算，不平均各 Run 的 ratio；
- weighted_sum 只累计 evaluated；
- strict 与 coverage 分开聚合，不混版本。

### 2.7 retry：复制父快照，显式换配置新建 Run

`retry_run` 改为：

- 复制父 `judge_config` / `config_snapshot` / `retrieval_config` / `item_selection` / dataset 字段；
- **不调用** `build_judge_config()` 取当前默认；
- 不刷新 weknora 配置；
- 校验父 Prompt MANIFEST 仍可加载、`schema_version` / `metric_version` 与父快照一致；
- 不可用 → `RagEvaluationConflictError("父快照不可用，必须新建 Run")`。

候选选择（**Item 级**，不是单纯 metric 级）：

- 对每个 Item 先看全部 expected metric 的结果；
- 任一 expected metric 为 A/B invalid → **整个 Item 不进入 retry**（同配置会重复违约，应新建 Run 修 Prompt）；
- 无 invalid 时，满足任一条件才进入：
  - 缺 coverage / 缺 strict；
  - execution failed（`status=failed` 且 `invalid_reason IS NULL`）；
  - metric_version 过期；
  - 只缺 strict 且 coverage current；
- skipped → 不重试；
- 只缺 strict：子 Run 复制 coverage 后派生 strict，**不调用 Judge**，不复制父 strict。

显式换配置入口：

- 推荐在 `RagEvaluationCreate` 增加可选 `judge_prompt_version`；
- `create_run` 用该字段构建 `judge_config`，走“新建 Run”路径；
- **create 时必须先校验该 Prompt 的 MANIFEST/Prompt 可加载**；缺失/版本不一致 → 400/409，不创建 Run/Task；
- C3 不改 Prompt、不创建 v1.2.0；C3 的 v3 测试只能用 tmp fixture/mock Judge，不得创建 v1.2.0 Run；
- retry API 不提供 Prompt/Schema/模型覆盖参数；调用方要换配置就新建 Run；
- 若人工审核不希望加 API 字段，则退化为“当前默认配置 = 新建 Run 的配置”，retry 仍只复制父快照；但 create 的前置校验仍必须做。

### 2.8 API / Schema

- `MetricAggregate` 增加：
  - `invalid: int = 0`；
  - `insufficient_count: int = 0`；
  - `insufficient_ratio: float | None = None`；
  - `all_insufficient_count: int = 0`；
- `RagEvaluationResultRead` 已有 `invalid_reason` / `derived_from_result_id`（C2）；
- `RagEvaluationRunRead` / `RagEvaluationRunListItem` 已有 `evaluated/invalid/unprocessed_items`（C2）；
- 如批准显式换配置：`RagEvaluationCreate` 增加 `judge_prompt_version: str | None`；
- API/报告标签：
  - `invalid` → “输出契约无效”；
  - `failed(execution)` → “执行失败”；
  - 不得混用。

## 3. 变更文件清单（计划）

| 文件 | 改动 |
|---|---|
| `backend/app/agents/base.py` | `AgentResult.error_type`；失败返回写入 `type(exc).__name__` |
| `backend/app/schemas/agents/rag_judge.py` | strict metric 常量、v3 metric version、metric_version_for_prompt 识别 strict |
| `backend/app/services/rag_judge_service.py` | v3 coverage/strict 计分、invalid 分类、移除 C1 v3 guard、双 outcome |
| `backend/app/services/rag_evaluation_service.py` | expected_metrics/derived_metrics、finalize/aggregate/summary、retry 快照复制、create_run prompt_version |
| `backend/app/services/rag_evaluation_runner.py` | coverage 先写/取 id、strict 派生写入、strict-only 派生、父结果复用 |
| `backend/app/repositories/rag_evaluation.py` | 如需要：coverage id 查询/返回、invalid 过滤辅助 |
| `backend/app/schemas/rag_evaluation.py` | `MetricAggregate.invalid`；可选 `judge_prompt_version` |
| `backend/app/api/v1/rag_evaluations.py` | MetricAggregate invalid 映射；可选 create 字段 |
| `backend/tests/unit/test_rag_judge_v3_scoring.py` | 新增 v3 计分/无效契约 |
| `backend/tests/unit/test_rag_evaluation_v3_rules.py` | 新增 Item 聚合/expected_metrics/retry 规则 |
| `backend/tests/unit/test_agent_result_error_type.py` | 新增 AgentResult.error_type 映射测试 |
| `backend/tests/integration/test_rag_evaluation_v3.py` | 新增双行写入/聚合/API/retry 集成 |
| 现有 v2 测试 | 原样通过；只补 v3 用例 |

**不修改：**

- `backend/migrations/**`（C2 已完成）
- `backend/app/prompts/rag_judge/v1.2.0/**`
- Judge Prompt 文本 / v2 语义
- `19-m1b-003-freeze-draft.md` / D1–D4 / 目标 v1.0.2 / Human Gold
- Judge 运行、v1.2.0 激活、M2/M3

## 4. 测试清单

### 4.1 Stage 1 十二条核心（L01–L12）

| ID | C3 覆盖 |
|---|---|
| L01 | retry 复制父快照；不调用当前 `build_judge_config` |
| L02 | 默认 Prompt 漂移仍复制父快照 |
| L03 | 显式换配置 / 父快照不可用 → 拒绝 retry，新建 Run |
| L04 | 1 Item 双行；coverage 先写，strict `derived_from_result_id` 指向 coverage |
| L05 | evaluated + skipped 聚合；completed=evaluated |
| L06 | evaluated + failed 跨 Metric；F mean 仍取 evaluated 行 |
| L07 | invalid A/B vs execution failed 分离；invalid_items 独立 |
| L08 | 全 insufficient：coverage 0.0 evaluated，strict skipped，Item evaluated |
| L09 | cancelled/timeout：partial item 归 skipped，只有无 row 是 unprocessed |
| L10 | 五类守恒；rows 不等于 cases |
| L11 | mean 排除 invalid/failed/skipped |
| L12 | 历史 v2 Run 兼容；不补 strict；v2/v3 不混算 |

### 4.2 附加公式/契约（F/T）

- F01–F05 + r2 §9.1 11 组 S/U/I/N 参数化；
- T06 缺/非法 subtype → invalid；
- T07 supported 无 evidence → invalid；
- T08 quote/context/answer/conflict 单边 → invalid；
- T09 invalid A/B 持久化；
- T10 只缺 strict 派生，不调用 Judge；
- T11a/T11b retry；
- T12 浮点 0.10 边界；
- V01 仅 v2 历史降级。

### 4.3 C3 补充

| # | 测试 | 预期 |
|---|---|---|
| C3-01 | `expected_metrics`/snapshot v3 + F | 包含 `derived_metrics=[faithfulness_strict]`、`metric_versions[faithfulness_strict]=v3`；不写入 judge_metrics |
| C3-02 | v3 只选 C/R | 不产生 strict |
| C3-03 | 双行写入 | coverage id 存在；strict derived id 正确；同 run/item/version |
| C3-04 | coverage invalid/failed | strict 同状态，不 evaluated |
| C3-05 | strict-only 缺失 | 从 current coverage 派生；Judge 调用次数 0 |
| C3-06 | invalid A/B 聚合 | B 归 invalid_items，不进 failed_items |
| C3-07 | finalize 五类 | completed=evaluated；completion/success 分开 |
| C3-08 | aggregate invalid | mean 排除 invalid；invalid 计数独立 |
| C3-09 | aggregate insufficient | S=3/U=0/I=2 → insufficient_count=2、ratio=0.4、mean 只算 evaluated |
| C3-10 | summary strict | coverage/strict 分开聚合，不混版本 |
| C3-11 | API 响应 | result 有 invalid_reason/derived_from；run 有 counters；aggregate 有 invalid/insufficient |
| C3-12 | retry invalid（Item 级） | 任一 invalid → 整个 Item 不 retry |
| C3-13 | retry failed+invalid 同 Item | 不选中，不重跑 invalid F |
| C3-14 | 显式换配置 | 走新建 Run；retry 不换口径 |
| C3-15 | create 显式 v1.2.0 | MANIFEST 缺失 → 400/409，不创建 Run/Task |
| C3-16 | AgentResult.error_type | Output/Structured → invalid+contract；Timeout → failed+timeout；Execution/Degraded → failed+execution；Input → failed+input_error；未知 → failed+unknown |
| C3-16a | credential 未配置 | `LLMCredentialNotConfiguredError` 在 judge_trace 边界转 failed outcome；不抛 500；details.failure_kind=credential |
| C3-16b | credential 失效 | `LLMCredentialInvalidError` 同上；不归 invalid；`agent_error_type` 可查 |
| C3-17 | strict 不当 LLM metric | runner 的 judge_metrics 不含 strict；Judge 调用次数不增加 |
| C3-18 | Run 全 invalid | `partial_failed`；全 execution failed 才 `failed` |
| C3-19 | v1/v2 回归 | 原有 v2 scoring/聚合测试原样通过 |

## 5. 非目标

- 不修改 migration 022 或 C2 测试（P2 小修另开）；
- 不创建/激活 v1.2.0 Prompt；
- 不运行 Judge；
- 不改 Judge Prompt 文本 / v2 语义；
- 不改 D1–D4、目标、Human Gold；
- 不启动 M2/M3；
- 不宣布 M1-C accepted。

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 失败类型仍靠字符串解析 | `AgentResult.error_type` 结构化；Service 只按类型映射 |
| credential 异常绕过 AgentResult | `judge_trace` 边界 catch 两类 credential 异常，转 failed outcome |
| `StructuredOutputError` 不是 AgentError 子类 | `error_type=StructuredOutputError` 白名单单独映射 invalid |
| create 显式 v1.2.0 触发 500 | create 前置 MANIFEST/Prompt 校验；失败转 400/409，不建 Run |
| snapshot 漏 strict 版本 | 创建时写 `derived_metrics` + `metric_versions[strict]`；测试断言 |
| C4 报告缺 insufficient 解释 | aggregate/API 增加 insufficient_count/ratio/all_insufficient_count |
| retry 重跑 invalid F | Item 级排除：任一 invalid → 整个 Item 不 retry |
| v3 双指标改变 v2 行为 | 全部逻辑按 `schema_version=v3` 分支；v2 路径原样 |
| coverage 先写/取 id 破坏幂等 | 唯一键 + ON CONFLICT；coverage 查询按 run/item/metric/version |
| strict-only retry 误调 Judge | runner 将 strict 从 `judge_metrics` 分离；单测断言调用次数 0 |
| strict 被当 LLM metric 重复写 | runner 只在 strict 派生阶段写；judge_metrics 循环显式排除 |
| B 行在聚合/重试中混入 failed | 统一 helper `is_invalid_result(row)` / `is_execution_failed(row)` |
| 旧 v3 快照无 derived_metrics | `expected_metrics` 运行时回退补 strict |

## 7. 验收与退出

C3 完成时必须提交：

1. 文件清单与 diff stat；
2. L01–L12 + F/T + C3 补充测试结果；
3. `AgentResult.error_type` 映射测试（Output/Structured → invalid；Execution/Timeout/Degraded → failed；Input → failed+input_error）；credential 未配置/失效边界测试（failed+credential，不 500）；
4. v2 scoring / schema loader / 聚合测试原样通过；
4. `pytest -m "not prompt"`、`black`、`flake8`、`mypy app`、`lint-imports`、CI 全绿；
5. 明确声明：未改 Judge Prompt、未跑 Judge、未激活 v1.2.0、未改 C2 migration；
6. 状态只能写 `implemented/verified`，不能写 `accepted`。

## 8. 待人工确认

| # | 选择 | 建议 |
|---|---|---|
| 1 | `AgentResult` 失败类型 | 新增 `error_type`，写入 `type(exc).__name__`；不解析 errors 字符串 |
| 2 | `AgentInputError` 归类 | `failed` + `failure_kind=input_error`，details 记录；不归 invalid（输入错误不是输出契约违约） |
| 3 | `StructuredOutputError` 归类 | 单独按 `error_type` 映射 invalid；不依赖 AgentError 继承 |
| 4 | credential 异常 | `judge_trace` 边界 catch 两类 credential 异常 → failed + `failure_kind=credential`；不 500、不归 invalid |
| 5 | 显式换配置入口 | `RagEvaluationCreate.judge_prompt_version`；create 前置校验 MANIFEST，缺失 400/409 |
| 6 | strict 记录 | `config_snapshot.derived_metrics` + `metric_versions[faithfulness_strict]` |
| 7 | insufficient 聚合 | `MetricAggregate` 增加 count/ratio/all_insufficient_count |
| 8 | invalid 是否重试 | Item 级排除：任一 invalid → 整个 Item 不 retry |
| 9 | Run 状态遇到 invalid | `partial_failed`；全 execution failed 才 `failed` |
| 10 | P2 小修（CHECK 行为测试、downgrade 文案） | C3 不改；另开测试/文案小修 |
