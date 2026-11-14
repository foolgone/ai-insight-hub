# Phase 3E · Prompt v1.1.0 设计（未激活）

**日期**：2026-11-14
**状态**：**设计稿 + 人工基准准备**；未切换版本、未运行 v1.1.0、未改 Phase 3C 数据库/API、未新增 Agent。
**基线**：Prompt v1.0.0（Pilot 10 条，qwen-max，30/30 结构化，评分质量暂不通过）。

---

## 1. 版本管理

| 版本 | 位置 | 状态 | SHA-256 |
|---|---|---|---|
| v1.0.0 | `backend/app/prompts/rag_judge/`（根目录，线上生效） | 活跃基线，**不覆盖** | F `287053e9…` / C `106e11f2…` / R `27203126…` |
| v1.0.0 归档 | `backend/app/prompts/rag_judge/v1.0.0/` | 只读副本 + `MANIFEST.json` | 同上 |
| v1.1.0 | `backend/app/prompts/rag_judge/v1.1.0/` | **pending_review，未激活** | F `d113653b…` / C `c3f7fc6b…` / R `e17ed6bb…` |

- 根目录 `version.txt` **未修改**，当前仍按 v1.0.0 运行；
- v1.0.0 的 Pilot 结果保留在 `docs/repair/phase3e/pilot-judge-results.json`；
- 两个版本的 `MANIFEST.json` 记录版本、SHA、状态、修改理由与关联案例；
- v1.1.0 不覆盖任何历史文件。

完整 Prompt diff：`docs/repair/phase3e/prompt-v1.1.0.diff`

---

## 2. 修改理由与对应 Pilot 案例

### 2.1 Faithfulness

| 修改 | 理由 | 案例 |
|---|---|---|
| 结论句必须作为第一条 claim | 旧版漏掉首句结论，导致 Q23 的“可以按政策反馈”未被判定 | Q23 |
| `claim_type`: `factual_claim` / `non_factual` / `contradictory` | 旧版把操作建议与事实断言混在一起，长回答被过度扣分 | Q11、Q35 |
| `non_factual` 不进入分母 | 合理建议/下一步不应压低 Faithfulness | Q11、Q35 |
| 含事实承诺的建议仍按 factual_claim | 避免用“建议”包装事实承诺逃避判断 | Q01、Q29 |
| `contradictory` 作为诊断标签，仍判断 supported | 需要同时保留“是否支持”和“是否自相矛盾”两个信息 | Q23 |
| 无 claim 继续 skipped | 保持既有规则 | — |

**注意**：v1.1.0 输出新增 `claim_type` / `contradiction_with`；当前 v1.0.0 的运行时代码/输出 schema 尚未支持，激活前必须完成第 4 节的代码改动。

### 2.2 Correctness

| 修改 | 理由 | 案例 |
|---|---|---|
| 模糊问题条件式回答 0.8~1.0 | 旧版把“给出条件分支 + 要求补充信息”判成 0.3/0.2 | Q35、Q36 |
| 泛泛政策但未结合条件 0.4~0.6 | 区分“有条件的合理回答”与“只背政策” | Q35、Q36 |
| 无依据确定性结论 ≤0.3 | 防止信息不足时强行下结论 | Q36 |
| 无答案问题：正确拒答 1.0，编造 ≤0.2 | 旧版对“文档未提及”判分偏低/偏高不稳定 | Q29、Q31 |
| 首句/后文矛盾或同时给出可以/不可以 ≤0.3 | 旧版 Q23 漏判首句矛盾，给 0.8 | Q23 |

阈值不是普遍真理：仅作为 v1.1.0 的初始 rubric，必须用相同 10 条 Pilot 复核后再决定是否调整。

### 2.3 Relevancy

| 修改 | 理由 | 案例 |
|---|---|---|
| 只评价是否围绕问题展开 | 避免与 Correctness/Faithfulness 职责重叠 | 全部 |
| 合理拒答/信息不足/下一步建议可 0.8~1.0 | 旧版把正确的“无法确认”判 0.6 | Q29 |
| 合理拒答不自动 1.0 | 防止所有无答案回答被无条件满分 | Q29、Q31 |
| 正确拒答 vs 错误拒答交给 Correctness | Relevancy 不判断事实对错 | Q29、Q31 |

