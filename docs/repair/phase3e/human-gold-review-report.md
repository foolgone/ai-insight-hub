# Phase 3E 人工 Gold 复核准备报告

**日期**：2026-11-16
**性质**：仅整理复核材料；**未产生 Human Gold**，未修改 Prompt/Agent/Schema/API/DB，未运行 Judge。
**工作台**：`docs/repair/phase3e/human-gold-review-workbench.md`

---

## 1. 文件检查

### 1.1 实际读取

| 文件 | 用途 |
|---|---|
| `docs/repair/phase3e/subagent-review.md` / `.json` | 5 组 subagent 复核结果 |
| `docs/repair/09-phase3e-prompt-v1.1-design.md` | Prompt v1.1.0 设计与复核结论 |
| `docs/repair/phase3e/annotation-spec.md` | 人工标注规范 |
| `docs/repair/phase3e/candidates.json` | 40 条候选（`auto_generated`） |
| `docs/repair/phase3e/human-review-pilot.csv` | 10 条 Pilot 审核表 |
| `docs/repair/phase3e/human-review-remaining.csv` | 30 条剩余审核表 |
| `docs/repair/phase3e/pilot-claims-review.csv` | 35 条 Claim 审核表 |
| `docs/repair/phase3e/human-gold.template.json` | Human Gold 模板（human 字段全空） |
| `docs/repair/phase3e/pending-review.md` | 40 条待审清单 |
| `docs/repair/phase3e/pilot-labels.ai-draft.json` | 10 条 Pilot AI Claim 草稿 |
| `docs/repair/phase3e/pilot-judge-results.json` | v1.0.0 Judge 结果（只读参考） |
| `C:\Users\The Fool\AppData\Local\Temp\opencode\phase3e_runs.json` | 40 条真实 WeKnora 生成答案/上下文 |
| `C:\Users\The Fool\AppData\Local\Temp\opencode\phase3e_doc.md` | 原始文档（已复制入仓库） |

### 1.2 40 条候选位置

- 唯一候选文件：`docs/repair/phase3e/candidates.json`（meta：`auto_generated` / `pending_human`）。
- 未发现另一份 40 条候选副本；未创建重复候选文件。

### 1.3 原始文档可访问性

- 本地 WeKnora KB：`4ae8e147-6f76-4330-93f1-d2b3fef3d9ba`，文档 `phase3d_doc.md`。
- 仓库只读副本：`docs/repair/phase3e/source/phase3d_doc.md`。
- SHA-256：`737f6bd3ef412d41d14ada4d2000bd01e851355f0d95cd0d321ac84416f9002d`。
- 来源说明：`docs/repair/phase3e/source/SOURCE.md`。
- 注意：若仓库副本与 WeKnora 索引内容不一致，以知识库实际内容为准并记录差异；本次复核以仓库副本为逐字引用依据。

---

## 2. 人工复核材料

### 2.1 8 条基础数据

| ID | 材料齐全 | 主要内容 |
|---|---|---|
| Q23 | ✅ | 问题、当前答案、Evidence、§12 原文、时间边界风险、人工字段 |
| Q36 | ✅ | 问题、当前答案、Evidence、§1/§12 原文、文档口径冲突、人工字段 |
| Q14 | ✅ | 问题、当前答案、Evidence、§4 原文、answerability 选项 |
| Q15 | ✅ | 问题、当前答案、Evidence、§5 原文、category 选项 |
| Q16 | ✅ | 问题、当前答案、Evidence、§6 原文、category 选项 |
| Q19 | ✅ | 问题、当前答案、Evidence、§9 原文、answerability 选项 |
| Q37 | ✅ | 问题、当前答案、Evidence、§4 原文、文档外流程标记 |
| Q40 | ✅ | 问题、当前答案、Evidence、§10 原文、与 Q20 重复对比 |

### 2.2 1 条 Claim

| ID | 材料齐全 | 主要内容 |
|---|---|---|
| Q21#3 | ✅ | 原 Claim、AI 标签、§1/§3/§8 原文、证据不足说明、人工标签字段 |

### 2.3 其余 31 条抽查候选

已提供 5 条候选（待用户确认后才作为人工抽查记录）：

