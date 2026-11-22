# Phase 3E 项目控制台（README）

> 用途：Phase 3E / RAG Judge 项目的**单一决策与进度入口**。
> 使用规则：
> 1. 每次需要做决策前，先读本文件；
> 2. 每完成一个工作流，更新本文件的状态、证据和“下一步”；
> 3. Agent 只能报告 `implemented` / `verified`，不能自行标 `accepted`；
> 4. 未冻结的定义/目标，不得进入代码实现。
>
> 最后更新：2026-11-22
> 当前阶段：**M1-D-2 v1.2.1 evidence-continuity Prompt 已 metadata-only 冻结；未激活、未跑 Judge**
> 当前阻塞决策：**是否重新提交 v1.2.1 的 10 条 Judge 申请**
> 当前不做：跑 Judge、跑 40、v1.2.0/v1.2.1 激活、M2/M3、生产 migration

---

## 0. 一分钟状态

| 项 | 状态 |
|---|---|
| 项目阶段 | 核心研发向产品化过渡 |
| 主线 | M1 评测可信度；v1.2.1 frozen，等待新 10 条申请 |
| 并行 A | M2 只读工作台；API 审计完成，前端未开始 |
| 并行 B | M4-A 生产约束；未开始 |
| M3 优化闭环 | 未开始；等 M1 可信、M2 可用 |
| 当前可写代码？ | **否**；先决定是否重新申请 10 条 |
| 当前可跑 Judge？ | **否**；10 条未批准 |
| v1.2.0 / v1.2.1 | v1.2.0 `frozen`；v1.2.1 `frozen`、`active=false` |
| 最近一次决策 | 2026-11-22 v1.2.1 metadata-only freeze 通过 |
| 下一个交付 | 重新提交 10 条 Judge 申请（使用 v1.2.1 SHA） |

### 现在只需要一个决定

**v1.2.1 已冻结；是否重新提交 10 条 Judge 申请。**

| 选项 | 含义 | 结果 |
|---|---|---|
| **提交新 10 条申请** | 使用 v1.2.1 SHA、Q11 修复证据、target v1.0.2 | 仍需人工批准；不得跑 40 |
| **暂缓** | 不申请 | 保持 frozen / active=false |
| **退回** | 冻结元数据需改 | 回到冻结审核 |

---

## 1. 项目目标与边界

**核心闭环**：导入知识库问答数据 → 建立可信评测集 → 执行 RAG 评测 → 定位质量问题 → 调整 RAG 配置 → 对比优化效果 → 输出评测报告。

**边界**：

- WeKnora 是被测知识库系统，不重新开发；
- 本平台负责数据集、执行、指标、诊断、实验和报告；
- 清洗/知识提取是数据准备能力，不在 M1 扩成独立数据治理平台；
- 洞察/报告基于评测结果，不先做泛化 BI；
- 第一版核心价值：**能可靠回答“这套 RAG 为什么答错，改完之后有没有变好”**。

---

## 2. 里程碑控制台

| 里程碑 | 状态 | 已完成证据 | 当前阻塞/下一步 |
|---|---|---|---|
| **M0 评测基础设施** | `accepted`（冻结维护） | Dataset/Version/Item、RAG Adapter、Trace、检索指标、Judge、Run/Celery、持久化聚合、WeKnora 联调 | 只修缺陷/兼容，不再架构重构 |
| **M1 评测可信度** | `in_progress` | M1-A 语义/Gold/target 已冻结；M1-B B 双指标草案（`19-…`）；M1-C C1–C4 已实现/验证；M1-D-0 Prompt `frozen`；M1-D-1 blocked at Q11；M1-D-2 v1.2.1 `frozen` | v1.2.0/v1.2.1 未激活；10/40 Judge 未通过；M1-E 未开始 |
| **M2 评测工作台** | `audit_complete` / 实现 `not_started` | API 审计完成：Run/详情/结果/失败/Trace 可用；前端 0 页面 | 等 M1-B 冻结后再决定是否写 P0 前端 |
| **M3 RAG 优化闭环** | `not_started` | 无 | 依赖 M1 可信 + M2 可用 |
| **M4 生产交付** | 基础已有 / 约束 `not_started` | 认证、加密、限流、Prometheus/Grafana/Sentry、备份/恢复演练 | M4-A：租户、保留期、审计、告警、成本、数据权利 |

