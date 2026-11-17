# Phase 3E · Prompt v1.1.1 设计与实现（默认关闭）

**日期**：2026-11-16
**状态**：**设计已实现，默认关闭**；v1.0.0 仍为 active_baseline，v1.1.0 保持 `pending_review`，v1.1.1 仍为 `design_draft` / `active=false`，只有显式设置 `RAG_JUDGE_PROMPT_VERSION=v1.1.1` 才加载。
**依据**：`subagent-review.md/json`、`09-phase3e-prompt-v1.1-design.md`、Human Gold v1（含 key_facts）、当前 v1.0.0 Prompt / Judge Schema / Agent / Service / 版本实现。
**本阶段未运行 Judge、未跑 10 条对照、未跑 40 条评测。**

---

## 1. 当前实现核查

| 项 | 当前事实 | 对 v1.1.1 的影响 |
|---|---|---|
| Judge 输入 `RagJudgeInput` | `query` / `answer` / `contexts: list[str]` / `gold_answer` | **没有 answerability/category**；v1.1.1 只能从 `gold_answer` 推断模糊/无答案 |
| `contexts` | 纯字符串列表，无 context_id | v1.1.1 使用 `C1..Cn` 序号引用；Service 需映射到真实 Trace context |
| Faithfulness Schema | `claim` / `supported` / `evidence` / `reason` | 需新增字段；v1.0.0 必须继续可解析 |
| Correctness/Relevancy Schema | score/missing_points/wrong_facts/reason 与 score/reason | 不变 |
| Prompt 版本 | `load_prompt_version(PROMPT_DIR)` 读根 `version.txt`，默认 v1.0.0 | v1.1.1 目录存在不会自动加载；需显式版本选择 |
| `prompt_sha256` | 对根目录 `<metric>.txt` 计算 | 必须与 `prompt_version` 来自同一路径 |
| `RAG_JUDGE_METRIC_VERSION` | 三个 Judge 指标均为 `v1` | v1.1.1 口径变化需升版，避免与 v1 混聚合 |
| `build_judge_config` | model/temperature/max_tokens/prompt_version/prompt_sha256/metric_version | 缺 schema_version/rubric_version；需扩展 JSONB，无需迁移 |
| `metric_version_for` | Judge 指标返回 v1 | 激活 v1.1.1 时映射 v2；默认 v1.0.0 仍 v1 |

> 结论：v1.1.1 必须同时设计 **Prompt + Schema + 版本加载 + 评分服务**；设计已完成，代码已在默认关闭的开关后落地，见 §11。

---

## 2. Faithfulness v1.1.1

### 2.1 分类与状态分离

| 字段 | 取值 | 说明 |
|---|---|---|
| `claim_type` | `factual_claim` / `non_factual` | **互斥**；contradictory 不是类型 |
| `claim_subtype` | `policy` / `absence` / `conflict` / `advice` / `meta` | 诊断子类型；absence/advice/meta 为 non_factual，conflict 为 factual_claim |
| `support_status` | `supported` / `unsupported` / `insufficient_evidence` | 只对 factual_claim 有意义；v1.1.1 factual 必填 |
| `is_contradictory` | bool | Claim 之间的关系/诊断标签 |
| `contradiction_with` | list[claim_id] | 与哪些 claim 冲突 |
| `evidence_refs` | list[{context_id, quote}] | supported 必须非空且逐字匹配 |

### 2.2 关键规则

1. **结论句优先**：结论 claim 先输出，其余按出现顺序；不得因顺序遗漏。
2. **原子性**：一条 claim 只表达一个可判定事实；不合并。
3. **non_factual 不计入分母**：问候、共情、纯建议、下一步指引、纯元信息。
4. **规范性要求属于 factual_claim**：“需/必须/应当/应/须提供/流程/材料/凭证”即使是用户动作，也按事实判断；无上下文则 `insufficient_evidence`（解决 Q11）。
5. **supported 必须有 Evidence**：`evidence_refs` 至少一条；`quote` 必须逐字出现在所引用的 `C1..Cn`；无法匹配真实 context 不得 supported。
6. **insufficient ≠ unsupported**：上下文未提及/只沾边 → insufficient；与上下文矛盾 → unsupported。
7. **矛盾仍进分母**：`is_contradictory=true` 的 claim 继续判断支持性；不得标 non_factual 排除（解决 Q23）。
8. **全 non_factual / 无 claim**：返回 `reason=no_scorable_claims`；Service 输出 `skipped(no_scorable_claims)`，**不是 1.0**（解决 Q29/Q30 类）。
9. **文档冲突披露**：关于文档不一致的 meta 陈述标 `factual_claim` / `claim_subtype=conflict`；两处原文都可给出时 supported；`is_contradictory=false`（矛盾在文档，不在回答）。
10. **absence meta**：“文档未提及/未说明 X，无法确认”标 `non_factual` / `claim_subtype=absence` 或 `meta`；无肯定 evidence，不进分母。Q29/Q30/Q35 的 absence 不得被当成 factual supported，也不得因此给 1.0。
11. **advice**：纯建议/下一步操作标 `non_factual` / `claim_subtype=advice`；若建议包含事实承诺，按 factual policy 判断。

### 2.3 反例/few-shot

