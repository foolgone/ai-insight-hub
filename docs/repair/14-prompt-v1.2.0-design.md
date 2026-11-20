# Prompt v1.2.0 设计与冻结提案（M1-D-0）

> 状态：设计已通过；2026-11-20 人工批准 **metadata-only freeze**（`status=frozen`、`active=false`，见 `27-m1d0-prompt-freeze-record.md`）。**未激活、未跑 Judge、未上生产。**
> 日期：2026-11-20。
> 范围：修订 v1.2.0 Prompt 设计；创建 `backend/app/prompts/rag_judge/v1.2.0/` 下的 3 个 Prompt、MANIFEST 与 version.txt；补 loader / Schema v3 / v1-v2 回归测试；输出 SHA 与冻结提案。
> 明确不做：跑 Judge（单案例/10 条/40 条）、激活 v1.2.0、修改 v1.0.0/v1.1.x Prompt、修改 Schema v2 语义、修改 r2 / 目标 v1.0.2 / Human Gold / provisional、修改 C2 migration 022、启动 M2/M3、混入 C3 P2 小修、自行宣布 M1-C 或 M1-D accepted。

## 1. 结论

1. v1.2.0 使用 **Schema v3** 与 **metric v3**；Prompt 只负责 claim 分类、支持状态和证据，不计算总分。
2. Faithfulness 采用 **r2 双指标**：
   - `faithfulness` = **F_coverage** = `S / (S + U + I)`；
   - `faithfulness_strict` = **F_strict** = `S / (S + U)`，只作诊断。
3. `faithfulness_strict` 由 Service 从同一次 Faithfulness 输出派生，**不写第二个 Prompt、不额外调用 LLM、不进入 `RAG_JUDGE_METRICS`、不写入 `judge_metrics`**。
4. 旧单 F / 单 A 口径已删除；v1.2.0 不再用“排除 insufficient 后的单 F”或“单独 A 指标”描述 Faithfulness。
5. v1.2.0 资产状态为 `frozen`、`active=false`、`runtime_active=false`；默认 `RAG_JUDGE_PROMPT_VERSION` 仍为 `v1.0.0`。
6. 冻结已由人工批准且为 metadata-only；激活、默认版本切换与 Judge 均需另行批准，不得自行改 `active=true`。

## 2. 冻结输入

| 资产 | SHA256 / 版本 | 状态 |
|---|---|---|
| Judge 语义规范 `12-judge-semantic-spec.md` | 2026-11-18 frozen | 未改 |
| r2 双指标契约 `19-m1b-003-freeze-draft.md` | `M1-B-003-r2` | `freeze_draft_pending_human`；本次只对齐 |
| Schema v3 / Service 设计 `15-phase3e-v1.2.0-schema-service-design.md` | Schema v3 | C1–C4 已实现 |
| 目标表 `pilot-40-targets-v1.2.0-v1.0.2.json` | `3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846` | 只读 |
| final labels `pilot-40-final-labels.json` | `f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb` | 只读 |
| 静态重算 `m1b003-static-recalc.json` | `53787fbb2a434953354bd821b62581e6e56ba5db10751149c236f1e7656437bb` | 只读 |
| C4 静态目标 `m1c-c4-static-targets.json` | `3ead3bdf8e354d3968d6dcc77561068d9c2a455ec42070e16dda20e58d2c5f44` | 只读 |
| C4 40 条盘点 `m1c-c4-inventory.json` | `581b71589b801849e7f6c045aead88d67741d164a0689ca1bae5b51eecc9d326` | 只读 |
| v1.2.0 Prompt 目录 | `backend/app/prompts/rag_judge/v1.2.0/` | `frozen`（metadata-only） |

目标使用 v1.0.2；旧 `pilot-40-targets-v1.2.0.json`（`34357b34…`）只作历史，不覆盖、不混用。Q17/Q32 的 v1.2.0 值仍是预期标签，不是实测。

## 3. 指标契约（r2）

### 3.1 分桶

| 桶 | 条件 | 是否进入分母 |
|---|---|---|
| `S` | `factual_claim` + `support_status=supported` | 进入 F_coverage 与 F_strict |
| `U` | `factual_claim` + `support_status=unsupported` | 进入 F_coverage 与 F_strict |
| `I` | `factual_claim` + `support_status=insufficient_evidence` | 只进入 F_coverage |
| `N` | `non_factual`（7 种） | 不进入任何 F 分母 |

