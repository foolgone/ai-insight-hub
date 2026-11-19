# M1-C C1：Schema v3 设计与变更范围

> 状态：C1 设计/范围报告，待人工审核；**不写代码、不创建 migration、不跑 Judge、不创建/激活 v1.2.0**。
> 依据：`19-m1b-003-freeze-draft.md`（r2）、`22-m1c-stage0-gap-list.md`（rev2.1）、`12-judge-semantic-spec.md` §3.1/§3.2、`15-phase3e-v1.2.0-schema-service-design.md` §2.1。
> 范围：**仅 C1**（Schema v3 注册 + loader + v1/v2 兼容）。C2/C3/C4 不在本轮，不写 Service/migration/API 代码。

## 0. 结论

1. C1 只做 Schema v3 注册、V3 输出模型、loader/agent 选择、v1/v2 兼容。
2. C1 同时注册 `metric_version=v3` 的**版本映射**，但不实现 Service 双指标、invalid、聚合、retry；v1.2.0 不激活，C1 后仍不能跑 Judge。
3. C1 **不创建** `backend/app/prompts/rag_judge/v1.2.0/`；测试用 `tmp_path` 的临时 MANIFEST/Prompt fixture。
4. C1 不改 DB、migration、model、repository、API、Service scoring；这些属于 C2/C3。
5. 推荐**独立 V3 模型**，不改 v1/v2 现有的宽容解析语义，避免 v2 回归。

## 1. 当前基线

### 1.1 代码现状

| 位置 | 现状 |
|---|---|
| `backend/app/schemas/agents/rag_judge.py:33-37` | 只有 `JUDGE_SCHEMA_V1` / `JUDGE_SCHEMA_V2`；`JUDGE_V2_PROMPT_VERSIONS = v1.1.1–v1.1.5` |
| `backend/app/schemas/agents/rag_judge.py:46-48` | `judge_schema_version`：V2 集合内 → v2；其它（含 v1.2.0）→ v1 |
| `backend/app/schemas/agents/rag_judge.py:51-55` | `metric_version_for_prompt`：V2 集合内 → v2；其它 → v1 |
| `backend/app/schemas/agents/rag_judge.py:79-96` | `FaithfulnessClaim` 只有旧 subtype；`claim_type` 默认 factual；无 v3 必填校验 |
| `backend/app/schemas/agents/rag_judge.py:162-166` | `METRIC_OUTPUT_SCHEMAS` 只有一套模型 |
| `backend/app/agents/rag_judge_agent.py:116-118` | `schema_version` 优先取 MANIFEST，否则用版本映射 |
| `backend/app/agents/rag_judge_agent.py:163-168` | 只有 v2 分支补 `context_ids` |
| `backend/app/agents/rag_judge_agent.py:203-212` | `_validate_output` 固定使用 `METRIC_OUTPUT_SCHEMAS[self.metric]` |
| `backend/app/agents/rag_judge_agent.py:226-250` | 只有 v2 repair example；其它走 v1 旧格式 |
| `backend/app/prompts/rag_judge/` | 已有 v1.0.0–v1.1.5；默认 v1.0.0；**无 v1.2.0** |
| `backend/tests/unit/test_rag_judge_v2_schema_loader.py` | 覆盖 v1/v2 版本映射、MANIFEST/SHA、Agent schema |
| `backend/tests/unit/test_rag_judge_v2_scoring.py` | 覆盖 v2 单指标计分与旧 subtype 归一 |

### 1.2 当前行为

- `v1.0.0` / `v1.1.0` → schema v1；`v1.1.1–v1.1.5` → schema v2；未知版本 → v1。
- `v1.2.0` 当前会落到 schema v1 / metric v1；这是 C1 必须修的映射缺口。
- V2 claim 允许旧 subtype、`claim_type` 默认 factual、缺 `support_status` 也能解析；V3 需要更严格。
- 现有 v2 测试全部通过；C1 不能改变这些行为。

## 2. C1 设计

### 2.1 版本注册

新增常量：