- **Q23**：结论“可以按政策反馈” vs 后文“已超时不符合” → 结论 factual_claim / unsupported / `is_contradictory=true` / `contradiction_with=[C2]`；不能标 non_factual 排除。
- **Q21#3**：“质量问题不受 7 天限制” → factual_claim / `insufficient_evidence`；原文只把 7 天限定在无理由退款，未规定普通商品质量问题期限。
- **Q11**：“需提供照片/视频凭证” → factual_claim / insufficient_evidence；“建议联系客服” → non_factual，不进分母。

### 2.4 评分语义（二次修订）

#### 定义

| 字段 | 定义 |
|---|---|
| `scorable_claim_count` | `claim_type == factual_claim` 的数量（含 unsupported/insufficient） |
| `supported_claim_count` | factual_claim 中 `support_status == supported` 的数量 |
| `unsupported_claim_count` | factual_claim 中 `support_status == unsupported` 的数量 |
| `insufficient_evidence_count` | factual_claim 中 `support_status == insufficient_evidence` 的数量 |
| `non_factual_count` | `claim_type == non_factual` 的数量；不进分母 |
| `absence_count` | `claim_subtype == absence` 的数量；应同时是 non_factual |
| `document_conflict_count` | `claim_subtype == conflict` 且 supported 的数量；Service 据此置 `document_conflict=true` |
| `contradiction_count` | `is_contradictory == true` 的 factual_claim 数量；仅诊断，不排除 |

#### 公式

```
scorable = factual_claim 列表
if len(scorable) == 0:
    status = skipped(no_scorable_claims)      # 不是 1.0
else:
    score = supported_claim_count / scorable_claim_count
    status = evaluated
```

- `unsupported` 和 `insufficient_evidence` **都进入分母**，但都不进入分子；
- `insufficient_evidence` 不得自动视为 supported，也不得从分母删除；
- 额外输出 `insufficient_evidence_rate = insufficient_count / scorable_count`，但不改变主分；
- `non_factual` 完全不进分母；
- `contradiction_count` 只做诊断，不额外扣分/加分；矛盾 claim 仍以其 support_status 进入分子/分母。

#### 边界案例

| 场景 | 结果 |
|---|---|
| 全部 non_factual / 0 claim | `skipped(no_scorable_claims)`，score=None |
| 全部 factual 为 insufficient_evidence | `evaluated`，score=0.0；`all_insufficient=true`；不 skipped |
| 全部 factual 为 unsupported | `evaluated`，score=0.0 |
| 混合 supported/unsupported/insufficient | `supported / scorable` |
| 全部 factual supported | `evaluated`，score=1.0 |

#### Q21#3 的单 Claim 与整条回答

- **单 Claim 视角**：Q21#3 若单独评测，`support_status=insufficient_evidence`，score=0.0（1 个 scorable，0 supported）。
- **整条回答视角**：Q21 回答若拆成 5 个 factual claim，其中 Q21#3 与“可依据保修条款申请保修”均为 insufficient、其余 3 个 supported，则 score=3/5=0.6（保修 §8 只覆盖电子产品/配件，不能推广到所有普通商品）。
- 两者不冲突：0.0 是“该 claim 的贡献”，0.6 是“整条回答汇总分”；报告必须同时给出 `Q21#3` 标签与整条 `score`，不能用一个数覆盖另一个。
- v1.1.1 验收以**整条回答 0.6–0.7 + Q21#3 为 insufficient_evidence** 为准；若单独 claim 测试，则期望 0.0。

### 2.5 矛盾标签定义（二次修订）

| 类型 | 触发 | 字段 | 是否进分母 | 案例 |
|---|---|---|---|---|
| 回答内部 Claim 矛盾 | 同一回答的两个 claim 不可同时成立 | `is_contradictory=true`；`contradiction_with=[cl...]`；`scope=answer_internal` | 是（两个 claim 都算） | Q23 |
| 回答 vs Context 矛盾 | claim 与所引 context 原文冲突 | `support_status=unsupported`；`scope=context`；可选 `evidence_refs` 指向冲突原文 | 是 | 如声称“7 天可退”但 context 写“不支持” |
| Context 自身冲突 | 文档两条规则范围/口径不一致；不是回答自相矛盾 | 关于文档的 meta claim 标 `factual_claim` / `claim_subtype=conflict`；两处原文都可给出时 `support_status=supported`；`is_contradictory=false`；Service 记 `document_conflict=true` | 是（meta claim 计 1 条） | Q36 |

校验规则：

- `is_contradictory=true` 只能用于**回答内部**；至少需要 2 个 factual claim，`contradiction_with` 非空、引用存在的 `claim_id`、不能自指；
- `contradiction_with` 不得引用 non_factual claim；
- 回答 vs Context 冲突用 `support_status=unsupported`，不得用 `is_contradictory` 冒充；
- Context 自身冲突用 meta claim + `document_conflict` 诊断，不得把披露冲突的回答标成 contradictory；
- 所有矛盾 claim 仍参与 supported 分子/分母计算，不得排除。

---

## 3. Correctness v1.1.1

### 3.1 输入契约与 answerability 推断

保持 `query` / `answer` / `gold_answer`；**不接入 key_facts**。
当前 `RagJudgeInput` **没有 answerability/category**；v1.1.1 只能从 `gold_answer` 推断，规则如下：