### 2.1 M1 工作包

| 工作包 | 状态 | 交付/证据 |
|---|---|---|
| M1-A 语义规范 + Gold + 目标 | `accepted` | 语义规范冻结 2026-11-18；final_labels SHA `f139623f…`；target v1.0.2 SHA `3ee15dfc…`（`freeze_draft_pending_human`，旧 v1.0.1 只读） |
| M1-B Schema/Service 定稿 | `implemented`，**未 `accepted`** | P1-1 关闭；P1-2 证据契约已定；B 双指标冻结草案 `19-…` 待审核 |
| M1-C 实现与测试 | `implemented` / `verified`，**未 `accepted`** | C1 Schema v3、C2 migration 022、C3 Service 双指标/invalid/聚合/retry、C4 静态回归已完成；10/40 Judge 未运行 |
| M1-D 有限实验 | `in_progress`（M1-D-0 / M1-D-1 / M1-D-2） | M1-D-0 Prompt `frozen`；M1-D-1 blocked at Q11；M1-D-2 v1.2.1 `frozen`、未激活；等待新 10 条申请 |
| M1-E 质量验收 | `not_started` | 四组报告（HG/provisional/40 条/系统质量）+ 已知问题决定 + SHA 追溯 |

### 2.2 门禁视角

| 门禁 | 状态 | 说明 |
|---|---|---|
| G1 数据 | 部分 | 数据集/版本/校验和已有；保留期/隔离未定 |
| G2 评测 | 未过 | B 指标定义待冻结；v1.2.0 Prompt 已 `frozen`，但未激活、未跑 Judge |
| G3 稳定性 | 基础 | Run/重试/取消/恢复已有；未做 v1.2.0 压测 |
| G4 产品 | 断点 | M2 前端为 0 |
| G5 安全 | 部分 | 认证/RBAC/加密有；租户隔离无 |
| G6 运营 | 部分 | 监控/备份有；告警规则、保留期无 |
| G7 用户验收 | 未开始 | 无真实用户试用 |

---

## 3. 已冻结 / 历史决策

### 3.1 冻结资产