`invalid(contract_violation)` 与 `failed(execution)` 不进入任何桶，整条 metric 无分数。

### 3.2 公式与展示

```text
F_coverage (faithfulness)        = S / (S + U + I)   if S + U + I > 0
F_strict   (faithfulness_strict) = S / (S + U)       if S + U > 0
```

- `F_strict >= F_coverage`（两者都 evaluated 时）；`I=0` 时相等。
- `F_strict=1.0` 只表示“可判定 claim 中没有 unsupported”，**不表示没有矛盾，也不表示全部 factual 都被支持**。
- 展示名：`faithfulness` = “Faithfulness（证据覆盖）”；`faithfulness_strict` = “Strict Faithfulness（可判定事实）”。
- `unsupported` 展示为“未被上下文支持”，不得写成“矛盾”；矛盾只看 `is_contradictory` / `contradiction_with`。
- `faithfulness_strict` 不挂目标、不参与目标通过率、不进入 `judge_metrics`。

### 3.3 状态边界

| 场景 | `faithfulness` | `faithfulness_strict` | Item 状态 |
|---|---|---|---|
| 有 S/U | `evaluated S/(S+U+I)` | `evaluated S/(S+U)` | `evaluated` |
| 全部 insufficient（S=0,U=0,I>0） | `evaluated 0.0` + `all_insufficient=true` | `skipped(no_decidable_claims)` | `evaluated` |
| 全部 non_factual | `skipped(no_scorable_claims)` | 同左 | `skipped` |
| 无上下文 | `skipped(context_unavailable)` | 同左 | `skipped` |
| 契约违约 | `invalid(contract_violation)` | 同左 | `invalid` |
| 执行失败 | `failed(execution)` | 同左 | `failed` |

- `context_unavailable` / `invalid` / `failed` 优先于分桶计分。
- `invalid` 与 `failed(execution)` 必须分开；invalid 不得解释为执行失败。
- 全 insufficient 是 `evaluated 0.0`，不是 skip；strict 的 skipped 只是该 metric 的终态。

### 3.4 派生关系

- 一次 Faithfulness Judge 调用只产生一份 claims/evidence/raw output。
- Service 先写主结果 `faithfulness`，再由同一份 claims 派生 `faithfulness_strict`。
- 派生结果保存 S/U/I 计数、F_strict、`derived_from_result_id` 与同一 `judge_config` 摘要；不重复保存完整 claims/evidence/raw output。
- coverage invalid/failed/skipped 时，strict 必须同状态，不得有分数。
- 只有 coverage 存在且 current 时，才允许从它重新派生 strict；只缺 strict 不重新调用 Judge。

## 4. Schema v3 契约

### 4.1 16 个 claim_subtype

| factual_claim（9） | non_factual（7） |
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
- `claim_type` 只有 `factual_claim` / `non_factual`。
- `claim_subtype` 必填，且必须与 `claim_type` 匹配；缺/非法/type 不一致 → 整条 `invalid(contract_violation)`。
- factual 必须有 `support_status`；non_factual 必须为 `null`；违反 → 整条 invalid。
- `policy_scope` / `policy_relationship` 是 factual；无明确依据时 `insufficient_evidence`，不得转 non_factual。
- `doc_scope` / `doc_relationship` 只表示文档覆盖/章节关系，不表示政策范围/政策关系。
- `conflict` 只在回答披露文档冲突时出现。

### 4.2 evidence_refs

- v3 canonical evidence 是 `evidence_refs: [{context_id, quote}]`。
- 旧 `evidence`（字符串数组）只用于 v1/v2 解析；v1.2.0 输出 `supported` 但只有旧 `evidence`、没有 `evidence_refs` → invalid，不得自动迁移。
- 旧 `supported`（布尔）在 v3 是禁止字段；必须用 `support_status`。
- `context_id` 只能是输入中真实存在的 C1..Cn，不是文档章节号。
- `quote` 必须是该上下文的逐字连续子串；允许保留原文标点；不得改写、拼接、补主语/谓词、跨行去换行。
- `supported` 必须有至少一条有效 evidence；`insufficient_evidence` 必须为空；`unsupported` 可带矛盾证据。
- `conflict` 必须有两条去重且互不为子串的 evidence。