| 条件 | 推断 |
|---|---|
| gold_answer 含“文档未提及/未说明/无法确认/信息不足/无法判断/未规定”等，且没有实质政策答案 | `unanswerable` |
| gold_answer 含明确条件分支（“如果/取决于/分两种/需确认/视…而定”）或要求补充信息 | `ambiguous` |
| 同时含 no-answer 标记与条件分支 | `ambiguous`（如 Q36） |
| 有实质政策答案、无条件分支 | `answerable` |
| 无法可靠判断 | `unknown`：不启用无答案/模糊特殊加分，只按一般事实覆盖评分 |

`unknown` 不是 `ambiguous`，不得给条件式回答额外奖励；也不得因“可能模糊”自动扣分。

### 3.1.1 Q36：真实单边口径 vs 编造口径

| 回答 | 判定 |
|---|---|
| 引用 §12“虚拟商品一经售出不支持退款”，但不披露 §1“已激活”限定 | 真实但单边 → `0.5–0.6`；`missing_points` 含“§1/§12 冲突披露”；`wrong_facts` 为空 |
| 同时披露 §1/§12 并给条件分支 | `0.9–1.0`；不因“没有唯一结论”扣分 |
| 编造“虚拟商品 7 天内可退”或文档不存在的规则 | `0.0–0.2`；写入 `wrong_facts` |
| 引用真实单边口径但声称“文档明确统一规定” | `0.3–0.4`；真实引用 + 错误确定性 |

### 3.1.2 Q23/Q35/Q36 判定树（按优先级）

1. **首句/结论与后文或金标矛盾** → Q23：`0.0–0.2`，`wrong_facts` 必填，停止。
2. **编造文档不存在的规则** → `0.0–0.2`，`wrong_facts` 必填。
3. **Q36 单边真实口径、未披露冲突** → `0.5–0.6`，`missing_points` 含冲突披露，`wrong_facts` 为空。
4. **Q35 混淆发货与到货** → `0.3–0.4`；区分二者、说明无运输时长 → `0.9–1.0`；只答发货且未说明到货 → `0.5–0.6`。
5. **分支覆盖**：全分支 `0.9–1.0`；部分 `0.5–0.6`；泛泛政策 `0.3–0.4`。
6. **次要缺失** `0.7–0.8`；完整 `0.9–1.0`。

### 3.2 不重叠区间与优先级

| 区间 | 含义 |
|---|---|
| 0.0–0.2 | 关键事实矛盾、编造、答非所问、首句/后文矛盾 |
| 0.3–0.4 | 无依据的确定性结论，或核心事实错误 |
| 0.5–0.6 | 部分正确，缺主要分支/关键条件 |
| 0.7–0.8 | 核心正确，缺次要信息/表述不精确 |
| 0.9–1.0 | 关键事实、条件、分支完整且与金标一致 |

**优先级**：矛盾 > 编造/无依据确定性结论 > 部分正确 > 次要缺失 > 完整。
命中多条时取最严重区间，不平均、不向上取整。区间之间不连续；若不确定，选择更严重（更低）的区间，禁止输出间隙值（如 0.25）。

### 3.3 模糊/条件式

- 金标有分支：必须覆盖**问题真正需要的全部分支**，不因使用“如果/取决于”自动高分。
- 全部分支 + 明确缺信息 → 0.9–1.0；部分分支 → 0.5–0.6；泛泛政策 → 0.3–0.4；无依据确定性结论 → 0.0–0.2 + wrong_facts。

### 3.4 文档冲突

- 金标披露 §1/§12 冲突时：回答同时披露 + 分支 → 0.9–1.0；只选一边不披露 → 0.5–0.6；编造第三条 → 0.0–0.2。
- 冲突披露不判错；缺披露进 `missing_points`，不进 `wrong_facts`。

### 3.5 拒答

- 金标是“未提及/无法确认/信息不足”：正确拒答 + 下一步 → 0.9–1.0；编造 → 0.0–0.2。
- 金标有实质答案：拒答 → 0.0–0.2（错误拒答）。

### 3.6 矛盾与措辞

- 首句/结论与后文关键事实冲突，或同时给“可以/不可以” → 0.0–0.2；`wrong_facts` 必填。
- `missing_points` 只列金标事实/条件；建议不算 missing point，除非金标明确要求。
- 不因措辞、顺序、详细程度扣分；不评价语气/格式/长度。

### 3.7 few-shot

- Q23 首句矛盾 → 0.0–0.2 + wrong_facts。
- Q35 发货 vs 到货 → 0.9–1.0；混淆 → 0.3–0.4。
- Q36 冲突披露 → 0.9–1.0；只选一边 → 0.5–0.6。

---

## 4. Relevancy v1.1.1

| 区间 | 含义 |
|---|---|
| 0.0–0.2 | 答非所问、空泛、只复述问题 |
| 0.3–0.4 | 只沾边/回避，需重新提问 |
| 0.5–0.6 | 泛泛政策或只回应一小部分 |
| 0.7–0.8 | 回应主要部分，缺子问题/条件 |
| 0.9–1.0 | 完整回应；或合理拒答 + 下一步 |

规则：

