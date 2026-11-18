# Prompt v1.2.0 设计草案

> 状态：设计草案；**语义规范已于 2026-11-18 冻结，v1.2.0 运行时未创建/未激活，目标未冻结**。本文不创建 v1.2.0 运行时版本，不修改 Prompt/Service/Schema/API/DB，不运行 Judge。
>
> 设计目标：从“逐案例补 few-shot”转为“先冻结 Judge 语义，再用通用规则与结构化 Schema 实现”。P0：`policy_scope` / `policy_relationship` 是 factual，不得退出 F 分母。

## 1. 背景与结论

v1.0.0 → v1.1.5 的经验：

- v1.1.x 的 10 条闸门多次通过，但每次扩到 40 条都会暴露新的语义边界（Q22/Q23/Q30/Q32/Q17）。
- 失败集中在三类：
  1. **non_factual 边界混用**：absence/uncertainty 被误建 factual；policy scope/relationship 被误移出 factual（P0）。
  2. **evidence quote 合成/跨行/标点**；
  3. **条件/目的/权益推断被过度 supported**。
- 逐案例 few-shot 会让 Prompt 膨胀，且不可证明覆盖；v1.2.0 必须用**统一 taxonomy + 结构化输出 + Service 校验**替代。

## 2. 设计原则

1. 语义优先：先定义“什么算 claim、什么进分母”，再写 Prompt。
2. 规则可复用：禁止案例 ID 特例；few-shot 只展示模式，不展示答案。
3. Schema 先行：claim 类型/子类型/状态由 Schema 约束，Prompt 只负责分类。
4. Service 守门：分母、skip、failed、evidence 降级、重复/冲突由 Service 统一处理。
5. 版本隔离：v1.0.0 保持 baseline；v1.2.0 默认 inactive；旧 Run 不混 SHA。
6. 可重复：高方差案例 3 次；报告全部结果，不报最好一次。

## 3. Faithfulness Prompt 方向

### 3.1 输出契约

建议 v1.2.0 Schema 使用更明确的 claim 类型（设计稿，不实现）：

```json
{
  "claim_id": "cl1",
  "claim": "...",
  "claim_type": "factual_claim | non_factual",
  "claim_subtype": "policy | condition | normative_requirement | fact | process | derived | policy_scope | policy_relationship | conflict | absence | doc_scope | doc_relationship | uncertainty | meta | advice | greeting",
  "support_status": "supported | unsupported | insufficient_evidence | null",
  "is_contradictory": false,
  "contradiction_with": [],
  "evidence_refs": [{"context_id": "C1", "quote": "..."}],
  "reason": "..."
}
```

关键变化：
- **P0 边界**：`policy_scope`、`policy_relationship` 是 factual；文档没有明确写时判 insufficient，留在 F 分母。`doc_scope`、`doc_relationship`、`absence`、`uncertainty` 才是 non_factual。
- `condition` 独立于 `policy`，用于条件/例外/时限。
- `normative_requirement` 独立，避免“需提供凭证”被误判 advice。
- 增加 `fact` / `process` / `derived`：派生结论（第 10 天 > 7 天、89 元+新疆运费 20）不再硬塞 policy。
- `conflict` 只在回答披露文档冲突时出现。
- v1.1.x 的 Q17/Q30 目标（通过把政策范围/关系移出分母得到）在 v1.2.0 下可能失效，必须重新审批。

### 3.2 Claim 提取规则

- 先判“是不是事实”，再判“支持不支持”。
- 一条 claim 一个可判定事实；混合句拆成 factual + non_factual。
- 事实部分：文档明确写的政策、条件、数字、时限、流程、规范性要求、派生结论。
- **政策范围/政策关系**：`policy_scope` / `policy_relationship` factual；无明确依据 → insufficient，不进 non_factual。
- 非事实部分：absence、doc_scope、doc_relationship、uncertainty、meta、advice、greeting。
- 目的/权益/补偿/取消/全称 generalization：默认 insufficient，除非文档明确写。
- 引用原文是回答内容；引用中的独立事实要拆；quote 必须来自 contexts。