### 4.3 invalid 契约

以下任一情况，整条 metric `invalid(contract_violation)`，无分数、不进分母/均值、不降级、不 drop：

- 缺 `claim_type` 或 `claim_subtype`；
- 子类型不在对应枚举内，或 `claim_type` 与 `claim_subtype` 不一致；
- factual 缺 `support_status`，或 non_factual 带 `support_status`；
- `supported` 无有效 `evidence_refs`；
- `insufficient_evidence` 带 `evidence_refs`；
- `context_id` 不存在；
- `quote` 为空、非逐字、跨片段拼接、引用 answer；
- `conflict` 单边、两条相同或互为子串；
- 使用旧 `supported` / `evidence` 代替 v3 字段。

`unsupported` 是合法评价结果：evidence 真实存在但不支持 claim，或回答与上下文矛盾，都判 `unsupported`，不是 invalid。

## 5. Faithfulness Prompt 设计

### 5.1 输入与输出

输入：`query`、`answer`、`contexts`、`context_ids`。
输出：`claims[]` + `reason`；每条 claim 含 `claim_id`、`claim`、`claim_type`、`claim_subtype`、`support_status`、`is_contradictory`、`contradiction_with`、`evidence_refs`、`reason`。

Prompt 明确要求：
- 不输出总分；
- 不输出旧字段 `supported` / `evidence`；
- 不计算 F_coverage / F_strict；
- 不自行 skip / invalid；由 Service 判定。

### 5.2 分类顺序

1. 先判是否 factual_claim。
2. 是 factual 才判 `support_status`。
3. 再检查 evidence 逐字性与充分性。
4. 最后判回答内部矛盾 / 文档冲突。
5. 不得因为找不到 evidence 就把 factual 改 non_factual。

### 5.3 P0 范围/关系边界

| 句子 | 分类 | 支持状态 |
|---|---|---|
| “文档未说明是否支持海外配送” | `absence`（non_factual） | 不进分母 |
| “无法确认积分支持礼品兑换” | `uncertainty`（non_factual） | 不进分母 |
| “文档详细说明了退款、换货、发票……” | `doc_scope` / `meta`（non_factual） | 不进分母 |
| “政策适用于所有订单” | `policy_scope`（factual） | 明确写 → supported；否则 insufficient |
| “该规则与是否满 99 元无关” | `policy_relationship`（factual） | 明确写 → supported；否则 insufficient |
| “能否退款，取决于具体商品类型和签收时间” | `condition` / `policy_scope`（factual） | 文档写了普通/特殊规则 → supported |
| “默认适用于中国大陆境内订单” | `policy_scope`（factual） | 明确写 → supported；否则 insufficient |
| “两处条款对虚拟商品范围表述不一致” | `conflict`（factual） | 两处原文都可给出 → supported |

“取决于/区分/需确认”优先 `condition`；`policy_scope` 只用于“适用于哪些订单/地区/对象”。两者都是 factual，不影响是否进入 F 评价。

### 5.4 分类优先级与原子性

- 一条 claim 一个可判定事实；混合句必须拆分。
- 全称/排除性表述（所有/任何/一律/均/默认/不受……限制）必须有明确依据，否则 insufficient。
- 目的、权益、补偿、取消、催单推断没有明确条款时 insufficient。
- 引用块、转述原文、`<kb ...>` 前原文都是回答内容；其中每个独立事实都要建 claim。
- 先输出结论 claim，再按出现顺序输出其余 claim；`claim_id` 用 `cl1..cln`。
- 不评价语气、格式、长度。

### 5.5 Evidence 规则

- 只引 contexts 的逐字连续子串；最短子串优先。
- 不得拼接两个不连续片段；不得把前一分句主语拼到后一分句谓词。
- 不得引用 answer 自身、query、模型知识或括注。
- 跨行引用保留换行；更稳妥是只引单行。
- 找不到逐字证据时，按事实类型判 insufficient；不要伪造 quote。
- `conflict` 两条 quote 必须来自两处不同表述，且互不为子串。