- 合理拒答可 0.9–1.0，但**不自动满分**：只给套话/回避 → 0.3–0.6；有具体下一步 → 1.0。
- 信息不足 + 要求补充条件 → 0.9–1.0；泛泛政策 → 0.5–0.6。
- 建议可以相关，但不能把跑题回答拉满；建议占主导且核心未回应 → 0.3–0.6。
- 多部分：全部 0.9–1.0；部分 0.7–0.8；一个子问题/通用政策 0.5–0.6；遗漏核心 0.0–0.4。
- **不判断事实正确性**；正确/错误拒答由 Correctness 负责，不重复扣分；验收用分指标下限，不用简单平均。
- 区间之间不连续；若不确定，选择更严重（更低）的区间，禁止输出间隙值。

Few-shot：Q29 合理拒答 0.9–1.0；Q35 条件式 0.9–1.0 / 只答发货 0.5–0.6；Q36 分支+冲突披露 0.9–1.0。

---

## 5. Schema 兼容设计（已实现，默认关闭）

### 5.1 FaithfulnessClaim 增量

保留旧字段，新增可选字段：

```python
claim: str
supported: bool | None = None          # v1.0.0 兼容；v1.1.1 用 support_status
evidence: list[str] = []               # v1.0.0 兼容；v1.1.1 用 evidence_refs
reason: str = ""
claim_id: str | None = None
claim_type: Literal["factual_claim", "non_factual"] = "factual_claim"
claim_subtype: Literal["policy", "absence", "conflict", "advice", "meta"] | None = None
support_status: Literal["supported", "unsupported", "insufficient_evidence"] | None = None
is_contradictory: bool = False
contradiction_with: list[str] = []
evidence_refs: list[EvidenceRef] = []
```

- v1.0.0 输出缺新字段 → 默认 `factual_claim` / support_status 由 `supported` 派生；行为不变。
- v1.1.1 factual claim 必须有合法 `support_status`；缺失/非法 → `validation_error`，按 `insufficient_evidence` 处理并计数（不得默认 supported）。
- `support_status` 优先；`supported` 仅作为 v1 兼容派生值；两者冲突时以 `support_status` 为准并记 `legacy_supported_conflict=true`。
- `claim_subtype` 校验：policy/conflict 必须 factual；absence/advice/meta 必须 non_factual；冲突/缺失 → `validation_error`。
- `EvidenceRef`: `{context_id: str, quote: str}`；Service 校验 quote 在对应 context 中逐字存在。
- `FaithfulnessOutput` 可增加 `scorable_claim_count`（可选），但分母以 Service 计算为准。

### 5.2 其他 Schema

Correctness/Relevancy 输出不变；`RagJudgeInput` 不变（不新增 answerability）。

### 5.3 测试要求（已补充单测）

- v1.0.0 24 条 Judge 测试全部保持；
- v1.1.1 schema 解析、缺省字段回退、evidence 校验；
- non_factual 过滤、zero-denominator skipped；
- claim_type 非法值归一化（默认 factual_claim）并记录计数，避免单条坏 claim 导致整个 metric failed。

### 5.4 Evidence 校验（Service 已实现）

| 检查 | 规则 | 失败处理 |
|---|---|---|
| Context ID 有效 | `context_id` 必须在本次输入的 C1..Cn 中 | 标记 `unknown_context_id`；该 claim 不得 supported |
| Quote 原文子串 | `quote.strip()` 必须是 `context.content.strip()` 的子串；不做内部空白/同义词归一化 | 标记 `quote_not_found`；不得 supported |
| supported 必须有 evidence | supported claim 的 `evidence_refs` 非空且每条通过上述校验 | 降级为 `insufficient_evidence`，记 `evidence_validation_failed=true` |
| insufficient/unsupported | 允许空 evidence；若提供则仍校验 | 失败只记诊断，不改变 support_status（unsupported 仍 unsupported） |
| 重复/空 quote | 空 quote、只有省略号、跨 context 拼接 | 标记 `empty_quote` / `quote_not_in_context`；不得 supported |

- 校验失败**不静默接受**：Service 在 `details.evidence_validation` 记录 `claim_id`、错误码、原始 context_id/quote；
- 一个 claim 校验失败不影响其它 claim；
- 若全部 factual claim 因 evidence 校验降级为 insufficient，按 2.4 处理（score=0.0, `all_insufficient=true`），不是 1.0；
- 这部分已在 `rag_judge_service._faithfulness_score` 落地；v1.0.0 走兼容分支，不改变旧行为。

---

## 6. 版本管理与 fingerprint

### 6.1 版本映射

| 版本 | prompt_version | schema_version | rubric_version | Judge metric_version | 状态 |
|---|---|---|---|---|---|
| v1.0.0 | v1.0.0 | rag_judge_schema_v1 | v1.0.0 | v1 | active_baseline |
| v1.1.0 | v1.1.0 | rag_judge_schema_v2（拟） | v1.1.0 | v2（拟） | pending_review |
| v1.1.1 | v1.1.1 | rag_judge_schema_v2 | v1.1.1 | v2 | design_draft |

- **metric_version 升到 v2**：Faithfulness 分母改变，Correctness/Relevancy 评分语义改变；避免 v1/v2 结果混入同一聚合。
- `rubric_version` / `schema_version` 存入 `judge_config` 与结果 `details` 的 JSONB，**不新增数据库列、不迁移**。
- 检索指标仍 `v1`；Judge 指标 v2。
- 历史 Run 的 `judge_config` 快照不覆盖；v1.0.0 结果继续按 v1 聚合。