| 资产 | SHA / 版本 | 状态 | 用途 |
|---|---|---|---|
| `docs/repair/12-judge-semantic-spec.md` | 冻结内容 = `92ce3ab` 版本（`d64cb13` 的 P1-2 就地修改已撤销） | `frozen` | v1.2.0 语义基线；旧 freeze record `b50830b` 未改写 |
| `docs/repair/phase3e/pilot-40-final-labels.json` | `f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb` | `frozen` | 40 条分类唯一来源 |
| `docs/repair/phase3e/pilot-40-targets-v1.2.0.json` | `34357b34c3d0fc85e78f90eeebb353b25a148926e3a55b19f17cc23b08b2b5eb`（revision v1.0.1） | `frozen` / 只读 | 历史目标；未被覆盖 |
| `docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.2.json` | `3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846`（revision v1.0.2） | `freeze_draft_pending_human` | metadata-only 目标 revision；数值不变；validation 20/20 |
| `docs/repair/phase3e/m1b003-static-recalc.json` | `53787fbb2a434953354bd821b62581e6e56ba5db10751149c236f1e7656437bb` | `static_recalculation_not_judge_run` | 静态重算；validation 13/13 |
| `docs/repair/phase3e/pilot-40-targets.json` | `8ae37ac4…` | `read_only` | 旧目标；不得用于新 Run |
| `docs/repair/16-m1b-decision-record.md` | M1-B-002 | 历史（A 单 F） | P1-1/P1-2 证据契约；单 F 公式已被 B 取代 |
| `docs/repair/18-m1b-dual-metric-design-evaluation.md` | M1-B-003 设计评估 | `superseded_by_freeze_draft` | B 双指标定义、目标映射、D1–D4；冻结文本见 19 |
| `docs/repair/19-m1b-003-freeze-draft.md` | `d2d2e0decd84fee57b68acf90e862189c09acf6ce608d92578f6346f7cc5183d`（r2） | `freeze_draft_pending_human` | D1–D4 约束、生命周期、Run 不可变、Item 聚合、invalid 持久化、标签/术语、验收测试 |
| `docs/repair/19-m1b-003-freeze-draft.validation.json` | 33/33 | `static_validation` | r1 4 项 + 术语统一 + r2 2 项 |
| `docs/repair/20-m1b-003-revision-record.md` | M1-B-003-r1 | 历史记录 | r1 4 项逐项关闭证明 |
| `docs/repair/21-m1b-003-r2-revision-record.md` | M1-B-003-r2 | `revision_record` | r2 2 项收尾证明、剩余未决 |
| `backend/app/prompts/rag_judge/v1.2.0/` | F `b6377758…` / C `a50520de…` / R `a5386070…`；MANIFEST `ee1c25be…` | `frozen` / `active=false` | v1.2.0 Prompt、MANIFEST、version.txt；默认仍 v1.0.0 |
| `docs/repair/phase3e/m1d-prompt-v1.2.0-validation.json` | `21326f2c…` | `static_validation` 22/22 | v1.2.0 资产 SHA/字段/默认隔离/旧 Prompt 完整性 |
| `docs/repair/27-m1d0-prompt-freeze-record.md` | freeze record | `frozen` | 记录 `071c3b6`、旧/新 MANIFEST SHA、Prompt SHA、validation、批准人与 activation requirements |
| `docs/repair/28-m1d1-ten-case-judge-application.md` | application JSON `7378d368…`；validation `bb2e1602…` | `approved`（r3；执行 stopped） | Production Service replay、预注册规则、可复算预算 |
| `docs/repair/phase3e/m1d1-ten-case-application.json` | `7378d368adf13b7d55e58904af200310fa20f47cf51ccc67967f13e7e437e2ad` | `static_application` | 机器可读 r3 申请；validation 50/50 pass |
| `docs/repair/29-m1d1-judge-only-results.md` | raw `821bd7cc…`；summary `47f0979e…` | `stopped` / `blocked` | Q11 F invalid 后停止；3 attempted / 7 unprocessed |
| `docs/repair/phase3e/m1d1-judge-only-results.json` | `821bd7ccbb5f842c34596f9f3b74f774b8e6318341a1d659f86c7ac473fe6472` | `raw_results` | 3 个 case 的原始 JudgeOutcome、token/cost、停止原因 |
| `docs/repair/30-m1d2-v1.2.1-prompt-patch-scope.md` | design/scope | `design_record` | Q11 evidence 连续性规则、Q11 回归 fixture、版本/冻结计划；已按此实现 |
| `backend/app/prompts/rag_judge/v1.2.1/` | F `9efdc64d…` / C `a50520de…` / R `a5386070…`；MANIFEST `8bdd673c…` | `frozen` / `active=false` | 只改 F 连续性；C/R SHA 不变；rubric_version=v1.2.0 |
| `docs/repair/phase3e/m1d2-prompt-v1.2.1-validation.json` | `33890eed…` | `static_validation` 22/22 | v1.2.1 资产 SHA、C/R 继承、连续性规则、版本映射 |
| `docs/repair/31-m1d2-v1.2.1-implementation.md` | implementation report | `frozen` / `verified` | Q11 bad/good tests、SHAs、冻结结果与 activation requirements |
| `docs/repair/32-m1d2-v1.2.1-freeze-record.md` | freeze record | `frozen` | 旧/新 MANIFEST、validation、Prompt SHA、批准人与 activation requirements |

### 3.2 决策时间线