### 5.6 矛盾与冲突

- 回答内部矛盾：`is_contradictory=true` + `contradiction_with=[claim_id]`；仍判 support_status。
- 回答 vs Context 矛盾：`support_status=unsupported`，不用 `is_contradictory` 冒充。
- 文档冲突：`claim_subtype=conflict`，`is_contradictory=false`；回答未披露时不输出 conflict claim。两处逐字证据无法给出时，不输出 conflict claim，改按可确认的 policy/condition 或 uncertainty 输出。
- `conflict` 不是 unsupported；不得把文档冲突判成回答内部矛盾。

### 5.7 无有效 claim

- 全部 non_factual / 无 claim：输出 `reason="no_scorable_claims"`；Service 判 `skipped(no_scorable_claims)`。
- 全部 factual insufficient：仍输出 claims；Service 判 coverage `evaluated 0.0`、strict `skipped(no_decidable_claims)`。
- 部分可判定、部分 insufficient：正常输出，Service 分桶统计。

### 5.8 Few-shot 策略

只保留模式级 few-shot，不绑定案例 ID：
1. 政策 + 规范性要求 + 建议；
2. 政策范围/关系 vs 文档覆盖/absence；
3. 条件 + 文档冲突 + 不确定性。

不写 Q 编号，不为单案例加特例；模式覆盖分类、证据和 invalid 边界。

## 6. Answer Correctness Prompt 设计

- 继承 v1.1.5 的 C 评分区间与“额外正确信息不扣分”规则。
- 从 `gold_answer` 推断 unanswerable / ambiguous / answerable / unknown；输入契约没有 `answerability` 字段。
- `missing_points` 只列金标中有、回答未覆盖的事实/条件；建议不算 missing point。
- `wrong_facts` 只写与金标/文档矛盾的事实；正确且相关的额外信息不写。
- 首句/结论与后文矛盾 → `0.0–0.2`。
- 文档冲突披露：披露 + 条件分支 → `0.9–1.0`；单边口径未披露 → `0.5–0.6`；声称“文档统一规定” → `0.3–0.4`；编造规则 → `0.0–0.2`。
- 不根据 Faithfulness 的 claim 分类改变 C 分数。
- 不启用 `key_facts`；Q14 的已知 non-pass 不因本版本被悄悄修好。
- 移除案例 ID 标签，保留模式级 few-shot。

## 7. Answer Relevancy Prompt 设计

- 只判断是否围绕问题、是否覆盖子问题/条件分支。
- 不判断事实正确性、上下文依据；不因回答包含更多事实/建议加分。
- 单一部分、直接完整回答 → `0.9–1.0`；不得因“没有下一步建议”降到 `0.7–0.8`。
- 合理拒答 + 下一步 → `0.9–1.0`；套话/回避 → `0.3–0.6`。
- 多部分问题：全部覆盖 → `0.9–1.0`；部分 → `0.7–0.8`；只回应一个子问题/泛泛政策 → `0.5–0.6`；遗漏核心 → `0.0–0.4`。
- 移除案例 ID 标签，保留模式级 few-shot。

## 8. 资产、MANIFEST 与版本隔离

### 8.1 资产

| 文件 | SHA256 |
|---|---|
| `faithfulness.txt` | `b637775869163fdd7bd2545ca9b79197c10193d2937c9bef4e61add72e934d61` |
| `answer_correctness.txt` | `a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95` |
| `answer_relevancy.txt` | `a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88` |
| `MANIFEST.json`（frozen） | `ee1c25be8767bf66069f92e769fd8dd1d986cb950d9e96d3f550af587c35f778` |
| `MANIFEST.json`（冻结前 `design_draft`，`071c3b6`） | `5a98be00f8762a67d12b453f70dd17eea6228949a48914339740d8412e8e6a7b` |
| `version.txt` | `v1.2.0` |
| `m1d-prompt-v1.2.0-validation.json`（frozen） | `21326f2cb3d275a7fe84291a87c2a04243e57dab23d0be2abd8fa27a42beb5f8` |
| `m1d-prompt-v1.2.0-validation.json`（冻结前 `design_draft`） | `907886bd0ad86a0f335f346966efed939a36be1ea852d608b9aa2623ffc7d493` |
| `m1d_prompt_assets_validate.py` | `bddb26e6935b4673d87d366c07abcc21b0403ce05cc7220a51c8eae1e69d4490` |