### 6.2 Fingerprint

`build_judge_config` 的 `metric_fingerprints` 扩展为：

```json
{
  "model": "...",
  "temperature": 0.0,
  "max_tokens": 8192,
  "prompt_version": "v1.1.1",
  "prompt_sha256": "...",
  "schema_version": "rag_judge_schema_v2",
  "rubric_version": "v1.1.1",
  "metric_version": "v2"
}
```

- 重试复用必须逐项相等；v1.0.0 结果不可复用于 v1.1.1。
- `prompt_sha256` 必须与 `prompt_version` 来自同一文件路径。
- fingerprint 不含 context 顺序；`evidence_refs` 的 C1..Cn 依赖 Service 的 context 顺序，需在 Trace/配置中保持稳定。

### 6.3 加载器

- 已新增 `RAG_JUDGE_PROMPT_VERSION`，默认 `v1.0.0`；
- 已实现显式解析 `rag_judge/<version>/<metric>.txt`；
- v1.1.1 目录存在**不会自动加载**；
- 缺文件/缺 MANIFEST/SHA 不匹配 → 明确报错，不静默回退；
- `judge_config.prompt_version` 使用 resolved prompt version，并同时记录 `resolved_prompt_version`；
- 根目录 `version.txt` 不再作为 Judge 唯一事实源（避免 `2026-11-14.1` 与 `v1.0.0` 不一致）。

### 6.4 v1/v2 兼容与历史行为

#### Schema 字段关系

| v1.0.0 字段 | v1.1.1 字段 | 兼容规则 |
|---|---|---|
| `claim` | `claim` | 必填，不变 |
| `supported: bool` | `support_status: enum` | v1 输出无 `support_status` → 由 supported 派生：true=supported，false=unsupported；v1.1.1 以 support_status 为准 |
| `evidence: list[str]` | `evidence_refs: list[{context_id, quote}]` | v1 evidence 仅作兼容；v1.1.1 校验 quote 是否为对应 context 子串 |
| 无 | `claim_id` | v1 自动生成 `C1..Cn`；v1.1.1 要求模型提供 |
| 无 | `claim_type: factual_claim|non_factual` | v1 默认 factual_claim；v1.1.1 必须显式 |
| 无 | `is_contradictory` / `contradiction_with` | v1 默认 false/[]；v1.1.1 按 2.5 校验 |
| `reason` | `reason` | 不变 |

**解析策略**：v1.0.0 输出用 v1 兼容路径；v1.1.1 输出用 v2 路径。不得让 v1.1.1 输出缺 `supported` 时被 v1 Schema 拒绝，也不得让 v1.0.0 输出因缺新字段而 failed。

#### JudgeOutcome 预期变化

| 字段 | v1.0.0 | v1.1.1 |
|---|---|---|
| `metric_version` | v1 | v2（Judge 三指标） |
| `score` | supported/全部 claims | supported/scorable factual claims |
| `skipped_reason` | `no_claims` | `no_scorable_claims`（全部 non_factual） |
| `details` | claims, supported_count, claim_count | 增加 scorable/supported/unsupported/insufficient/non_factual/contradiction counts、evidence_validation、all_insufficient |
| `judge_config` | model/temp/max_tokens/prompt_version/SHA/metric_version | 增加 schema_version/rubric_version |

#### 历史 Run 与复用

- 历史 Run 的 `judge_config` 快照与结果不改写；v1.0.0 结果继续 `metric_version=v1`；
- v1.1.1 新建 Run 使用 v2；不得把 v2 结果写回 v1 Run；
- 重试复用 Judge 结果必须逐项比较 fingerprint：model/temperature/max_tokens/prompt_version/prompt_sha256/schema_version/rubric_version/metric_version；任一不等不得复用；
- **Trace 复用与 Judge 结果复用是两件事**：Trace 复用只看检索配置/checksum；Judge 结果复用必须看上述完整 fingerprint。

#### 聚合隔离与 metric_version_for

- `rag_evaluation_results.metric_version` 是聚合隔离键；v1 与 v2 不得合并均值；
- `build_aggregate` / `summary` 继续按 `metric_version` 分组；
- 当前 `metric_version_for(metric_name: str)` 只接收指标名并读静态映射，无法同时支持两版；设计改为 `metric_version_for(metric_name, prompt_version: str | None = None)`（或传入 resolved config）：
  - 未传 `prompt_version` → 默认 `v1.0.0` 映射，返回 v1；
  - `prompt_version=v1.1.1` → Judge 三指标 v2；检索指标始终 v1；
- `build_judge_config.metric_versions`、`expected_metrics`、`_parent_result_reusable` 必须使用**同一解析结果**，避免配置/结果/聚合不一致；
- 激活前必须补该签名与调用方测试，默认行为保持 v1。
- 不需要 DB Migration；历史 v1 行不更新。

---

## 7. 验收矩阵（设计，未运行）

完整机器可读：`docs/repair/phase3e/prompt-v1.1.1-acceptance-matrix.json`
固定输入：`docs/repair/phase3e/prompt-v1.1.1-fixtures.json`

### 7.0 Fixture 上下文来源（P0-1 修正）

`prompt-v1.1.1-fixtures.json` 对每个案例冻结两组上下文：