| 日期 | 决策 | 状态 |
|---|---|---|
| 2026-11-18 | v1.2.0 语义规范冻结 | `frozen` |
| 2026-11-18 | 40 条 final_labels 冻结（只分类，不冻目标） | `frozen` |
| 2026-11-18 | v1.2.0 active target 冻结；Q32 以 3 个 factual 点为前提 | `frozen` |
| 2026-11-18 | P1-1：Service 单测 / Judge 验收分离 | `accepted` |
| 2026-11-18 | P1-2：证据契约严格化（A：单 F） | `superseded`（2026-11-19 改 B） |
| 2026-11-19 | 选 B：F_strict + F_coverage | `accepted`（方向） |
| 2026-11-19 | D1–D4 原则同意；D1/D2 附约束 | `approved_with_constraints` |
| 2026-11-19 | M1-B-003 冻结草案 + 目标 v1.0.2 + 静态重算 | `freeze_draft_pending_human` |
| 2026-11-19 | `approve_with_changes`；r1 修订 4 项 + 术语统一 | `freeze_draft_pending_human` |
| 2026-11-19 | r2 契约收尾：Item 计数 + invalid 持久化 | `freeze_draft_pending_human` |
| 2026-11-19 | M2 API 审计完成 | `audit_complete` |
| 2026-11-20 | M1-D-0 批准执行；v1.2.0 Prompt `design_draft` 交付 | `design_draft` / 待审核 |
| 2026-11-20 | 人工批准 metadata-only freeze | `frozen` / `active=false`；未激活 |
| 2026-11-21 | M1-D-1 10 条申请 r2 退回；补充 r3 | `pending_approval`；Production Service replay；未运行 |
| 2026-11-21 | M1-D-1 r3 执行 3 个 case 后停在 Q11 F invalid | `stopped` / `blocked`；未 verified |
| 2026-11-21 | Q11 invalid 复核通过；准备 v1.2.1 patch 设计与范围 | `design_scope_pending_review`；未改 Prompt |
| 2026-11-22 | v1.2.1 evidence-continuity patch 实现/验证 | `design_draft` / `implemented/verified`；待冻结 |
| 2026-11-22 | v1.2.1 metadata-only freeze | `frozen` / `active=false`；未激活 |

---

## 4. 当前 B 方案（冻结草案）

### 4.1 指标定义

| metric key | 展示名称 | 公式 | 角色 |
|---|---|---|---|
| `faithfulness` | **Faithfulness（证据覆盖）** | `S / (S + U + I)` | 主指标；现有 `F` 目标全部映射到它 |
| `faithfulness_strict` | **Strict Faithfulness（可判定事实）** | `S / (S + U)` | 诊断；v1.2.0 不设硬目标 |

其中：

- `S` = factual + supported
- `U` = factual + unsupported
- `I` = factual + insufficient_evidence
- `N` = non_factual（不进分母）

### 4.2 状态边界

| 情况 | F_strict | F_coverage |
|---|---|---|
| 有 S/U | `S/(S+U)` | `S/(S+U+I)` |
| 全部 U，无 S/I | 0.0 | 0.0 |
| 全部 I，无 S/U | `skipped(no_decidable_claims)` | `evaluated 0.0` + `all_insufficient=true` |
| 全部 non_factual / 空 claims | `skipped(no_scorable_claims)` | `skipped(no_scorable_claims)` |
| 无上下文 | `skipped(context_unavailable)` | `skipped(context_unavailable)` |
| 证据/结构违约 | `invalid(contract_violation)` | `invalid(contract_violation)` |
| Judge 执行失败 | `failed(execution)` | `failed(execution)` |

**全 insufficient 的 0 分必须带说明**：`all_insufficient=true`、`report_label=evidence_undecidable`；报告写“证据不可判定”，不写“幻觉/编造”。

### 4.3 目标兼容证据

用 v1.1.5 的 32 条结果静态重算（不是新 Judge 运行）：