### 3.3 Evidence 规则

- quote 只引 contexts 的最短连续子串。
- 允许保留原文标点；不得改写标点/补原文没有的标点；跨行保留换行；不得拼主语+谓词。
- 不得引用 answer 自身/括注。
- supported 必须有 evidence；insufficient 空数组；unsupported 可给矛盾证据。
- Service 继续做逐字校验、降级、重复/冲突检查。

### 3.4 Few-shot 策略

只保留模式级 few-shot，建议 5 组：

1. **Q23 型**：回答内部矛盾 + 最短子串（不按案例 ID）。
2. **Q30/Q17 型**：政策范围/关系断言 → factual；无依据 insufficient；只有文档覆盖/章节关系才 doc_scope/doc_relationship。
3. **Q20 型**：全称/适用范围断言 → policy_scope factual；无依据 insufficient。
4. **Q32 型**：无法确认/信息不足 → uncertainty/absence。
5. **Q36 型**：文档冲突披露 + “能否退款取决于……”是 condition/`policy_scope` factual，不是 meta；§1/§12 分条 + 两条单句证据；Q36 F 目标可保持 0.8–1.0，但不得靠排除条件句取得。

不再为 Q22/Q23/Q30/Q32/Q17 各加独立长 few-shot；用同一组模式覆盖。政策范围/关系不能通过 few-shot 教成 meta。

### 3.5 输出稳定性

- temperature 0.0；max_tokens 足够。
- 结构化失败重试一次；仍失败 → `failed`，不进入均值。
- 不允许 Service 用“默认 supported”兜底。

## 4. Answer Correctness Prompt 方向

- 以 gold_answer 的关键事实/条件/结论为准。
- `missing_points`：金标关键点未覆盖。
- `wrong_facts`：与金标/文档矛盾；**正确且相关的额外信息不算 wrong_fact**。
- 单一部分、直接完整回答，不因缺少额外步骤/建议降分。
- 不把“回答更长/更多建议”当作正确性加分。
- **v1.2.0 不启用 key_facts**：当前 C Prompt 只读 gold_answer；启用 key_facts 需要单独 Schema/输入改造，不在本版本范围。Q14 仍按已知 non-pass 记录（F unavailable + C 方差），不因 key_facts 被悄悄修好。
- Q14 类：回答缺“未开具前可以修改”是答案问题，不是 F 问题；C 应保留 `missing_points`。

## 5. Answer Relevancy Prompt 方向

- 只判断是否围绕问题、是否覆盖子问题/条件分支。
- 单一部分、直接完整回答 → 0.9–1.0；不得因“没有下一步建议”降到 0.7–0.8。
- 多部分/条件分支：遗漏子问题才降分。
- 合理拒答 + 下一步 → 0.9–1.0；套话/回避 → 0.3–0.6。
- 不因引用多/篇幅长扣分。
- Q16 类：回答与金标逐字一致，R 必须 0.9–1.0。
- R 的高方差需要独立校准集；不得只用 F 的 40 条。

## 6. Schema / Service 必要变化（设计）

### 6.1 Schema

- `claim_subtype` 扩展：`condition`、`normative_requirement`、`fact`、`process`、`derived`、`policy_scope`、`policy_relationship`、`uncertainty`、`doc_scope`、`doc_relationship`。
- `claim_type` 仍两类：factual_claim / non_factual。
- `support_status` 仅 factual；non_factual 为 null。
- `evidence_refs` 保持 `{context_id, quote}`；可增加 `validation_status`（设计）。
- 增加 Run 级 `prompt_version` / `schema_version` / `metric_version` 元数据（已有）。
- `policy_scope` / `policy_relationship` 归 factual；`doc_scope` / `doc_relationship` 归 non_factual。
- 不引入 `claim_scope`（回答/文档/通用）字段，避免过度设计；用子类型表达。