| ID | 类型 | 推荐理由 |
|---|---|---|
| Q05 | direct | 简单事实题，验证 Evidence 逐字对应 |
| Q13 | multi | 两个事实点，验证多段综合 |
| Q22 | constraint | 金额 + 地区双条件 |
| Q30 | unanswerable | 验证“不编造” |
| Q35 | ambiguous | Subagent 已发现“收货地区”误判 |

备选：Q09、Q18、Q38。

### 2.4 无法找到原始证据的项目

- **Q37**：当前答案中的“在订单中申请电子发票并填写抬头”在原文 §4 无依据；已隔离，不进入 Gold。
- 其余 8 条均有原文；Q36 是“文档自身口径冲突”，不是缺证据。

---

## 3. 风险清单

| # | 问题 | 证据来源 | AI 审核意见 | 需要用户决定 |
|---|---|---|---|---|
| R1 | Q36 虚拟商品口径冲突 | §1“已激活的虚拟商品” vs §12“虚拟商品一经售出” | 不能强行生成唯一 Gold，保留 ambiguous + 条件分支 | 采用哪条口径，或要求业务澄清 |
| R2 | Q23“第 2 天”时间边界 | §12“24 小时内” | 跨午夜时可能未满 24 小时；答案在通常理解下成立 | 改题干为“超过 24 小时”，或保留并标 ambiguous |
| R3 | Q14 是否已开具 | §4“开具前可改；已开具先红冲” | 参考答案有两分支，但问句缺状态 | 标 ambiguous，或改题干为“已开具” |
| R4 | Q19 是否过期 | §9“有效期内退回；已过期不退” | 参考答案有两分支，但问句缺状态 | 标 ambiguous，或改题干为“已过期” |
| R5 | Q15 分类 | §5 单事实“电话预约” | 答案正确；`multi` 不匹配 | 改 `direct`（影响覆盖）或换 multi-hop 题 |
| R6 | Q16 分类 | §6 单条件“超过 24 小时联系客服” | 答案正确；`multi` 不匹配 | 改 `constraint`/`direct` 或换题 |
| R7 | Q37 文档外流程 | §4 无“申请入口/填写抬头” | 删除文档外内容，保留 §4 事实 + 分支 | 确认修正答案；是否标 ambiguous |
| R8 | Q40 与 Q20 重复 | §10 同一知识点 | 建议删除或改写 | 删除/改写/保留并记录 |
| R9 | Q21#3 推断 | §1 只限定无理由退款；§3 换货仍 7 天；§8 保修 | 证据不足，不能确认“质量问题不受 7 天限制” | supported / insufficient_evidence / needs_recheck |
| R10 | 分类调整影响覆盖 | 当前 10/10/8/6/6 | 改 Q15/Q16 会改变分布 | 是否保持覆盖比例，或替换题目 |
| R11 | 原始文档副本一致性 | 仓库副本 SHA 737f6bd3… | 与本地 WeKnora 索引对应；本次未逐 chunk 比对 | 是否需要额外核对 KB chunk |
| R12 | AI 审核不是 Human Gold | `reviewer_type=ai_subagent` | 只能作为意见，不能直接转 `human_reviewed` | 最终人工签核 |

---

## 4. 用户操作说明

### 4.1 打开哪些文件

1. 先读：`docs/repair/phase3e/human-gold-review-workbench.md`（9 个对象的完整上下文）。
2. 填表：
   - `docs/repair/phase3e/human-gold-review-base.csv`（8 行基础数据）
   - `docs/repair/phase3e/human-gold-review-claim.csv`（1 行 Q21#3）
3. 对照原文：`docs/repair/phase3e/source/phase3d_doc.md`。
4. 如需看全量候选：`docs/repair/phase3e/candidates.json`。

### 4.2 每条需要填写的字段

基础表：

- `human_decision`：`accept_current` / `use_subagent_correction` / `rewrite` / `needs_recheck` / `reject`
- `human_corrected_answer`
- `human_corrected_evidence`
- `human_reason`
- `human_reviewer`
- `review_status`：`human_reviewed` / `needs_recheck`

Claim 表：