- `F_coverage` 在 30/30 有分数案例上与旧 F 一致（6 位小数）；Q14/Q29 均为 skip；
- `F_strict` 在 29/30 有分数案例上为 1.0；仅 Q23=0.75；
- Q11/Q17/Q21/Q23/Q32 的 frozen target 在 B 下均可复现（Q17/Q32 按 v1.2.0 预期标签）；
- A 方案下 Q21/Q23 的“目标不可达/越界”冲突，在 B 下消失。

### 4.4 D1–D4 状态（已审核，附约束）

| 编号 | 问题 | 结论 | 状态 |
|---|---|---|---|
| **D1** | 指标 key | `faithfulness` = F_coverage；`faithfulness_strict` = F_strict；必须显示分母说明；历史版本靠 `metric_version` + `prompt_sha256` 区分 | `approved_with_constraints` |
| **D2** | 持久化 | 两条 result row；strict 派生、不额外调 Judge；记录 `derived_from_result_id`；同 Run/Item/Version；重试版本一致；Case 数不翻倍 | `approved_with_constraints` |
| **D3** | 全 insufficient | coverage `evaluated 0.0` + `all_insufficient=true`；strict `skipped(no_decidable_claims)`；有 unsupported 时不得标 `evidence_undecidable` | `approved` |
| **D4** | F_strict 目标 | v1.2.0 只观察 `F_strict`、`unsupported_count/ratio`、`insufficient_ratio`、`strict_gap`；不设硬目标 | `approved` |

### 4.5 冻结草案与验证

| 项 | 状态 |
|---|---|
| `19-m1b-003-freeze-draft.md`（r2） | `freeze_draft_pending_human`；SHA `d2d2e0de…`；33/33 validation |
| `20-m1b-003-revision-record.md` | r1 历史记录；4 项关闭证明 + 术语统一 |
| `21-m1b-003-r2-revision-record.md` | r2 修订记录；2 项收尾证明 |
| 目标 revision `v1.0.2` | `freeze_draft_pending_human`；20/20 validation；数值不变 |
| 静态重算 | `static_recalculation_not_judge_run`；13/13 validation；输出 SHA `53787fbb…` |
| M1-B 整体 | 仍为 `implemented`，**未 `accepted`** |

---

## 5. 下一步开发计划

> 顺序原则：**先冻结指标定义与验收目标 → 再实现 Schema/Service → 最后跑 Judge**。不允许代码反过来决定标准。

### 5.1 当前流程（P0）

**已完成（r2）**：

| 任务 | 产物 | 证据 |
|---|---|---|
| r2 修订 2 项 | `19-m1b-003-freeze-draft.md` | 33/33 validation；SHA `d2d2e0de…` |
| r2 修订记录 | `21-m1b-003-r2-revision-record.md` | Item 计数 + invalid 持久化逐项证明 |
| Item 计数语义 | 冻结草案 §4.4.3、§4.4.4 | `completed_items=evaluated_items`；四类 + unprocessed 守恒；3 items/6 rows/3 cases |
| invalid 持久化 | 冻结草案 §4.7 | 独立 invalid / `failed+invalid_reason` 共同语义；不进均值；不算执行失败 |

**M1-D-1 执行结果（stopped / blocked）**：

| 项 | 结果 |
|---|---|
| attempted | Q01/Q04/Q11 |
| PASS | Q01/Q04 |
| invalid | Q11 F `quote_not_found`（`contract_violation`） |
| unprocessed | Q17/Q21/Q23/Q29/Q31/Q35/Q36 |
| calls | 9 / 51 |
| tokens | 28,460 input / 2,245 output |
| cost | CNY 0.089856 / 1.00 |
| stop condition | 已触发；未重跑、未跑 40 |

**M1-D-0 已 metadata-only `frozen`；M1-D-1 r3 执行停在 Q11 invalid，未 verified。v1.2.0 未激活、默认仍 v1.0.0。M1-B r2 仍待人工最终审核；M1-C C1–C4 已实现/验证但未 `accepted`。10/40 Judge 均未通过。**

### 5.2 M1-C（已实现/验证，未 accepted）

