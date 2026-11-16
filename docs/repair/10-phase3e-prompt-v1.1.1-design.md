# Phase 3E · Prompt v1.1.1 设计（未激活）

**日期**：2026-11-16
**状态**：**设计稿**；v1.0.0 仍为 active，v1.1.0 保持 `pending_review`，v1.1.1 未接入运行时。
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

> 结论：v1.1.1 必须同时设计 **Prompt + Schema + 版本加载 + 评分服务**，但本阶段只交设计，不改代码。

---

## 2. Faithfulness v1.1.1

### 2.1 分类与状态分离

| 字段 | 取值 | 说明 |
|---|---|---|
| `claim_type` | `factual_claim` / `non_factual` | **互斥**；contradictory 不是类型 |
| `support_status` | `supported` / `unsupported` / `insufficient_evidence` | 只对 factual_claim 有意义 |
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
9. **文档冲突披露**：关于文档不一致的 meta 陈述标 factual_claim；两处原文都可给出时 supported；`is_contradictory=false`（矛盾在文档，不在回答）。

### 2.3 反例/few-shot

- **Q23**：结论“可以按政策反馈” vs 后文“已超时不符合” → 结论 factual_claim / unsupported / `is_contradictory=true` / `contradiction_with=[C2]`；不能标 non_factual 排除。
- **Q21#3**：“质量问题不受 7 天限制” → factual_claim / `insufficient_evidence`；原文只把 7 天限定在无理由退款，未规定普通商品质量问题期限。
- **Q11**：“需提供照片/视频凭证” → factual_claim / insufficient_evidence；“建议联系客服” → non_factual，不进分母。

### 2.4 评分（代码计算）

```
scorable = [c for c in claims if c.claim_type == "factual_claim"]
if not scorable: skipped(no_scorable_claims)
score = supported_count / len(scorable)
details: supported_count, scorable_claim_count, non_factual_count,
         contradiction_count, insufficient_count
```

不支持 claim 不补 0 分，而是进入分母但计为未支持；non_factual 完全排除。

---

## 3. Correctness v1.1.1

### 3.1 输入契约

保持 `query` / `answer` / `gold_answer`；**不接入 key_facts**。
当前没有 `answerability` 字段：v1.1.1 从 `gold_answer` 是否包含“文档未提及/无法确认/信息不足”或条件分支来推断；未来可加可选字段，但不属于本次运行时改动。

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

## 5. Schema 兼容设计（未实施）

### 5.1 FaithfulnessClaim 增量

保留旧字段，新增可选字段：

```python
claim: str
supported: bool | None = None          # v1.0.0 兼容；v1.1.1 用 support_status
evidence: list[str] = []               # v1.0.0 兼容；v1.1.1 用 evidence_refs
reason: str = ""
claim_id: str | None = None
claim_type: Literal["factual_claim", "non_factual"] = "factual_claim"
support_status: Literal["supported", "unsupported", "insufficient_evidence"] | None = None
is_contradictory: bool = False
contradiction_with: list[str] = []
evidence_refs: list[EvidenceRef] = []
```

- v1.0.0 输出缺新字段 → 默认 `factual_claim` / support_status 由 `supported` 派生；行为不变。
- v1.1.1 输出 `support_status`；`supported` 仅作为兼容派生值。
- `EvidenceRef`: `{context_id: str, quote: str}`；Service 校验 quote 在对应 context 中逐字存在。
- `FaithfulnessOutput` 可增加 `scorable_claim_count`（可选），但分母以 Service 计算为准。

### 5.2 其他 Schema

Correctness/Relevancy 输出不变；`RagJudgeInput` 不变（不新增 answerability）。

### 5.3 测试要求（激活前）

- v1.0.0 24 条 Judge 测试全部保持；
- v1.1.1 schema 解析、缺省字段回退、evidence 校验；
- non_factual 过滤、zero-denominator skipped；
- claim_type 非法值归一化（默认 factual_claim）并记录计数，避免单条坏 claim 导致整个 metric failed。

---

## 6. 版本管理与 fingerprint

### 6.1 版本映射