| 字段 | 内容 | 用途 |
|---|---|---|
| `retrieval_contexts` | v1.0.0 retrieval trace 的 **4 个原始片段**（R1–R4） | 检索配置/证据来源参考 |
| `answer_contexts` | v1.0.0 query trace 的 **2 个原始生成上下文**（C1–C2） | v1.0.0 Pilot Judge 实际输入 |

经核对，v1.0.0 Pilot Judge 的 Faithfulness 使用的是 `answer_contexts`（query/agent_chat 上下文），不是 retrieval 的 4 条；历史分数必须与 `answer_contexts` 绑定，不能改用 4 条 retrieval 片段后仍引用旧分数。若未来要用 4 条 retrieval 上下文做 Faithfulness，必须重跑 v1.0.0 建立同输入基线，旧分数降级为历史参考。本设计不混用两组上下文。

### 7.1 Human Gold 覆盖与限制

| Case | 基础 Gold 来源 | 是否 Human Gold | 说明 |
|---|---|---|---|
| Q23 | Human Gold v1 | ✅ | 题干已改写；答案/证据人工确认 |
| Q35 | Human Gold v1 | ✅ | 区分发货/到货 |
| Q36 | Human Gold v1 | ✅ | 含 §1/§12 冲突披露 |
| Q21#3 | Human Gold Claim | ✅（仅 Claim） | Q21 基础题为 AI draft；Q21#3 已人工确认 insufficient_evidence |
| Q11 | AI draft | ❌ | 基础题未人工复核；验收为 provisional |
| Q29 | AI draft | ❌ | 基础题未人工复核；验收为 provisional |

> Q11/Q21 基础/Q29 基础不是 Human Gold，不得把其期望说成人工验证；只有 Q21#3 Claim 是人工确认。Q23/Q35/Q36 的 Gold 与 v1.0.0 输入 fixture 分开保存。

### 7.2 六案例矩阵

| Case | 重点 | 期望（分数区间 + 必现诊断） |
|---|---|---|
| Q23 | 回答内部矛盾 | C 0.0–0.2；F 0.4–0.5（6 scorable: 3 supported / 1 unsupported / 2 insufficient = 0.5）；R 0.7–1.0；`is_contradictory=true`、`contradiction_with=["cl2"]`、`wrong_facts` 含肯定结论 |
| Q35 | 发货 vs 到货 | C 0.7–1.0（目标 0.9–1.0）；F 0.8–1.0；R 0.8–1.0；absence 为 non_factual、无 wrong_facts |
| Q36 | Context 自身冲突 | v1.0.0 无披露：C 0.5–0.6，`missing_points` 含冲突；披露 variant：C 0.9–1.0；F 0.8–1.0（7 policy supported；cl8 conflict optional）；不得 `wrong_facts` 真实单边引用 |
| Q21#3 | 证据不足 | 整条 F 0.6–0.7（5 scorable: 3 supported + 2 insufficient = 0.6）；Q21#3 `insufficient_evidence`；单 Claim 0.0；不得 1.0 |
| Q11 | 规范性要求 vs 建议 | F 0.6–0.9（3/5=0.6；5/6=0.833 也是合法拆分）；“需提供…” factual/insufficient；“建议…” non_factual；不得 <0.5 |
| Q29 | 合理无答案 | F `skipped(no_scorable_claims)`；C 0.9–1.0；R 0.9–1.0；`scorable_claim_count=0` |

每个案例的完整 fixture、预期 Claim 拆分、标签、诊断、禁止行为、容差、回归规则见 JSON；本表只做摘要。

### 7.3 矩阵静态校验（不跑 Judge）

激活前必须通过脚本校验：

- `required` / `variant_only` 是 boolean；`human_gold` 是 boolean；`human_gold_claim` 是 null 或结构化对象；
- 每个 case 的 `claim_id` 唯一；`contradiction_with` 都能解析到同 case 的 claim；
- `claim_subtype ∈ {policy, absence, conflict, advice, meta}`，且 policy/conflict 为 factual、absence/advice/meta 为 non_factual；
- 每个 F 期望区间都能由 claim 的 supported/scorable 算出；
- 所有 `evidence_refs.context_id` 都在 fixture `answer_contexts` 中存在，且 `quote.strip()` 是对应 context 的逐字子串；
- 每个 `supported` factual claim 至少有一条 evidence_refs；
- Q29 的 scorable=0，skip reason 精确为 `no_scorable_claims`。

本次设计自检已通过上述静态规则；负向测试（Q35 cl6/cl7 指 C2、supported 无 evidence）能被脚本抓出；未运行 Judge。

六案例 dry-run（2026-11-16，签字通过后执行）已通过：6/6 案例 Schema/标签/证据/计分符合矩阵；负向/边界测试 12/12 符合预期（含 Q21 1.0 超出 0.6–0.7 FAIL、Q21 2/3=0.667 PASS、Q36 base 7/7 PASS）。dry-run 用矩阵 expected_claims 构造合成输出，只验证 Schema/计分/证据规则，不调用 Judge，不代表 Prompt 真实模型表现。

通用：