### 6.2 Service

- 分母：只统计 factual_claim；non_factual 全部排除。
- `skipped(no_scorable_claims)`：全部 non_factual。
- `skipped(context_unavailable)`：无上下文；F unavailable。
- `failed(schema)` / `failed(all_invalid)`：不进入均值。
- evidence：逐字校验、最短子串、answer 引用拒绝、降级、重复/冲突检查。
- 冲突：conflict 必须有两条互不为子串的 evidence；base 不因文档冲突扣分。
- 统计：HG/provisional 分组；C1-only/context_unavailable 单独列；known issue 分列。
- 浮点：`>0.10` 使用容差（`old - new > 0.10 + 1e-9`），恰好 0.10 不停止。

### 6.3 兼容性

| 版本 | 状态 | 默认 | 说明 |
|---|---|---|---|
| v1.0.0 | active_baseline | 是 | 不改 |
| v1.1.x | design_draft | 否 | 只读归档；新结果不混 SHA |
| v1.2.0 | design_only | 否 | 本文只设计；不创建运行时目录/不激活 |

- `RAG_JUDGE_PROMPT_VERSION` 默认仍 `v1.0.0`。
- v1.2.0 只有人工签字后才允许创建目录与运行。
- 任何 Schema 变更需要迁移/兼容层；旧 Run 不重算。

## 7. 测试矩阵

### 7.1 单元测试

- Prompt loader：v1.2.0 manifest/SHA/版本映射。
- Schema：claim_type/subtype/status/evidence/contradiction/conflict。
- Service：
  - non_factual 不进分母；
  - supported 无 evidence 降级；
  - quote 非逐字降级；
  - duplicate claim_id；
  - conflict 单边证据；
  - context_unavailable / no_scorable / failed；
  - 浮点 0.10 边界。
- 版本：v1.0.0 默认、v1.2.0 显式选择、旧版本兼容。

### 7.2 Fixture 矩阵

| 类型 | 案例 | 断言 |
|---|---|---|
| 直接回答 | Q05/Q13/Q16/Q37/Q40 | F/C/R 不低于目标；R 不因缺建议降分 |
| 多部分 | Q11/Q12/Q18/Q19/Q22 | 子问题覆盖；不误合并 |
| 约束/运算 | Q21/Q23/Q24–Q28 | Q21#3 insufficient；Q23 内部矛盾；Q28 权益推断 insufficient |
| absence/无法确认 | Q29/Q30/Q31/Q32/Q33 | absence/meta/uncertainty 不进分母；skip 边界 |
| 冲突/模糊 | Q35/Q36/Q37–Q40 | 冲突披露；两条单句证据；base 不扣冲突 |

### 7.3 集成测试

- 10 条闸门：Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36。
- 40 条规模/回归：13 HG + 27 provisional；补齐 Q33–Q40 与 6 条 baseline。
- 高方差重复：Q14/Q16/Q17/Q23/Q30/Q32 各 3 次。
- 每层报告 HG/provisional 分组，不混均值。

### 7.4 负向测试

- quote 跨行拼接；
- quote 主语+谓词合成；
- quote 引用 answer；
- absence 标 factual；
- 把 `doc_scope` / `doc_relationship` / `uncertainty` 标成 factual；
- 把 `policy_scope` / `policy_relationship` 标成 non_factual（P0 错误）；
- 全称 generalization；
- supported 无 evidence；
- 重复 claim_id；
- conflict 单边证据；
- context_unavailable 标 0；
- all invalid 标 skip；
- 恰好 0.10 误停。

## 8. 实验与成本