- `human_decision`：`accept_current` / `change_label` / `needs_recheck`
- `human_label`：`supported` / `unsupported` / `insufficient_evidence` / `needs_recheck`
- `human_evidence_reference`
- `human_reason`
- `human_reviewer`
- `review_status`

### 4.3 可以直接确认的

- **Q15、Q16**：答案本身有 §5/§6 原文支持；只需决定分类。
- **Q14、Q19**：答案有两分支且原文支持；只需决定 `answerability`。
- **Q37**：删除文档外流程后的修正答案可对照 §4 确认。
- **Q23**：若接受“第 2 天=超过 24 小时”的通常理解，答案可确认；否则改题干/标 ambiguous。

### 4.4 需要先查文档或业务规则的

- **Q36**：虚拟商品 canonical 口径（§1 vs §12）。
- **Q23**：24 小时起算点（签收时间/自然日）。
- **Q40**：是否删除/改写，及覆盖比例。
- **Q21#3**：是“supported（字面范围）”还是“insufficient_evidence（承诺证据不足）”。
- **Q15/Q16**：是否允许改变 10/10/8/6/6 分类覆盖。

### 4.5 抽查候选

先确认是否采用 Q05、Q13、Q22、Q30、Q35；确认后再补 `review_target=spot_check` 行，不要现在写入人工记录。

---

## 5. 修改范围核查

| 项 | 是否修改 |
|---|---|
| Prompt v1.0.0 | ❌ 未修改 |
| Prompt v1.1.0 | ❌ 未修改 |
| Prompt v1.1.1 / 加载器 | ❌ 未创建、未修改 |
| Agent / Schema / Service / API | ❌ 未修改 |
| 数据库 / Migration | ❌ 未修改 |
| Judge 执行 | ❌ 未执行 |
| 10 条对照 / 40 条评测 | ❌ 未执行 |
| Human Gold | ❌ 未产生；`human-gold.template.json` 未改 |
| AI 审核 | ✅ 仅作为 `ai_subagent` 意见；未转 Human Gold |
| 新增文件 | 原始文档副本、复核工作台 MD/CSV/JSON、本报告 |

---

## 6. 结论

- 8 条基础数据 + 1 条 Claim 的复核材料**齐全**，均有原文摘录、位置、AI 意见和空白人工字段。
- 5 条抽查候选已给出，待用户确认。
- 所有 `human_*` 字段为空，`review_status=pending_human`；**未产生 Human Gold**。
- Q36 文档冲突、Q23 时间边界、Q37 文档外内容、Q40 重复、Q21#3 推断是必须由用户决定的事项。

**完成后停止，等待用户确认；不进入下一阶段。**

---

## 7. 复核结论回填（2026-11-16）

人工判断已完成并写入两张复核表，逐条说明见 `human-gold-decisions.md`。

| 对象 | 决定 | 最终标签 |
|---|---|---|
| Q23 | rewrite（题干改“超过 24 小时”） | constraint / answerable |
| Q36 | use_subagent_correction | ambiguous |
| Q14 | accept_current | multi / ambiguous |
| Q15 | accept_current | direct |
| Q16 | accept_current | constraint |
| Q19 | accept_current | multi / ambiguous |
| Q37 | use_subagent_correction | ambiguous |
| Q40 | rewrite（题干改“转让或提现”） | direct / answerable |
| Q21#3 | accept_current | insufficient_evidence |
| Q05/Q13/Q22/Q30 | accept_current | 原标签不变 |
| Q35 | use_subagent_correction | ambiguous |

- 复核表：`human-gold-review-base.csv` 13 行（8 基础 + 5 抽查）、`human-gold-review-claim.csv` 1 行；所有 `human_*` 已填，`review_status=human_reviewed`。
- 分类覆盖：direct 10→12、multi 10→8、constraint 8→9、unanswerable 6→6、ambiguous 6→5。
- 复核人署名：江晚（结论由 AI 起草，用户确认署名）；如需更严格的逐条签核，可补充签核时间。
- 仍未生成 `human-gold.json`，`human-gold.template.json` 未改；未运行 Judge、10 条对照或 40 条评测，Phase 3E 仍未进入 Phase 4。