| 版本 | prompt_version | schema_version | rubric_version | Judge metric_version | 状态 |
|---|---|---|---|---|---|
| v1.0.0 | v1.0.0 | rag_judge_schema_v1 | v1.0.0 | v1 | active |
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

- 新增 `RAG_JUDGE_PROMPT_VERSION`，默认 `v1.0.0`；
- 显式解析 `rag_judge/<version>/<metric>.txt`；
- v1.1.1 目录存在**不会自动加载**；
- 缺文件/缺 MANIFEST → 明确报错，不静默回退；
- `AgentConfig.version`、`prompt_sha256`、`judge_config.prompt_version` 必须来自同一解析结果；
- 根目录 `version.txt` 不再作为唯一事实源（避免 `2026-11-14.1` 与 `v1.0.0` 不一致）。

---

## 7. 验收矩阵（设计，未运行）

完整机器可读：`docs/repair/phase3e/prompt-v1.1.1-acceptance-matrix.json`

| Case | 重点 | 期望 |
|---|---|---|
| Q23 | 首句/后文矛盾 | Correctness 0.0–0.2；Faithfulness ≤0.5；Relevancy 0.7–1.0；wrong_facts 必填 |
| Q35 | 发货 vs 到货 | Correctness 0.7–1.0（目标 0.9–1.0）；Faithfulness 0.8–1.0；Relevancy 0.8–1.0 |
| Q36 | 文档冲突 | Correctness 0.5–0.6（缺披露）/0.9–1.0（披露）；Faithfulness 0.8–1.0；Relevancy 0.8–1.0 |
| Q21#3 | 证据不足 | Faithfulness 0.7–0.9；claim `insufficient_evidence`；不得 1.0 |
| Q11 | 建议 vs 规范性要求 | Faithfulness 0.6–0.9；“需提供…” factual/insufficient；“建议…” non_factual |
| Q29 | 合理无答案 | Faithfulness `skipped(no_scorable_claims)`；Correctness 0.9–1.0；Relevancy 0.9–1.0 |

通用：

- 容差：分数区间 ±0.10；标签/skip reason 精确；无回归下降 >0.10（除明确目标）；
- 10 条整体：schema 合法率 100%，无 supported 无 evidence，无新增 failed；
- 不得修改 Human Gold；不得用 v1.0.0 分数反推 Gold。

---

## 8. 风险与未解决问题

1. **answerability 不在当前输入契约**：v1.1.1 只能从 `gold_answer` 推断；未来加字段需另开 Schema/Service 设计。
2. **contexts 无 ID**：C1..Cn 依赖 Service 顺序；需在实现时映射真实 Trace context，并验证 quote 逐字匹配。
3. **Q36 canonical 口径未确认**：设计只要求披露 §1/§12 冲突，不选边；业务确认仍待办。
4. **评分区间未人工验证**：0.0–0.2 等是设计假设，10 条实验只验证相对改善，不把它们包装成客观阈值。
5. **metric_version v2**：需在激活时同步修改 `metric_version_for`/聚合；不迁移 DB，但历史 v1 结果不能与 v2 混算。
6. **key_facts 尚未进入 Correctness 输入**：当前只读 gold_answer；未来启用需 Schema 增 `fact_type/required/evidence_status`，并定义 absence/conflict 不进 supported 分母。
7. **Prompt 长度/成本**：Faithfulness few-shot 增加输入 token；10 条实验需记录 token/成本。
8. **v1.1.1 未运行**：所有期望均未验证；本阶段不产生任何 Judge 分数。

---

## 9. 交付物

| 文件 | 内容 |
|---|---|
| `backend/app/prompts/rag_judge/v1.1.1/*.txt` | 三份 Prompt 模板 |
| `.../v1.1.1/MANIFEST.json` | SHA、schema/rubric/metric 映射、激活条件、风险 |
| `docs/repair/phase3e/prompt-v1.1.1.diff` | 与 v1.0.0 逐行 diff |
| `docs/repair/phase3e/prompt-v1.1.1-acceptance-matrix.json` | 六案例验收矩阵 |
| 本文件 | 设计决策、Schema 兼容、版本映射、风险 |

**状态：设计完成，等待审核；未激活、未运行 Judge、未跑 10/40 条、不进入 Phase 4。**
