# Phase 3E Subagent 独立复核报告

**日期**：2026-11-16
**复核方式**：5 个独立 subagent 并行审核
**复核性质**：`reviewer_type=ai_subagent`，**不是 Human Gold**，不替代人工签核
**总判定**：Prompt v1.1.0 `approve_with_changes`，`ready_for_implementation=false`

---

## 1. 总览

| 审核对象 | 数量 | `ai_reviewed` | `needs_recheck` | 结论 |
|---|---|---|---|---|
| Prompt v1.1.0（3 个指标） | 3 | — | — | approve_with_changes，暂不可实施 |
| 10 条 Pilot 基础字段 | 10 | 8 | 2（Q23、Q36） | 2 条需人工定稿 |
| 剩余 30 条基础字段 | 30 | 24 | 6（Q14/Q15/Q16/Q19/Q37/Q40） | 6 条需人工定稿 |
| 35 条 Pilot Claim | 35 | 34 | 1（Q21#3） | 32 supported / 1 unsupported / 2 insufficient |
| **合计** | **78** | **66** | **9** | 未达到“直接实施”门槛 |

> 说明：Q35 的 `reference_answer_ok=false`，但复核后已给出修正答案，状态仍为 `ai_reviewed`；Q23、Q36 需人工确认题干/文档口径。

---

## 2. Prompt v1.1.0 阻断项

### 2.1 Faithfulness（最严重）

| # | 问题 | 影响 |
|---|---|---|
| F1 | `claim_type` 不是互斥分类：`contradictory` 可能被同时标成 `non_factual` 而排除出分母 | Q23 的首句矛盾可能再次漏判 |
| F2 | 没有 `insufficient_evidence` 的表示；当前只有 `supported: bool` | Q21“质量问题不受 7 天限制”无法落到“证据不足”，仍可能被判 supported |
| F3 | 未定义“分母为 0” | 纯拒答/纯建议回答可能除零或静默跳过 |
| F4 | `supported=true` 仍可带空 evidence | 与标注规范冲突 |
| F5 | 同时要求“按出现顺序”和“结论句第一条”，规则自相矛盾 | 输出不稳定 |
| F6 | 删除了 v1.0.0 的“不要合并多条事实” | Claim 粒度可能变差 |
| F7 | 没有“上下文未禁止 ≠ 支持”规则 | Q21 的推断型错误无法拦截 |
| F8 | 未定义 deontic（需/必须/应当提供凭证）属于事实还是建议 | Q11 仍可能被过度扣分 |
| F9 | 无 few-shot；无 claim_type 非法值兜底；`metric_version` 仍为 v1 | 版本追溯与聚合会混用 v1.0/v1.1 |

**建议**：
- `claim_type = factual_claim | non_factual`，另加 `is_contradictory` / `evidence_status`；
- `insufficient_evidence` 作为评分状态；
- 分母只统计 factual + contradictory；分母为 0 → `skipped(no_scorable_claims)`；
- `supported=true` 必须有至少一条原文 evidence；
- 结论 claim 优先，其余按出现顺序；恢复原子性；
- 增加 Q23、Q11/Q35、Q21 三个 few-shot；
- Faithfulness 新口径应提升 `metric_version`（或增加 rubric_version）。

### 2.2 Correctness

| # | 问题 | 影响 |
|---|---|---|
| C1 | 模糊题 rubric 要求“条件分支与金标一致”，但金标本身是“信息不足”，没有分支 | Q35/Q36 的 0.3/0.2 可能重复 |
| C2 | 评分区间重叠且无优先级 | 0.3 vs 0.4-0.5、0.8-1.0 vs 0.6-0.9 不可判定 |
| C3 | 无答案 rubric 未限定“金标本身也是无答案” | 可把“答不出可答题”判成 1.0 |
| C4 | 删除了“不要因措辞不同扣分” | 改述可能被误扣分 |
| C5 | 删除了 missing_points / wrong_facts 的定义 | Q23 的 wrong_facts 不稳定 |
| C6 | “同时给出可以/不可以”没有覆盖 Q23 的“可以 + 已超时不符合” | 矛盾仍可能漏判 |
| C7 | 无 few-shot；未传入 answerability/category | 模糊/无答案 rubric 靠模型猜 |

**建议**：
- 把“与金标一致的条件分支”改为“条件分支与文档事实一致且不冲突；金标为信息不足时，给出分支 + 明确缺信息即可”；
- 使用不重叠区间并声明优先级；
- 无答案 rubric 仅在 gold 明确为“未提及/无法确认/信息不足”时启用；
- 恢复“不因措辞扣分”和 missing_points/wrong_facts 定义；
- Q23 类“首句肯定 + 后文否定”明确 ≤0.3，并写入 wrong_facts；
- 传入 `answerability/category`。

### 2.3 Relevancy

| # | 问题 | 影响 |
|---|---|---|
| R1 | 1.0 / 0.8~1.0 / “不自动满分”三处冲突 | 同一拒答可得不同分 |
| R2 | 判断“合理拒答”需要事实判断，与“不判断事实”冲突 | 与 Correctness 职责重叠 |
| R3 | 评分区间重叠 | 不可复现 |
| R4 | 条件式回答既可能 1.0 也可能 0.6-0.9 | Q35/Q36 不稳定 |
| R5 | 无 few-shot；无 answerability 输入 | 无答案/模糊题靠猜 |