### 8.2 MANIFEST 必填字段

| 字段 | 值 |
|---|---|
| `version` | `v1.2.0` |
| `status` | `frozen` |
| `active` | `false` |
| `frozen` | `true` |
| `runtime_active` | `false` |
| `schema_version` | `rag_judge_schema_v3` |
| `rubric_version` | `v1.2.0` |
| `metric_version_mapping.faithfulness` | `v3` |
| `metric_version_mapping.faithfulness_strict` | `v3` |
| `judge_metrics` | 只含 F/C/R，**不含** `faithfulness_strict` |
| `derived_metrics` | `["faithfulness_strict"]` |
| `default_prompt_version` | `v1.0.0` |

### 8.3 版本兼容

| 版本 | Schema | Metric | 默认 | 状态 | 说明 |
|---|---|---|---|---|---|
| `v1.0.0` | v1 | v1 | 是 | `active_baseline` | 不改 |
| `v1.1.1`–`v1.1.5` | v2 | v2 | 否 | 只读归档 | 不改；旧结果不混 SHA |
| `v1.2.0` | v3 | v3 | 否 | `frozen`（未激活） | 显式选择才加载；`active=false` |

- `RAG_JUDGE_PROMPT_VERSION` 默认仍 `v1.0.0`。
- 目录存在不会自动切换默认版本；默认解析不读取 v1.2.0。
- 显式选择 v1.2.0 时，loader 校验 MANIFEST 的 `schema_version` 与版本映射一致；不一致直接报错。
- v1.0.0 / v1.1.x Prompt 文件与 SHA 不变；v1/v2 测试原样通过。
- 跨版本结果不得混算均值；报告必须写 `prompt_version + schema_version + metric_version + prompt_sha256`。

## 9. 测试矩阵

### 9.1 Prompt loader / MANIFEST

- v1.2.0 MANIFEST 可读取，`version` / `schema_version` / `rubric_version` / `status` / `active` 正确。
- 3 个 Prompt 均注册，文件存在，SHA256 与 MANIFEST 一致。
- 显式 `prompt_version="v1.2.0"` 可加载，schema=v3、metric=v3、output schema=`FaithfulnessOutputV3`。
- 默认设置 `RAG_JUDGE_PROMPT_VERSION=v1.0.0` 时仍加载 v1.0.0；v1.2.0 目录存在不改变默认。
- MANIFEST schema 与版本映射不一致 → `RagJudgePromptError`。
- v1.2.0 的 `judge_metrics` 不含 `faithfulness_strict`；strict 只在 `derived_metrics`。

### 9.2 Schema v3

- 9 个 factual subtype、7 个 non_factual subtype 均可解析。
- factual 缺 `support_status` → 拒绝；non_factual 带 `support_status` → 拒绝。
- supported 无 evidence → 拒绝；insufficient 带 evidence → 拒绝。
- conflict 少于两条 evidence → 拒绝。
- 旧 `supported` / `evidence` 字段 → 拒绝（`extra="forbid"`）。
- 缺/非法 subtype、type 与 subtype 不一致 → 拒绝。
- v1/v2 payload 仍可解析；旧 `supported` / `evidence` 在 v2 模型上不被误删。

### 9.3 Service v3（已由 C3 覆盖，本轮只回归）

- S/U/I/N 分桶；N 不进分母；I 不进 F_strict。
- supported 无 evidence / context_id 不存在 / quote 非逐字 / conflict 单边 → 整条 invalid。
- 全 insufficient → coverage evaluated 0.0、strict skipped。
- 全 non_factual → coverage/strict skipped。
- invalid 不进均值；strict 由 coverage 派生；retry 不重新调用 Judge 只补 strict。
- summary 只统计 root Run；retry 子 Run 不进入 summary。

### 9.4 v1/v2 回归

- v1.0.0 默认仍加载 v1 schema/metric v1。
- v1.1.1–v1.1.5 仍加载 v2；Prompt 文本与 SHA 不变。
- v1.1.x 的 `supported` / `evidence` 旧 payload 仍可解析。
- v1.2.0 存在不影响 v1/v2 行为。