```python
JUDGE_SCHEMA_V3 = "rag_judge_schema_v3"
JUDGE_V3_PROMPT_VERSIONS = frozenset({"v1.2.0"})
RAG_JUDGE_METRIC_VERSION_V3 = {
    "faithfulness": "v3",
    "answer_correctness": "v3",
    "answer_relevancy": "v3",
}
```

映射：

| Prompt | Schema | Metric | C1 行为 |
|---|---|---|---|
| `v1.0.0` | v1 | v1 | 不变 |
| `v1.1.0` | v1 | v1 | 不变 |
| `v1.1.1–v1.1.5` | v2 | v2 | 不变 |
| `v1.2.0` | **v3** | **v3** | 新增映射；不激活 Prompt |
| 未知版本 | v1 | v1 | 保持现有兼容行为 |

规则：

1. `judge_schema_version` 先判 v3，再判 v2，最后 v1；未知版本仍回退 v1（不静默当 v3）。
2. `metric_version_for_prompt` 对 v3 prompt 返回 v3；只改版本元数据，不改任何计分逻辑。
3. `JUDGE_V2_PROMPT_VERSIONS` 不变；`v1.2.0` 不得加入 v2 集合。
4. `RagJudgeAgent` 读到的 MANIFEST `schema_version` 必须在 `{v1, v2, v3}` 内；未知值 → `RagJudgePromptError`，不静默降级。

### 2.2 V3 输出模型

推荐**独立模型**，不改现有 `FaithfulnessClaim`：

| 模型 | 用途 |
|---|---|
| `FaithfulnessClaimV3` | v3 claim 的严格结构 |
| `FaithfulnessOutputV3` | v3 faithfulness 输出 |
| `METRIC_OUTPUT_SCHEMAS_V3` | 只有 `faithfulness` 使用 V3；C/R 仍复用现有模型 |
| `output_schema_for(metric, schema_version)` | v3 → V3 模型；v1/v2 → 现有模型 |

`FaithfulnessClaimV3` 字段与校验：

| 字段 | V3 要求 |
|---|---|
| `claim_id` | 建议 C1 保持 `str | None`；重复/缺失的语义留给 C3，不新增 r2 未定义的 invalid 条件 |
| `claim` | 必填，非空 |
| `claim_type` | 必填，`factual_claim` / `non_factual` |
| `claim_subtype` | 必填，且必须在对应枚举内 |
| `support_status` | factual 必填；non_factual 必须为 null |
| `evidence_refs` | `supported` ≥1；`insufficient_evidence` 必须为空；`unsupported` 可带指向矛盾原文的 evidence |
| `evidence` / `supported` | **v3 不接受**；用 `extra="forbid"` 拒绝旧字段，避免“只有 evidence 也当 supported” |
| `is_contradictory` / `contradiction_with` | 默认 false / [] |
| `reason` | 默认空字符串 |

`claim_subtype` 枚举（16 个）：

```text
factual_claim:
  policy, condition, normative_requirement, fact, process,
  derived, policy_scope, policy_relationship, conflict

non_factual:
  absence, doc_scope, doc_relationship, uncertainty, meta, advice, greeting
```

模型级校验（C1 只做结构）：

1. factual + `support_status is None` → invalid；
2. non_factual + `support_status is not None` → invalid；
3. factual `supported` 且 `evidence_refs == []` → invalid；
4. factual `insufficient_evidence` 且 `evidence_refs != []` → invalid；
5. `conflict` 至少 2 条 `evidence_refs`；两条 quote 的子串/嵌套检查留给 C3（需要语义上下文）；
6. `evidence_refs` 的 `context_id` 是否存在、quote 是否逐字，C1 只校验结构；存在性留给 C3（需要 contexts）；
7. `claim_type` / `claim_subtype` 不一致 → invalid；
8. 不默认 `claim_type=factual`，不默认 subtype，不默认 supported。

`FaithfulnessOutputV3`：

- `claims: list[FaithfulnessClaimV3]`；
- `reason: str`；
- 顶层不强制 `extra="forbid"`，避免模型多余说明导致无谓修复；claim 级严格。

### 2.3 Loader / Agent 变更

1. `RagJudgeAgent.__init__`：
   - 读取 MANIFEST `schema_version` 后校验白名单；
   - 否则用 `judge_schema_version(prompt_version)`。