> C3 阶段验收通过。C4 静态目标回归/40 条盘点/报告模板已完成并本地验证，**待审核**；10/40 Judge 未运行。
>
> 实施顺序：C1 Schema v3 → C2 migration 022 + model/repo 字段 → C3 Service 双指标/invalid/聚合/retry → C4 目标回归。

| 任务 | 内容 | 验收 |
|---|---|---|
| Schema v3 | `claim_subtype` 枚举、`support_status` 必填、v1/v2 兼容 | Schema 单测 |
| Service 双指标 | `faithfulness` + `faithfulness_strict`、S/U/I 计数、全 insufficient 语义 | 12 条核心测试 + 附加契约测试 |
| 错误契约 | 缺 subtype / supported 无 evidence / quote 非逐字 → invalid | 负向测试 |
| 聚合/重试 | 两 metric 都进 `expected_metrics`；缺 strict 也算缺失；Case 数不按 row 翻倍 | 聚合/重试测试 |
| 双行生命周期 | `derived_from_result_id`、同 Run/Item/Version、删除级联、失败传播 | 生命周期测试 |
| Run 不可变/retry | `retry_run` 复制父快照；默认 Prompt/Schema 漂移仍复制父快照；显式换配置或父快照不可用才拒绝 retry、新建 Run | 配置一致性测试 |
| Item 聚合 | `completed_items=evaluated_items`；新增 `invalid_items`；completion/success 分开 | 聚合测试 |
| 术语契约 | API/前端显示“证据覆盖 / 可判定事实 / 评测覆盖率 / 证据不足比例” | 前端/API 契约测试 |
| 持久化 | 采用 A：独立 `invalid` 状态 + `invalid_reason`；不得并入 failed | migration/契约测试 |
| 标签体系 | `contains_unsupported_claims`、`contains_insufficient_claims`、`evidence_undecidable` 等主标签 | 标签/展示测试 |
| Judge acceptance | 标签正确性，不是 Service 单测 | 7 条负向语义测试 |

### 5.3 M1-D / M1-E（实现后）

**M1-D-0（2026-11-20，已完成 `design_draft` 并 metadata-only `frozen`）**：

1. 修订 v1.2.0 Prompt 设计；
2. 创建 3 个 Prompt + MANIFEST + version.txt；
3. 补 loader / Schema v3 / 默认隔离 / v1-v2 回归测试；
4. 输出 SHA、validation 与冻结提案；
5. **不跑 Judge、不激活 v1.2.0**；冻结已完成，等 10 条 Judge 单独批准。
6. M1-D-1 r3 Production Service replay 已执行 3 个 case，Q11 F invalid 后停止；结果见 `29-m1d1-judge-only-results.md`。
7. M1-D-2 v1.2.1 evidence-continuity patch 已 metadata-only `frozen`（`32-m1d2-v1.2.1-freeze-record.md`）；未激活。

**后续（未批准）**：

1. 重新提交 10 条 Judge 申请，使用 v1.2.1 SHA；不得复用 v1.2.0 批准；
2. 10 条通过后申请 40 条；
3. 40 条分层报告（HG 13 / provisional 27 分开）；
4. 6 条缺失 baseline 按方案 A 标 `baseline_delta: unavailable`，不跑 Judge 补齐；
5. 四组报告 + 已知问题接受/修复/延期 + SHA 追溯；
6. M1-E 验收。

### 5.4 并行线

| 线 | 状态 | 启动条件 | 第一交付 |
|---|---|---|---|
| M2 最小只读工作台 | 审计完成 | 用户明确批准写前端 | Run 列表 + 详情 + Case + Evidence；只读 |
| M4-A 生产约束 | 未开始 | 可与 M1 并行 | 用户/租户、保留期、审计、成本、告警、数据权利决策 |
| M3 优化闭环 | 未开始 | M1 可信 + M2 可用 | 首个受控优化实验 |

### 5.5 工作量估算（人日，非承诺日期）