- 容差：Faithfulness 的六个期望值使用 `target_range=...; tolerance=none`，区间为目标范围，不再额外加 ±0.10；其它精确目标值允许 ±0.10；forbidden/约束优先于分数容差；
- 10 条整体：Schema 合法率 100%，无 supported 无 evidence，无新增 failed；
- 不得修改 Human Gold；不得用 v1.0.0 分数反推 Gold；
- Q11/Q21 基础/Q29 的期望为 provisional，只有 Q21#3 Claim 是 Human Gold。

---

## 8. 风险与未解决问题

1. **answerability 不在当前输入契约**：v1.1.1 只能从 `gold_answer` 推断；`unknown` 时只按一般事实覆盖评分；未来加字段需另开 Schema/Service 设计。
2. **contexts 无 ID**：C1..Cn 依赖 Service 顺序；需在实现时映射真实 Trace context，并验证 quote 逐字匹配。
3. **Q36 canonical 口径未确认**：设计只要求披露 §1/§12 冲突，不选边；业务确认仍待办。
4. **评分区间未人工验证**：0.0–0.2 等是设计假设；10 条实验只验证相对改善，不把它们包装成客观阈值。
5. **metric_version v2**：需在激活时同步修改 `metric_version_for`/聚合；不迁移 DB，但历史 v1 结果不能与 v2 混算。
6. **key_facts 尚未进入 Correctness 输入**：当前只读 gold_answer；未来启用需 Schema 增 `fact_type/required/evidence_status`，并定义 absence/conflict 不进 supported 分母。
7. **Prompt 长度/成本**：Faithfulness few-shot 增加输入 token；10 条实验需记录 token/成本。
8. **Q11/Q21 基础/Q29 基础不是 Human Gold**：只有 Q21#3 Claim 是人工确认；这三条 Acceptance 为 provisional，需后续人工复核。Q21 cl5 已收窄为 insufficient，F 改为 0.6–0.7。
9. **Q21 整条 0.6 依赖 5 个 claim 的拆分**：若模型拆分不同，目标改为 0.6–0.7 + Q21#3 insufficient，不固定 0.6。
10. **v1.1.1 未运行**：所有期望均未验证；本阶段不产生任何 Judge 分数。
11. **metric_version_for 签名**：需改为接收 prompt_version/config；未传时默认 v1，v1.1.1 显式传 v2；调用方测试必须覆盖默认行为。
12. **fixture 基线上下文**：v1.0.0 分数绑定 answer_contexts（2 条 query trace）；4 条 retrieval_contexts 已冻结但不用于旧分数。若改用 4 条作为 Faithfulness 输入，必须重跑 v1.0.0 建立同输入基线。
13. **v1.0.0 MANIFEST**：status 已统一为 `active_baseline`；`archived` 仅表示不再迭代，不是 inactive。

---

## 9. 最终自检（2026-11-16）

| 检查 | 结果 |
|---|---|
| v1.0.0 Prompt | 未修改；status=active_baseline；根目录 SHA 仍 `287053e9…`（F） |
| v1.1.0 Prompt | 未修改；仍 pending_review |
| v1.1.1 Prompt 正文 | 按 P0-3/P0-4/P1-4/P1-7/P2-3 修订：claim_id cl、claim_subtype、absence/conflict、answerability 推断；已记录原因 |
| Agent/Service/Schema/API/DB | 设计阶段未修改；实现阶段已按 §11 在默认关闭开关后落地 |
| Migration | 未执行 |
| Judge / 10 条 / 40 条 | 未运行 |
| 固定 fixture | 6 个案例；每个含 4 条 retrieval_contexts + 2 条 answer_contexts；v1.0.0 分数绑定 answer_contexts |
| 验收矩阵 | 6 案例，含 claim_id/subtype/预期标签/分数/诊断/禁止/容差/回归；静态校验脚本 `validate_prompt_v1.1.1_matrix.py` 通过 |
| Human Gold 混用 | Q23/Q35/Q36 Human Gold；Q21#3 仅 Claim；Q11/Q21 基础/Q29 明确 AI draft |
| 版本关系 | v1.0.0 active；v1.1.1 design_draft/inactive；metric v2 映射已设计 |

---

## 10. 交付物

| 文件 | 内容 |
|---|---|
| `backend/app/prompts/rag_judge/v1.1.1/*.txt` | 三份 Prompt 模板 |
| `.../v1.1.1/MANIFEST.json` | SHA、schema/rubric/metric 映射、激活条件、风险 |
| `docs/repair/phase3e/prompt-v1.1.1.diff` | 与 v1.0.0 逐行 diff |
| `docs/repair/phase3e/prompt-v1.1.1-acceptance-matrix.json` | 六案例验收矩阵（含 claim_id/subtype/静态校验要求） |
| `docs/repair/phase3e/prompt-v1.1.1-fixtures.json` | 六案例固定输入：4 retrieval + 2 answer contexts、Human Gold/AI draft 标记 |
| `docs/repair/phase3e/validate_prompt_v1.1.1_matrix.py` | 矩阵静态校验（不跑 Judge）：类型/claim_id/subtype/evidence/分数自洽/4R2C |
| 本文件 | 设计决策、Schema 兼容、版本映射、风险 |

**状态：设计完成，等待审核；未激活、未运行 Judge、未跑 10/40 条、不进入 Phase 4。**

---

## 11. 实现记录（默认关闭，未激活）