**建议**：
- 合理拒答默认 0.8~0.9；只有完整回应 + 具体下一步才 1.0；删除“自动满分”冲突表述；
- 明确“拒答是否正确由 Correctness 判断，本指标只看是否围绕问题”；
- 使用不重叠区间；传入 answerability；
- 增加 Q29、Q35/Q36 few-shot。

### 2.4 跨指标与流程

1. **建议口径不一致**：Faithfulness 排除建议，Correctness 可能把缺少建议算 missing_points，Relevancy 又奖励下一步建议。
2. **错误拒答可被平均分掩盖**：Correctness 0.2 + Relevancy 0.9 ≈ 0.55；验收应使用分指标下限，不用简单平均。
3. **没有逐案例期望分数/容差/通过标准**：Q23/Q35/Q36/Q29/Q11/Q21 只列了案例，没有目标值和 no-regression 阈值。
4. **版本加载器未落地**：`RAG_JUDGE_PROMPT_VERSION` 未接入 `AgentConfig.version`，回退静默，根 `version.txt` 不是 `vX.Y.Z`；`prompt_version` 与 `prompt_sha256` 可能来自不同版本。
5. **标注分类不一致**：人工规范有 `insufficient_evidence/needs_recheck`，Judge 只有 `supported: bool`；Q29 建议句被标 unsupported，规范则应归 `non_factual`。
6. **测试策略不足**：stub 单测无法验证“0.8/≤0.3/1.0”这类语义期望，需要真实 LLM 评测 + 容差范围。

---

## 3. 基础字段复核发现

### 3.1 Pilot（10 条）

| ID | 状态 | 发现 |
|---|---|---|
| Q23 | `needs_recheck` | “第 2 天”跨午夜时可能未满 24 小时，题干需改为“超过 24 小时（如第 2 天）” |
| Q36 | `needs_recheck` | 原答案只写“信息不足”，缺条件分支；文档第 1 条“已激活虚拟商品”与第 12 条“虚拟商品一经售出”口径不一致 |
| Q35 | `ai_reviewed`（已修正） | 原答案把“收货地区”当成到货因素；文档只有发货时效，偏远地区只影响运费；已改为“发货 vs 到货”区分 |
| 其余 7 条 | `ai_reviewed` | 参考答案/证据/key_facts 基本正确，个别措辞已校正 |

### 3.2 剩余 30 条

| ID | 状态 | 发现 |
|---|---|---|
| Q14 | `needs_recheck` | 问句缺“发票是否已开具”，应标 `ambiguous`（参考答案已有两分支） |
| Q19 | `needs_recheck` | 问句缺“优惠券是否过期”，应标 `ambiguous`（参考答案已有两分支） |
| Q15 | `needs_recheck` | 分类 `multi` 不合适，建议 `direct` |
| Q16 | `needs_recheck` | 分类 `multi` 不合适，建议 `direct`/`constraint` |
| Q37 | `needs_recheck` | 原答案含文档外流程（订单中申请/填写抬头），已改为只依据文档事实 |
| Q40 | `needs_recheck` | 与 Q20 近似重复，建议删除或改写 |
| Q08 | `ai_reviewed` | key_fact 补“实付满 99 元”；偏远地区不包邮可作补充 |
| 其余 23 条 | `ai_reviewed` | 字段基本正确 |

### 3.3 35 条 Claim

| 结果 | 数量 | 说明 |
|---|---|---|
| `supported` | 32 | 均有提供上下文中的原文依据 |
| `unsupported` | 1 | **Q23#3**“可以按政策反馈”，且标记 `contradictory` |
| `insufficient_evidence` | 2 | **Q21#3** 质量问题不受 7 天限制；**Q29#2** 结算页建议 |
| `needs_recheck` | 1 | Q21#3（文档未规定普通商品质量问题期限） |
| `non_factual` | 1 | Q29#2 属操作建议，不应计入事实支持率 |

关键结论：**Q23 的矛盾能被 Claim 级评审发现，但当前 v1.1.0 Prompt 的 taxonomy 不能保证它进入分母**；**Q21 的推断型 supported 仍是盲点**。

---

## 4. 建议的下一步

1. **不实施当前 v1.1.0**（review verdict = approve_with_changes）。
2. 先修 Prompt/评分设计：
   - Faithfulness taxonomy、zero-denominator、evidence 必填、Q21 反例、few-shot；
   - Correctness 不重叠区间、answerability 输入、Q23 矛盾规则；
   - Relevancy 拒答分数统一、区间不重叠；
   - `metric_version` 升版或引入 `rubric_version`；
   - 版本加载器与 SHA/version 一致性。
3. 形成 v1.1.1（或 v1.2.0）后，**再次 subagent 复核**，再决定是否进入真实 10 条对比。
4. 人工定稿 9 条 `needs_recheck` 样本（Q23/Q36/Q14/Q15/Q16/Q19/Q37/Q40 + Q21 Claim），并确认虚拟商品口径。
5. 在这些完成前：不跑 v1.1.0、不跑 40 条、不宣布 Judge 验收通过、不进入 Phase 4。

---

## 5. 文件

- 机器可读：`docs/repair/phase3e/subagent-review.json`
- 本报告：`docs/repair/phase3e/subagent-review.md`
- 原始 Prompt 设计：`docs/repair/09-phase3e-prompt-v1.1-design.md`
- 人工审核表：`docs/repair/phase3e/human-review-*.csv`、`pilot-claims-review.csv`
- 待审清单：`docs/repair/phase3e/pending-review.md`