| 工作包 | 估算 |
|---|---|
| M1-B 冻结（含目标 revision） | 0.5–1 |
| M1-C 实现与测试 | 5–8 |
| M1-D 实验 | 2–4（不含模型等待） |
| M1-E 验收 | 1–2 |
| M2 P0 前端 | 6–9 |
| M2 compare 接口（P1） | +2–3 |
| M4-A 约束文档 | 2–3 |

---

## 6. 流程规则

### 6.1 状态词汇

`not_started → in_progress → implemented → verified → accepted`

| 状态 | 含义 |
|---|---|
| `not_started` | 未开始 |
| `in_progress` | 正在做，未形成可验收产物 |
| `implemented` | 代码/文档已完成 |
| `verified` | 有自动化测试或实验结果 |
| `accepted` | 人工审核通过，符合退出标准 |

附加状态：`blocked`、`proposed_pending_human`、`frozen`、`superseded`、`read_only`、`audit_complete`。

### 6.2 硬规则

1. 未冻结的指标定义/目标，不写 Schema/Service；
2. Agent 不得自行把任务标 `accepted`；
3. 不把“40 条都出了分数”当成 M1 完成；
4. 不把 `/summary` 当 pairwise compare；
5. 不把 `user_id` 隔离称为租户隔离；
6. 不静默改 frozen 文件；变更必须新文件 + 新 SHA + validation；
7. 每次完成工作流，先更新本 README，再开下一个；
8. 每次决策前，先读本 README 的 §0、§4、§5。

### 6.3 角色边界

| 角色 | 做 | 不做 |
|---|---|---|
| 人工（项目 owner） | 冻结/验收、范围、优先级、资源、对外交付决定 | — |
| Agent | 只读审计、设计草案、实现、测试、更新 README 事实与计划 | 不自行 `accepted`、不自行扩范围、不擅自运行 Judge、不擅自激活 v1.2.0 |

---

## 7. 风险与开放问题

| 风险/问题 | 影响 | 当前处理 |
|---|---|---|
| M1-B-003 未 accepted | M1-C 不能启动 | 等人工审核 r1 |
| `invalid` 持久化未定 | DB/API/M2 口径不一致 | M1-C 决定：新增枚举或 `failed+invalid_reason` |
| 当前 `retry_run` 用当前指纹 | 与 Run 不可变契约冲突 | M1-C 改为复制父快照；变化则新建 Run |
| 当前 `completed_items` 含 skipped | 完成率可能虚高 | M1-C 改为 evaluated_items；新增 invalid_items |
| F_strict 区分度低 | 容易变成“永远通过” | v1.2.0 只观察 |
| 全 insufficient 0 被误读 | 被当成幻觉 | `all_insufficient` + `evidence_undecidable` 文案 |
| Q17/Q32 预期值被当实测 | 目标判断失真 | 静态重算已分 `observed` / `expected_v1.2.0`，禁止混写 |
| 双行导致 Case 数翻倍 | 完成率/覆盖率错误 | 生命周期契约按 item 聚合，不按 row |
| M2 前端未开始 | 用户无法使用评测结果 | 等批准后排 P0 |
| M4 租户/保留期未定 | 不能对外交付 | M4-A 先定约束 |
| 6 条 baseline 缺失 | 40 条报告不完整 | M1-D 先补 |

---

## 8. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-11-18 | M1-A 语义/Gold/target 冻结；P1-1/P1-2 记录 |
| 2026-11-19 | 选 B；新增 `18-m1b-dual-metric-design-evaluation.md`；A 转为历史 |
| 2026-11-19 | M2 API 审计完成（`17-…`） |
| 2026-11-19 | D1–D4 原则同意（D1/D2 附约束） |
| 2026-11-19 | 新增 `19-m1b-003-freeze-draft.md`；目标 revision v1.0.2；静态重算 13/13 |
| 2026-11-19 | `approve_with_changes`；r1 修订 4 项 + 术语统一；`19` SHA `1abfc221…`；21/21 validation |
| 2026-11-19 | r2 契约收尾：Item 计数 + invalid 持久化；`19` SHA `d2d2e0de…`；33/33 validation |
| 2026-11-19 | 创建本 README，作为项目控制台 |