| 阶段 | 内容 | 预计成本 |
|---|---|---:|
| 单案例 | Q14/Q16/Q17/Q23/Q30/Q32 各 3 次 | ¥0.3 |
| 10 条闸门 | v1.2.0 双版本 | ¥0.6 |
| 40 条 | 40 条 + 6 条 baseline 补齐 | ¥1.4–1.8 |
| 重复/异常 | 高方差复跑 | ¥0.2–0.4 |
| 直接合计 |  | **¥2.5–3.1** |
| 30% 缓冲 | 模型/重跑/失败 | **¥0.8–0.9** |
| **建议预算** |  | **¥3.3–4.0** |

成本按 DashScope 实际账单重算；不包含人工审核时间。已花 v1.1.x 约 ¥5–6，完整程序总预算按 ¥8–10 分阶段签字。

## 9. 风险与未解决问题

| 风险/问题 | 影响 | 处理 |
|---|---|---|
| 语义规范过严/过松 | F 分布移动 | 先用 13 HG + 10 条校准，不直接开 40 |
| 模型仍把 absence 标 factual | 分母污染 | Schema 子类型 + Service 守门 + 负向测试 |
| quote 合成仍发生 | HG 降级 | 最短子串 + answer 引用拒绝 + 3 次重复 |
| Q36 冲突口径未选边 | 无法定义 canonical | 只验证披露；业务确认后再选边 |
| Q14 金标/答案差异 | C 目标争议 | 保留 missing_points；不因 F 失败改 C |
| Q21#3 单 claim | 与整条 F 混淆 | 单 claim 与整条分开报告 |
| Q30/Q32 目标边界 | 目标漂移 | 先改语义，再注册目标；不先移动目标 |
| P0 政策范围/关系回到 factual | Q17/Q30 的 v1.1.x 目标失效 | 重新审批 Q17/Q30 目标，不静默沿用 1.0 |
| absence/uncertainty 分类变化 | Q19/Q31/Q32/Q35 的 F/目标变化 | 冻结后重跑 baseline；Q32 目标重新注册 |
| Q14 key_facts 未启用 | C 仍 known non-pass | v1.2.0 不启用 key_facts；Q14 保留 non-pass |
| 8 条未运行/6 条 baseline 缺失 | 40 条不完整 | 先补 baseline，再算整体 |
| 40 条 final_labels 已冻结 | 分类与目标混淆 | 40 条报告只用 `pilot-40-final-labels.json`（SHA `f139623f…`）；目标另批 |
| C/R 高方差 | 单次结论不可靠 | 3 次重复 + 独立校准集 |
| 成本超预算 | 无法完成 | 分阶段：单案例→10 条→40 条，逐段签字 |

## 10. 交付与下一步

本文只交付设计。建议下一步（需人工批准）：

1. 语义规范已于 2026-11-18 冻结（`12-judge-semantic-spec.md`）；冻结后不再改语义，任何变化需新 freeze record。
2. 40 条 final_labels 已冻结：`pilot-40-final-labels.json`，SHA `f139623f…`；13 条 HG 来自 `human-gold.json`，27 条 provisional 来自 `candidates.json`；40 条报告只能使用该文件。
3. 重新审批目标：使用 `pilot-40-targets-v1.2.0-reapproval.json` / `.md`（Q17/Q30/Q32/Q19/Q20/Q31/Q35/Q36/Q14）；签字前不生成 active target。
4. 设计 v1.2.0 Schema / Service / 子类型：`fact` / `process` / `derived` / `policy_scope` / `policy_relationship` / `doc_scope` / `doc_relationship`；分母、evidence、skip/failed 按冻结规范。
5. 先写负向测试（policy_scope 误归 meta、Q36 条件句误归 meta、absence 进分母等），再做单案例、10 条、40 条。
6. 不创建/激活 v1.2.0，不跑 Judge；等 Schema/目标设计复核后再申请运行。
7. 任何阶段失败按 `13-phase3e-acceptance-plan.md` 停止，不累积 known miss。

## 11. 一句话总结

**v1.2.0 不是“再加几条 few-shot”，而是把 Claim 语义、Evidence 契约、non_factual 边界、skip/failed 边界固化成 Schema + Service + Prompt 三方一致的规范。**