2. `self.output_schema = output_schema_for(metric, self.schema_version)`。
3. `_validate_output` 改为用 `self.output_schema`，不再固定 `METRIC_OUTPUT_SCHEMAS[self.metric]`。
4. `_create_agent`：`schema_version in (JUDGE_SCHEMA_V2, JUDGE_SCHEMA_V3)` 时补 `contexts` + `context_ids`；v1 不变。
5. `_repair_example`：
   - v3 返回含 `claim_type` / `claim_subtype` / `support_status` / `evidence_refs` 的示例；
   - v2 示例保持原样；
   - v1 示例保持原样。
6. `load_prompt_manifest` / `load_judge_prompt` 不改；C1 不创建 v1.2.0 目录。

### 2.4 v1/v2 兼容

- `JUDGE_SCHEMA_V1` / `JUDGE_SCHEMA_V2` 常量不变；
- `JUDGE_V2_PROMPT_VERSIONS` 不变；
- `FaithfulnessClaim` / `FaithfulnessOutput` 不变；
- `METRIC_OUTPUT_SCHEMAS` 保持 v1/v2 默认映射；
- v1/v2 的 `judge_schema_version` / `metric_version_for_prompt` 结果不变；
- 现有 v2 scoring/schema loader 测试必须原样通过；
- C1 不调用 Service，不改变 `rag_judge_service.py` 的任何分支。

## 3. 变更范围（文件清单）

| 文件 | 计划改动 | 风险 |
|---|---|---|
| `backend/app/schemas/agents/rag_judge.py` | 新增 V3 常量、16 subtype 集合、`FaithfulnessClaimV3`、`FaithfulnessOutputV3`、`METRIC_OUTPUT_SCHEMAS_V3`、`output_schema_for`；更新映射与 `__all__` | 中；必须保证 V1/V2 分支不变 |
| `backend/app/agents/rag_judge_agent.py` | 校验 MANIFEST schema 白名单；选择 V3 模型；V3 context_ids；V3 repair example；`_validate_output` 用 `self.output_schema` | 中；只对 v3 生效 |
| `backend/tests/unit/test_rag_judge_schema_v3.py` | 新增 C1 单测（见 §4） | 低 |
| `backend/tests/unit/test_rag_judge_v2_schema_loader.py` | 仅补 `v1.2.0` 映射断言；不改 v2 预期 | 低 |

**明确不修改：**

- `backend/app/services/rag_judge_service.py`
- `backend/app/services/rag_evaluation_service.py`
- `backend/app/models/rag_evaluation.py`
- `backend/migrations/**`
- `backend/app/schemas/rag_evaluation.py`
- `backend/app/api/**`
- `backend/app/prompts/rag_judge/v1.2.0/**`（C1 不创建）
- `19-m1b-003-freeze-draft.md`、D1–D4、目标 v1.0.2、Human Gold/provisional

**预计改动规模**：生产代码约 120–180 行；测试约 200–260 行；无 migration、无 DB、无 API。

## 4. C1 测试清单

| # | 测试 | 预期 |
|---|---|---|
| 1 | `judge_schema_version` 映射 | v1.0.0/v1.1.0→v1；v1.1.1–v1.1.5→v2；v1.2.0→v3；未知→v1 |
| 2 | `metric_version_for_prompt` 映射 | v1.2.0 的 F/C/R→v3；v1.1.x→v2；v1.0.0→v1 |
| 3 | 9 个 factual subtype 解析 | 全部通过；`policy_scope`/`policy_relationship`/`conflict` 可解析 |
| 4 | 7 个 non_factual subtype 解析 | 全部通过；`doc_scope`/`doc_relationship`/`uncertainty`/`greeting` 可解析 |
| 5 | factual 缺 `support_status` | `ValidationError`，不默认 supported |
| 6 | non_factual 带 `support_status` | `ValidationError` |
| 7 | `supported` 无 `evidence_refs` | `ValidationError` |
| 8 | `insufficient_evidence` 带 `evidence_refs` | `ValidationError` |
| 9 | v3 只带旧 `supported`/`evidence` | `ValidationError`，不得自动迁移到 `evidence_refs` |
| 10 | 缺/非法 subtype、type 不一致 | `ValidationError`；不默认 `policy`/`meta` |
| 11 | v1/v2 payload 回归 | 旧 payload 仍可解析；v2 scoring 测试原样通过 |
| 12 | Agent v3 选择 | 临时 v1.2.0 MANIFEST + Prompt fixture → `schema_version=v3`、`output_schema` 为 V3、repair example 含 `evidence_refs` |
| 13 | Agent v2 不变 | v2 `output_schema` 仍为 V2 模型；repair example 仍含 `supported`/`evidence` |
| 14 | 边界 | `PROMPT_DIR/v1.2.0` 不存在；C1 未创建真实 Prompt；显式加载 v1.2.0 会按现有 loader 报 `manifest missing` |