---

## 3. 人工标注准备

| 文件 | 内容 |
|---|---|
| `annotation-spec.md` | 字段定义、状态机、Claim 标签规则、审核流程 |
| `human-review-pilot.csv` | 10 条 Pilot 基础字段审核表（human 列全空） |
| `human-review-remaining.csv` | 剩余 30 条基础字段审核表（human 列全空） |
| `pilot-claims-review.csv` | 10 条 Pilot 的 35 条 Claim 审核表 |
| `human-gold.template.json` | 40 条 Human Gold 模板；`human` 字段全空，AI 草稿单独存放 |
| `pending-review.md` | 40 条待审清单 |

规则：

- `candidates.json` 保留 `provenance=auto_generated`、`review_status=pending_human`；
- AI 预标注（`pilot-labels.ai-draft.json`）与 Human Gold 独立保存；
- 不确定样本标 `needs_recheck`，不得强行赋值；
- 只有 `approved` 样本可进入 v1.1.0 对比。

---

## 4. 激活 v1.1.0 所需的代码改动（本次未实施）

> 当前只提交 Prompt 设计；以下改动等待人工审核通过后再做。

1. **Schema**（`app/schemas/agents/rag_judge.py`）
   - claim 增加 `claim_type: Literal["factual_claim","non_factual","contradictory"] = "factual_claim"`；
   - 增加 `contradiction_with: str | None = None`；
   - 默认值保证 v1.0.0 输出仍可解析。
2. **Scoring**（`app/services/rag_judge_service.py`）
   - 分母只统计 `factual_claim` + `contradictory`；
   - `details` 增加 `non_factual_count`、`contradiction_count`；
   - v1.0.0 无 `claim_type` → 默认 factual_claim，行为不变。
3. **版本加载器**（`app/agents/rag_judge_agent.py`）
   - 增加 `RAG_JUDGE_PROMPT_VERSION` 配置（默认 `v1.0.0`）；
   - 优先读 `rag_judge/<version>/<metric>.txt`，缺失时回退根目录；
   - **默认仍为 v1.0.0**，切换需显式配置。
4. **测试**
   - v1.0.0 回归：现有 24 条 Judge 测试不变；
   - v1.1.0：结论句、non_factual 排除、contradictory 诊断、模糊题 0.8、矛盾 ≤0.3、无答案 1.0；
   - 版本切换测试：默认 v1.0.0、显式 v1.1.0 读取正确 SHA。

不改 Phase 3C 数据库/API；不新增 Agent；不覆盖历史结果。

---

## 5. 审核后执行顺序

1. 人工完成 10 条 Pilot 基础字段 + 35 条 Claim 审核；
2. 人工完成剩余 30 条基础字段审核（Claim 在生成答案后补）；
3. 审核通过后激活 v1.1.0（默认仍保留 v1.0.0 回退）；
4. 用**相同 10 条**跑 v1.1.0，对比 v1.0.0；
5. 重点检查 Q23、Q35、Q36、Q29、Q11、Q21；
6. 检查是否引入新偏差（过度宽松、把建议当事实、拒答滥用）；
7. 通过后才跑完整 40 条；
8. 仍不宣布 Judge 质量验收通过，直到人工 Gold 与 40 条对比完成。

---

## 6. 本次交付清单

- v1.0.0 归档 + MANIFEST（SHA/基线/Pilot 结果路径）
- v1.1.0 三个 Prompt + MANIFEST（pending_review，active=false）
- `prompt-v1.1.0.diff`（逐行修改）
- `annotation-spec.md`（人工标注规范）
- 10/30 条审核 CSV + 35 条 Claim 审核 CSV
- `human-gold.template.json`（人工 Gold 独立模板）
- `pending-review.md`（40 条待审清单）

**状态：暂停，等待人工审核。**