### 9.5 负向测试

- 把 `policy_scope` / `policy_relationship` 标成 non_factual；
- 把 `doc_scope` / `doc_relationship` 标成 factual；
- 把 absence 标成 factual/policy；
- supported 无 evidence；
- quote 跨行拼接、主语+谓词合成、引用 answer；
- conflict 单边/嵌套；
- 用旧 `supported` / `evidence` 代替 v3 字段；
- 把 `faithfulness_strict` 写进 `judge_metrics`；
- 默认版本被 v1.2.0 目录意外改变。

## 10. 冻结提案与结果

### 10.1 本轮已完成

- 修订本设计文档，删除旧单 F / 单 A 口径，明确双指标、Schema v3、invalid、strict 派生。
- 创建 `v1.2.0/faithfulness.txt`、`answer_correctness.txt`、`answer_relevancy.txt`。
- 创建 `MANIFEST.json`（v3、rubric v1.2.0）与 `version.txt`；初始 `design_draft`，后按人工批准改为 `frozen`。
- 记录 3 个 Prompt 与 MANIFEST 的 SHA256。
- 增加 loader / Schema v3 / 默认版本隔离 / v1-v2 回归测试。
- 静态校验 22/22 通过；冻结前 validation SHA `907886bd…`，冻结后 `21326f2c…`。
- 输出冻结提案、freeze record 与 activation requirements。

### 10.2 状态

| 项 | 状态 |
|---|---|
| v1.2.0 Prompt 资产 | `frozen` |
| active | `false` |
| frozen | `true` |
| 默认版本 | `v1.0.0` |
| Judge 运行 | 未运行 |
| 生产 | 未上线 |
| M1-C | 未 accepted |
| M1-D | 未 accepted |

### 10.3 人工审核项

1. 3 个 Prompt 正文是否与 r2 / Schema v3 / 语义规范一致。
2. 16 个 subtype 的定义、优先级与 P0 边界是否可接受。
3. evidence / invalid 规则是否过严或过松。
4. few-shot 是否仍含案例特例（本轮已移除案例 ID，保留模式）。
5. MANIFEST 的 `status` / `active` / `derived_metrics` 是否正确。
6. metadata-only freeze 已批准；10 条 Judge 尚未批准。

### 10.4 Activation requirements

冻结与激活分开；冻结已完成，激活仍需全部满足：

1. 人工审核通过本设计与 3 个 Prompt 正文（已完成）。
2. 人工审核通过 MANIFEST 字段与 SHA（已完成）。
3. 另开 freeze record，明确 `status=frozen`、审核人、日期与 SHA（已完成，见 `27-…`）。
4. 单独批准 10 条 Judge；10 条通过后才申请 40 条。
5. 40 条 Judge 报告必须写 `prompt_version + schema_version + metric_version + prompt_sha256`。
6. 激活默认版本必须是单独变更，不得在本轮或冻结时顺带修改 `RAG_JUDGE_PROMPT_VERSION`。
7. 未完成以上步骤前，v1.2.0 只可显式加载，不得成为默认，不得上生产。

## 11. 边界声明

- 本轮**未跑 Judge**：单案例、10 条、40 条均未运行。
- 本轮**未激活 v1.2.0**：默认仍 `v1.0.0`，MANIFEST `active=false`。
- 本轮**未修改** v1.0.0 / v1.1.x Prompt、Schema v2 语义、r2 冻结草案、目标 v1.0.2、Human Gold / provisional、migration 022。
- 本轮**未启动** M2 / M3，**未混入** C3 P2 小修。
- 本轮**未宣布** M1-C / M1-D accepted；状态为 `frozen` / `active=false`，仍未 accepted。
- Q17/Q32 的 v1.2.0 值仍是预期标签，不是实测；Q14/Q33 仍按 context_unavailable 处理；40 条 baseline_missing 仍写 `baseline_delta: unavailable`。

## 12. 一句话总结

**v1.2.0 用 Schema v3 把 16 个 claim 子类型、逐字证据和 invalid 契约写进 Prompt，用 r2 双指标把 F_coverage 与诊断性的 F_strict 分开；strict 由 Service 派生，不写第二个 Prompt，默认版本仍为 v1.0.0。**