**日期**：2026-11-16
**边界**：只实现 v1.1.1 Schema / Service / loader + 单测；v1.0.0 仍默认；未激活、未跑 Judge/10/40、未改 Human Gold、未做 Migration。

### 11.1 代码变更

| 文件 | 变更 |
|---|---|
| `backend/app/core/config.py` | 新增 `RAG_JUDGE_PROMPT_VERSION`，默认 `v1.0.0` |
| `backend/.env.example` | 同步默认值 |
| `backend/app/schemas/agents/rag_judge.py` | `FaithfulnessClaim` 扩展 `claim_id/claim_type/claim_subtype/support_status/is_contradictory/contradiction_with/evidence_refs`；`supported` 改为可选；新增 `EvidenceRef`、schema/metric 版本映射 |
| `backend/app/agents/rag_judge_agent.py` | 显式版本化 loader：`<version>/MANIFEST.json` + `<version>/<metric>.txt`，校验 MANIFEST/SHA；缺文件/缺 MANIFEST/SHA 不匹配 → `RagJudgePromptError` |
| `backend/app/services/rag_judge_service.py` | v2 计分：factual 进分母、non_factual 排除、0 scorable → `skipped(no_scorable_claims)`、全 insufficient → 0.0 + `all_insufficient`；evidence 校验/降级；矛盾/冲突校验 |
| `backend/app/services/rag_evaluation_service.py` | `metric_version_for(metric, prompt_version=None)`；`build_judge_config` 增加 schema/rubric/resolved prompt；Run 创建/重试/聚合按同一 prompt version 解析 |
| `backend/app/services/rag_evaluation_runner.py` | 结果行/失败行/复用检查按 Run 的 Judge prompt version 计算 metric_version；v2 evidence 统计 |
| `backend/tests/unit/test_rag_judge_v2_schema_loader.py` | v2 Schema、默认关闭、显式 v1.1.1、MANIFEST/SHA/缺文件负向测试 |
| `backend/tests/unit/test_rag_judge_v2_scoring.py` | v2 计分/证据/矛盾/zero-denominator；六案例 canonical + 12 个负向/边界回归 |
| `backend/tests/integration/test_rag_judge_integration.py` | 测试夹具改用有效 Prompt 版本；24 条 Judge 测试保持 |
| `backend/tests/integration/test_rag_evaluations.py` | fake judge 签名接受新增可选参数 |

### 11.2 行为结果

- 默认 `RAG_JUDGE_PROMPT_VERSION=v1.0.0`；v1.1.1 目录存在不会自动加载；
- v1.1.1 显式加载后：`schema_version=rag_judge_schema_v2`、`rubric_version=v1.1.1`、Judge `metric_version=v2`；
- v1.0.0 输出 `supported/evidence` 继续可解析，v1 计分路径不变；
- v2 factual 缺 `support_status`/非法 `claim_subtype` → `validation_errors`，按 `insufficient_evidence` 计数，不静默默认 supported；
- supported 无 evidence、quote 非逐字、context 不存在 → 降级 `insufficient_evidence`，记 `evidence_validation_failed`；
- `claim_subtype=conflict` + supported → `document_conflict=true`；两条证据必须 `(context_id, quote.strip())` 去重且互不为子串；冲突 claim 不得标 `is_contradictory=true`；
- 重复 `claim_id` 保留首条、跳过后续（只计一次），仍记录 `duplicate_claim_id`；
- 结构化失败保留首次/修复两次 raw output；null 集合字段宽容化；修复 Prompt 使用紧凑模板 + 完整 JSON 示例；
- v1.1.1 Faithfulness 输入显式附带 `context_ids=["C1", ...]`（不改变 `RagJudgeInput`），避免模型把文档章节号当 context_id；
- 共享 `parse_with_repair` 在无 `repair_example` 时回退到 `schema.model_json_schema()`，其它 Agent 修复能力不降级；
- Q17 单案例修复验证：attempt1/2 schema PASS 但 context_id 写成 C7（章节号）/quote 不命中；显式 `context_ids` 后 schema PASS、F=1.0、5/5 evidence、validation_errors=[]；新 F SHA `4ee65afb…`；
- 新增单测全部通过；生产 Schema/Service 重跑同一 6 案例 dry-run，结果与设计稿 dry-run 一致（6/6、12/12）。

### 11.3 激活闸门（仍未满足）

- 未设置 `RAG_JUDGE_PROMPT_VERSION=v1.1.1`；
- 回滚：删除该环境变量或设为 `v1.0.0`；v1.1.1 目录保留不会生效；
- `MANIFEST.active` 仅记录状态，不作为硬门禁；显式选择才加载，默认不选；
- 10 条真实对比第一次因 **Q17 v1.1.1 Faithfulness schema failed** 停止（4/10）；Q17 单案例修复后已 **schema PASS、F=1.0、5/5 evidence、validation_errors=[]**；
- 10 条重跑（2026-11-17）因 **Q01 Correctness 0.900→0.700（-0.200，无目标解释）** 停止（1/10）；未跑 40 条；
- Q11 v1.1.1 F=0.833 属于合法 5/6 拆分；Q11 target 已调整为 0.6–0.9；Q36 未运行，disclosure 未验证；
- 不得把 dry-run PASS 当作 Prompt 质量证据；v1.1.1 仍 `design_draft` / `active=false`。