运行命令：

```bash
pytest tests/unit/test_rag_judge_schema_v3.py tests/unit/test_rag_judge_v2_schema_loader.py tests/unit/test_rag_judge_v2_scoring.py -q
```

## 5. 非目标（C1 不做）

- 不创建/执行 migration 022；
- 不修改 `rag_evaluation_results` / `rag_evaluation_runs` 模型或 DB；
- 不实现 `invalid` / `invalid_reason` / `derived_from_result_id` 持久化；
- 不实现 Service 双指标、S/U/I/N 计分、invalid、聚合、retry、Item 计数；
- 不改 `expected_metrics`、API response、前端；
- 不创建/激活 v1.2.0 Prompt；
- 不运行 Judge；
- 不启动 M2/M3；
- 不宣布 M1-C accepted。

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 改 `FaithfulnessClaim` 全局 Literal 导致 v2 回归 | 不改旧模型；新增独立 V3 模型 |
| V3 模型 `extra="forbid"` 让 Judge 多字段触发修复 | v1.2.0 Prompt 明确只输出 V3 字段；修复轮示例用 V3 格式；C3 再评估是否放宽 |
| `v1.2.0` 没有真实 Prompt 目录，Agent 测试无法加载 | 测试用 `tmp_path` MANIFEST/Prompt fixture；生产显式加载 v1.2.0 仍报 manifest missing，符合“不创建/不激活” |
| C1 注册 metric v3，但 Service 仍是单指标 | v1.2.0 不激活；C1 不跑 Service；C3 完成双指标前禁止任何 v1.2.0 Run |
| MANIFEST `schema_version` 未知值 | C1 加白名单校验，未知值直接报错，不静默降级 |
| `conflict` 单边/嵌套 evidence 检查需要语义 | C1 只校验 ≥2 条 `evidence_refs`；子串/嵌套与 context 存在性留给 C3 |

## 7. 验收与退出

C1 完成时必须提交：

1. 文件清单与 diff stat；
2. `pytest` 输出（C1 新测 + v2 回归）；
3. `black` / `flake8` / `mypy` / `lint-imports` 结果；
4. 明确声明：未改 Service/migration/DB/API/Prompt/v1.2.0，未跑 Judge；
5. 状态只能写 `implemented`，不能写 `accepted`。

**C1 退出条件：**

- 14 条 C1 测试通过；
- 现有 v2 schema/scoring 测试原样通过；
- `v1.2.0` 仍无真实 Prompt 目录、未激活；
- 无 DB/migration/API diff；
- 分层契约 `lint-imports` 通过。

## 8. 待人工确认的设计选择

| # | 选择 | 建议 |
|---|---|---|
| 1 | C1 是否注册 `metric_version=v3` 映射 | **是**，只做版本元数据；Service 双指标仍归 C3 |
| 2 | V3 是否用独立模型 + `extra="forbid"` | **是**，避免改 v1/v2 宽容语义 |
| 3 | `claim_id` 是否在 C1 必填 | **否**，C1 保持可选；重复/缺失语义由 C3 按 15 §2.3 处理 |
| 4 | `conflict` 单边/嵌套 evidence 是否 C1 做 | **否**，C1 只校验 ≥2 条 refs；语义检查 C3 |
| 5 | MANIFEST `schema_version` 白名单 | **是**，只允许 v1/v2/v3，未知值报错 |
