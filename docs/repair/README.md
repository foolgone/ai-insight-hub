# Phase 3E 项目控制台（README）

> 用途：Phase 3E / RAG Judge 项目的**单一决策与进度入口**。
> 使用规则：
> 1. 每次需要做决策前，先读本文件；
> 2. 每完成一个工作流，更新本文件的状态、证据和“下一步”；
> 3. Agent 只能报告 `implemented` / `verified`，不能自行标 `accepted`；
> 4. 未冻结的定义/目标，不得进入代码实现。
>
> 最后更新：2026-11-24
> 当前阶段：**M2 P0 已 verified：VM PG/Redis + 宿主机 API/worker/前端，mock 适配器 5 条真实 Run 通过页面验收**
> 当前决策：**等待 accepted；之后 M3 两 Run 对比、M4-A 约束并行**
> 当前不做：target 校准、5-case 模型对比、10/40 Judge、v1.2.6、M1-E 验收

---

## 0. 一分钟状态

| 项 | 状态 |
|---|---|
| 项目阶段 | 平台交付优先；M1 降级为 beta 能力 |
| 主线 | M2 P0：RAG 评测工作台（Run 列表 / Run 详情 / Case 详情 / 报告入口） |
| M1 | v1.2.4 / v1.2.5 保持 `frozen` / `inactive`；标为 **beta / known issues**；不再跑 Judge |
| M1 校准 | **已停止**：target v1.0.3、5-case 对比、10/40、v1.2.6、M1-E 全部冻结 |
| 平台验收 | 用户能完成一次完整评测，看到可解释结果和报告；不以 target 通过率为门槛 |
| Judge 展示 | invalid / skipped / known issues 原样展示；人工复核可覆盖 |
| 当前可写代码？ | **是**：M2 P0 及平台主流程 |
| 当前可跑 Judge？ | **否**（仅 beta 展示；不新增校准调用） |
| 下一个交付 | M2 P0 accepted 确认 → M3 两 Run 对比 |
| 之后 | M3 两 Run 对比；M4-A 租户/保留期/审计/告警/成本/数据权利 |

### M2 P0 已交付

| 页面 | 路由 | 内容 |
|---|---|---|
| Run 列表 | `/rag-evaluations` | 状态、时间、数据集、F/C/R、invalid 数、新建评测 |
| Run 详情 | `/rag-evaluations/:runId` | 指标汇总、样本进度、known issues、Case 列表、失败列表、报告入口 |
| Case 详情 | `/rag-evaluations/:runId/cases/:itemId` | question/answer/contexts、claims/evidence、invalid 原因、raw output |

实现方式：复用现有 `/api/v1/rag/evaluations`、`/rag/traces`、`/qa-datasets`；后端仅给 Run 列表补了 `aggregate` 只读字段，未改架构。

**真实 Run（2026-11-24）**：`67596d50-5782-456e-a96a-63929b9a9a80`，completed，5/5 evaluated，F 0.700 / C 0.120 / R 0.540，invalid 0，failed 0；截图见 `docs/04-development/assets/m2-p0/`。M2 P0 状态：**accepted**（范围仅页面与真实 Run 流程，不含 Judge 质量/M1；qwen-flash 仅为运行时配置，F/C/R 不作 M1 证据）。

### M3 P0 已交付

| 项 | 内容 |
|---|---|
| 入口 | `/rag-evaluations/compare?base=<runId>&target=<runId>`；Run 列表/详情均有入口 |
| 指标 | F/C/R base/target/delta；invalid/failed/skipped/unprocessed 分列 |
| Case diff | `变好/变差/不变/invalid/未处理`，按 F/C/R 绝对变化最大的指标判定 |
| 验收 Run | base `67596d50…` vs target `56573a73…`；R Δ -0.040；变好 1 / 变差 2 / 不变 2 |
| 截图 | `docs/04-development/assets/m3-p0/compare.jpeg` |

### M1 当前口径（beta）

| 项 | 状态 |
|---|---|
| v1.2.5 | `frozen` / `inactive`；**beta** |
| 已知限制 | `factual_claim + absence`、`patch_null`、Q17/Q21 target 未校准 |
| target v1.0.2 | 保持 active，仅作参考；v1.0.3 draft 不激活 |
| 正式 10/40 | 不跑；不作为上线门槛 |
| M1-D-6 | `blocked`，不再推进 |

### 现在只需要一个决定

**M2 P0 已上线到代码；下一步是在真实环境跑通一次完整流程。**

| 选项 | 含义 | 结果 |
|---|---|---|
| **真实环境跑通（推荐）** | 启动栈 → 数据源 → 清洗 → 质量 → RAG 评测 → 报告 | 平台验收唯一标准 |
| **先补 M3 对比** | 两个 Run 前后对比 | P0 之后再排 |
| **M4-A 约束** | 租户/保留期/审计/告警/成本/数据权利 | 与真实客户前必须 |
| **恢复 Judge 校准** | 本轮明确停止 | 不再作为门禁 |

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
| **M1 评测可信度** | `in_progress` | M1-A 语义/Gold/target 已冻结；M1-B B 双指标草案（`19-…`）；M1-C C1–C4 已实现/验证；M1-D-0 Prompt `frozen`；M1-D-1 blocked at Q11；M1-D-2 v1.2.1 `frozen`；M1-D-3 blocked at Q23；M1-D-4 v1.2.2 `frozen`、Q23 invalid -> blocked；M1-D-5 v1.2.3 `frozen`、单案例 Q23 invalid -> diagnostic blocked；M1-D-6 v1.2.4 `frozen`、Q23 `patch_schema_invalid` -> blocked；Q23 根因复核完成，已选 B+C，待 v1.2.5 claim 分解 design | v1.2.x 未激活；10/40 正式验收未批准；M1-E 未开始 |
| **M2 评测工作台** | `audit_complete` / 实现 `not_started` | API 审计完成：Run/详情/结果/失败/Trace 可用；前端 0 页面 | 建议等 M1 有 10 条诊断报告 + 用户批准后再写 P0 前端 |
| **M3 RAG 优化闭环** | `not_started` | 无 | 依赖 M1 可信 + M2 可用 |
| **M4 生产交付** | 基础已有 / 约束 `not_started` | 认证、加密、限流、Prometheus/Grafana/Sentry、备份/恢复演练 | M4-A：租户、保留期、审计、告警、成本、数据权利 |

### 2.1 M1 工作包

| 工作包 | 状态 | 交付/证据 |
|---|---|---|
| M1-A 语义规范 + Gold + 目标 | `accepted` | 语义规范冻结 2026-11-18；final_labels SHA `f139623f…`；target v1.0.2 SHA `3ee15dfc…`（`freeze_draft_pending_human`，旧 v1.0.1 只读） |
| M1-B Schema/Service 定稿 | `implemented`，**未 `accepted`** | P1-1 关闭；P1-2 证据契约已定；B 双指标冻结草案 `19-…` 待审核 |
| M1-C 实现与测试 | `implemented` / `verified`，**未 `accepted`** | C1 Schema v3、C2 migration 022、C3 Service 双指标/invalid/聚合/retry、C4 静态回归已完成；10/40 Judge 未运行 |
| M1-D 有限实验 | `in_progress`（M1-D-0 … M1-D-6） | M1-D-0 Prompt `frozen`；M1-D-1 blocked at Q11；M1-D-2 v1.2.1 `frozen`；M1-D-3 blocked at Q23；M1-D-4 v1.2.2 `frozen`、Q23 invalid -> blocked；M1-D-5 v1.2.3 `frozen`、单案例 Q23 invalid -> diagnostic blocked；M1-D-6 v1.2.4 `frozen`、待单案例 |
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
| `docs/repair/33-m1d3-ten-case-judge-application.md` | application JSON `7077477e…`；validation `1f2fdb3a…` | `approved`；执行 stopped | v1.2.1 新 10 条申请、Q11 证据、预算/重复/Q36/停止条件 |
| `docs/repair/phase3e/m1d3-ten-case-application.json` | `7077477ef6108dcf7996b5ce17b2c492752cbbc85644856d91abdb3b5f45da28` | `static_application` | 机器可读 M1-D-3 申请；validation 31/31 pass |
| `docs/repair/34-m1d3-judge-only-results.md` | raw `96ff0d9b…`；summary `5e4d38c3…` | `stopped` / `blocked` | 6 attempted / 4 unprocessed；Q23 F invalid 后停止 |
| `docs/repair/phase3e/m1d3-judge-only-results.json` | `96ff0d9b03add2365f5a74219402deb59a3015f7c6adc1f174cb039cdb34c526` | `raw_results` | 6 个 case 的原始 JudgeOutcome、token/cost、停止原因 |
| `docs/repair/35-m1d4-v1.2.2-prompt-patch-scope.md` | design/scope r2 | `design_record` | Q23 absence / Q21 evidence directness、repair 版本隔离、Q21 单案例验收 |
| `backend/app/prompts/rag_judge/v1.2.2/` | F `ed21979a…` / C `a50520de…` / R `a5386070…`；MANIFEST `81dd3a32…` | `frozen` / `active=false` | 只改 F absence/直接支持；C/R SHA 不变；rubric v1.2.0 |
| `docs/repair/phase3e/m1d4-prompt-v1.2.2-validation.json` | `fadef856…` | `static_validation` 23/23 | v1.2.2 资产 SHA、C/R 继承、规则、repair 版本标记 |
| `docs/repair/36-m1d4-v1.2.2-implementation.md` | implementation report | `frozen` / `verified` | rules、repair 版本隔离、Q23/Q21 测试、冻结提案 |
| `docs/repair/37-m1d4-v1.2.2-freeze-record.md` | freeze record | `frozen` | 旧/新 MANIFEST、validation、Prompt SHA、agent_commit、repair SHA、批准人与 activation requirements |
| `docs/repair/38-m1d4-v1.2.2-single-case-diagnostic-application.md` | application SHA `a38e6477…`；validation `829dc4c4…` | 申请快照 `pending_approval`；已批准执行 | Q23/Q21/Q11 各 1 次、预算 14 calls / CNY 0.30、停止条件与验收断言 |
| `docs/repair/phase3e/m1d4-single-case-diagnostic-application.json` | `a38e6477558ee8c6e0e2c4450170406edcfe31f012f78dd604a36a642db9bf19` | `static_application` | 机器可读单案例申请；validation 43/43 pass |
| `docs/repair/phase3e/m1d4-single-case-application.validation.json` | `829dc4c4…` | `static_validation` 43/43 | 版本、SHA、frozen、默认、fixture/target、预算、停止条件、边界 |
| `docs/repair/39-m1d4-v1.2.2-single-case-diagnostic-results.md` | report SHA `764a614b…` | `stopped` / `blocked` | Q23 F invalid（3× quote_not_found）；cl5 混合句未拆分；Q21/Q11 未运行 |
| `docs/repair/phase3e/m1d4-single-case-results.json` | `c2cae388…` | `raw_results` | Q23 原始 claims、quote 校验、3 calls / CNY 0.03726；无 repair |
| `docs/repair/phase3e/m1d4_run_single_case.py` | runner | `executed` | 运行时指纹、显式 v1.2.2、预算/停止、repair 记录 |
| `docs/repair/40-m1d5-v1.2.3-contract-repair-design.md` | design/scope r2 | `approved_with_changes`；实现见 `41-…` | Agent quote 预校验 + 定向 repair、共享校验、证据来源规则、混合句 A、预算/门禁 |
| `backend/app/prompts/rag_judge/v1.2.3/` | F `52f1b3cf…` / C `a5f9e5b2…` / R `f3efe431…`；MANIFEST `7856b74e…` | `frozen` / `active=false` | Agent quote 预校验、去案例化 few-shot、v1.2.3 repair example；C/R SHA 因去案例化变化 |
| `docs/repair/phase3e/m1d5-prompt-v1.2.3-validation.json` | `8e790aac…` | `static_validation` 26/26 | v1.2.3 资产 SHA、quote validator、泄漏审计、旧版本隔离 |
| `docs/repair/phase3e/m1d5-prompt-leakage-audit.json` | `d21cc41b…` | `leakage_audit` findings=0 | 10 个 gate case 的 answer/gold/claim/evidence ≥12 字符审计 |
| `docs/repair/41-m1d5-v1.2.3-implementation.md` | implementation report | `frozen` / `verified` | 共享 validator、Agent 预校验、agent_contract、golden regression、测试 |
| `docs/repair/42-m1d5-v1.2.3-freeze-record.md` | freeze record | `frozen` | 旧/新 MANIFEST、validation、F/C/R SHA、C/R 去案例化说明、泄漏审计、批准人与 activation requirements |
| `docs/repair/43-m1d5-v1.2.3-single-case-diagnostic-application.md` | application SHA `fb6b98e7…` | `approved`；已执行 | Q23/Q21/Q11 各 1 次、14 calls / CNY 0.30、9 条停止条件 |
| `docs/repair/44-m1d5-v1.2.3-single-case-diagnostic-results.md` | report SHA `8c73f5bd…` | `stopped` / `blocked` | Q23 repair 后 Schema 失败；F invalid；C target miss；Q21/Q11 未运行 |
| `docs/repair/phase3e/m1d5-single-case-results.json` | `2394bac8…` | `raw_results` | 4 calls（3 primary + 1 repair）/ CNY 0.051797；Q23 首次与 repair 输出 |
| `docs/repair/45-m1d6-v1.2.4-evidence-patch-design.md` | design/scope r2 | `approved_with_changes`；实现见 `46-…` | evidence-only patch、final_errors、C 首句规则、ledger、预算/门禁 |
| `backend/app/prompts/rag_judge/v1.2.4/` | F `52f1b3cf…`（不变）/ C `ca489fcf…` / R `f3efe431…`（不变）；MANIFEST `33cad3a8…` | `frozen` / `active=false` | evidence-only patch、C 首句规则、patch schema/example |
| `docs/repair/phase3e/m1d6-prompt-v1.2.4-validation.json` | `9ecdb424…` | `static_validation` 23/23 | patch schema/example、C 规则、泄漏审计、旧版本隔离 |
| `docs/repair/phase3e/m1d6-prompt-leakage-audit.json` | `7a5fa618…` | `leakage_audit` findings=0 | 10 gate case answer/gold/claim/evidence 审计 |
| `docs/repair/46-m1d6-v1.2.4-implementation.md` | implementation report | `frozen` / `implemented` | patch flow、effective ID、conflict、final_errors、C warning |
| `docs/repair/47-m1d6-v1.2.4-freeze-record.md` | freeze record | `frozen` | 旧/新 MANIFEST、validation、patch schema/example、乱码修复、C 规则、ledger/activation requirements |
| `docs/repair/phase3e/m1d6-single-case-diagnostic-application.json` | application SHA `54193e91…` | `approved` / executed | Q23/Q21/Q11 单案例；14 calls / CNY 0.30；ledger 前置 |
| `docs/repair/phase3e/m1d6-single-case-ledger.jsonl` | ledger SHA `c07b8401…` | append-only / 4 attempts / 0 uncertain | primary 3 + patch 1；cost CNY 0.0422808 |
| `docs/repair/phase3e/m1d6-single-case-results.json` | raw results SHA `dec1d964…` | `stopped` | Q23 F invalid；Q21/Q11 未运行 |
| `docs/repair/phase3e/m1d6-single-case-analysis.json` | analysis SHA `24bea3ec…` | report-only | Q23 initial/patch、absence、patch 失败、停止条件 |
| `docs/repair/49-m1d6-v1.2.4-single-case-diagnostic-results.md` | report SHA `d7762d6a…` | `stopped at Q23` | Q23 patch_schema_invalid；M1-D-6 blocked |
| `docs/repair/50-m1d6-q23-root-cause-and-target-review.md` | read-only review | `pending_decision` | Q23 0.333 复现；S1 合并 derived=0.400；A/B/C 待选 |
| `docs/repair/51-m1d6-v1.2.5-claim-decomposition-scope.md` | design/scope | `approved_with_changes`；实现见 53 | claim 分解 + 内部矛盾 + patch 健壮性 |
| `docs/repair/52-m1d6-v1.2.5-c3-median-runner-design.md` | runner design | `approved_with_changes`；未执行 | Q23 F×3 + median/min/max；18 calls / CNY 0.40 |
| `docs/repair/53-m1d6-v1.2.5-implementation.md` | implementation report | `frozen` / implemented/verified | F claim 分解 + patch v125 + tests |
| `docs/repair/54-m1d6-v1.2.5-freeze-record.md` | freeze record | `frozen` | 旧/新 MANIFEST、validation、F/C/R、patch v125、C 单案例预授权 |
| `docs/repair/55-m1d6-v1.2.5-c-single-case-application.md` | C application | `approved` / preauthorized | Q23 F×3 + C/R×1 + Q21/Q11；18 calls / CNY 0.40；ledger |
| `docs/repair/56-m1d6-v1.2.5-c-single-case-results.md` | C results | `collected` / diagnostic failed | Q23 F 0/3 valid；Q21/Q11 F invalid；15 calls / CNY 0.1838 |
| `docs/repair/57-m1d6-v1.2.5-failure-mode-application.md` | failure-mode application | `approved` | 10 条 × 1 次；43 calls / CNY 0.80；无 repeats |
| `docs/repair/58-m1d6-v1.2.5-failure-mode-diagnostic-results.md` | failure-mode results | `collected` / D2 mixed | F 6 evaluated / 3 invalid / 1 skipped；Q23/Q35/Q36 invalid；32 calls / CNY 0.3747 |
| `docs/repair/59-m1d6-v1.2.5-model-comparison-flash-application.md` | flash comparison application | `approved` | qwen3.8-flash + no thinking；5 cases；13 calls / CNY 0.60 |
| `docs/repair/60-m1d6-v1.2.5-model-comparison-flash-results.md` | flash comparison results | `collected` / D3 | 5/5 evaluated、0 invalid；Q23/Q35/Q36 target hit；6 calls / CNY 0.1577（上界） |
| `docs/repair/61-m1d6-q17-q21-target-review.md` | M1-A target review r2 | `read_only_review` | Q21 cl3=insufficient；Q17/Q21 均建议 `[0.5,0.7]`；v1.0.2 未改 |
| `docs/repair/62-m1d6-target-v1.0.3-draft.md` | target v1.0.3 draft | `draft_pending_m1a_review` | Q17/Q21 F `[0.5,0.7]`；21/21 validation；不激活 |
| `docs/repair/63-m1d6-model-comparison-5case-application.md` | 5-case comparison application | `pending_approval` | qwen-max + qwen3.8-flash；23 calls / CNY 0.60 |
| `docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.3-draft.json` | draft SHA `50aeda48…` | `draft` / inactive | v1.0.2 active；仅 Q17/Q21 F 变更 |
| `docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.3-draft-validation.json` | validation SHA `d500f4cb…` | 21/21 pass | 40 cases；仅两条变更；v1.0.2 SHA 未变 |
| `docs/repair/phase3e/m1d6-q17-q21-target-review.json` | review SHA `800de34f…` | r2 | cl3=insufficient；建议均 `[0.5,0.7]` |
| `docs/repair/phase3e/m1d6-q17-q21-target-review.json` | review SHA `a7819032…` | 0 Judge calls | claim 明细 + 语义判定 + 建议区间 |
| `docs/repair/phase3e/m1d6-v125-model-comparison-flash-preflight.json` | preflight SHA `0e5925e8…` | `preflight_passed` | /models 200；thinking on/off 对比；6.8k 输入 631 输出 |
| `docs/repair/phase3e/m1d6-v125-model-comparison-flash-application.json` | application SHA `6f69e8f4…` | `approved` | 5 primary + 5 patch + 3 retry |
| `docs/repair/phase3e/m1d6-v125-model-comparison-flash-ledger.jsonl` | ledger SHA `6f9c4204…` | 6 attempts / 0 uncertain | primary 5 + patch 1；CNY 0.1577（上界） |
| `docs/repair/phase3e/m1d6-v125-failure-mode-ledger.jsonl` | ledger SHA `454e1672…` | 32 attempts / 0 uncertain | primary 31 + patch 1；cost CNY 0.3746904 |
| `docs/repair/phase3e/m1d6-v125-failure-mode-dry-run.json` | dry-run SHA `330bff00…` | ok / 0 LLM calls | 43/43 budget self-test；ledger empty |
| `docs/repair/phase3e/m1d6_run_failure_mode_v125.py` | failure-mode runner | implemented | 10 条 × 1 次；dry-run/report-only |
| `docs/repair/phase3e/m1d6-v125-ledger.jsonl` | ledger SHA `69c2a5a4…` | 15 attempts / 0 uncertain | primary 11 + patch 4；cost CNY 0.183756 |
| `docs/repair/phase3e/m1d6-v125-dry-run.json` | dry-run SHA `83f612f6…` | ok / 0 LLM calls | 18/18 budget self-test；ledger empty |
| `docs/repair/phase3e/m1d6_run_single_case_v125.py` | C runner | implemented | Q23 F×3 + C/R + Q21/Q11；dry-run/report-only |
| `backend/app/prompts/rag_judge/v1.2.5/` | F `9c80d4d5…`；C/R `ca489fcf…` / `f3efe431…`；MANIFEST `2e4ef8bf…` | `frozen` / `active=false` | claim 分解 + 内部矛盾；C/R 不变 |
| `docs/repair/phase3e/m1d7-prompt-v1.2.5-validation.json` | `20ab5ca3…` | `static_validation` 28/28 | patch schema/example、F 规则、旧版本隔离 |
| `docs/repair/phase3e/m1d7-prompt-leakage-audit.json` | `28937947…` | `leakage_audit` findings=0 | gate cases + m1d3/m1d4/m1d6 输出 |

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
| 2026-11-22 | M1-D-3 v1.2.1 10 条 Judge 申请提交 | `pending_approval`；未运行 |
| 2026-11-22 | M1-D-3 执行 6 个 case 后停在 Q23 F invalid | `stopped` / `blocked`；未 verified |
| 2026-11-22 | Q23 invalid 确认；准备 v1.2.2 patch 设计与范围 | `design_scope_pending_review`；未改 Prompt |
| 2026-11-22 | v1.2.2 absence/直接支持 patch 实现/验证 | `design_draft` / `implemented/verified`；待冻结 |
| 2026-11-22 | v1.2.2 metadata-only freeze | `frozen` / `active=false`；未激活；单案例未批准 |
| 2026-11-22 | 提交 v1.2.2 Q23/Q21/Q11 单案例诊断申请 | `pending_approval`；未运行 |
| 2026-11-22 | 执行 v1.2.2 单案例：Q23 F invalid 后停止 | `stopped` / `blocked`；3 calls / CNY 0.03726；Q21/Q11 未运行 |
| 2026-11-22 | 提交 v1.2.3 合同修复设计（Agent quote 预校验 + 定向 repair） | `design_draft_pending_review`；未实现 |
| 2026-11-22 | v1.2.3 设计 approve_with_changes；实现/验证完成 | `design_draft` / `implemented/verified`；待 freeze |
| 2026-11-22 | v1.2.3 freeze 退回：Prompt 仍含 gate case；去案例化 + 泄漏审计 113→0 | 重新待 freeze；未运行 Judge |
| 2026-11-22 | v1.2.3 metadata-only freeze | `frozen` / `active=false`；未激活；单案例未批准 |
| 2026-11-23 | v1.2.3 Q23/Q21/Q11 单案例执行：Q23 repair 后仍 invalid | `stopped` / `blocked`；4 calls / CNY 0.051797；Q21/Q11 未运行 |
| 2026-11-23 | 提交 v1.2.4 Evidence-only Patch Repair 设计 | `design_draft_pending_review`；未实现 |
| 2026-11-23 | v1.2.4 设计 approve_with_changes；P1-1~P1-4 修订并实现/验证 | `design_draft` / `implemented/verified`；待 freeze |
| 2026-11-23 | v1.2.4 乱码修复复审通过；metadata-only freeze | `frozen` / `active=false`；未激活；单案例未批准 |
| 2026-11-23 | v1.2.4 Q23/Q21/Q11 单案例执行：Q23 patch_schema_invalid | `stopped` / `blocked`；4 calls / CNY 0.0422808；Q21/Q11 未运行 |
| 2026-11-23 | Q23 根因复核：patch null 次要；S0=0.333，S1 合并 derived=0.400 | `pending_decision`；待 A target v1.0.3 / B claim 分解 / C 3 次 median |
| 2026-11-23 | 提交 v1.2.5 claim 分解 scope + C runner 设计 | `design_pending_review`；未实现、未跑 Judge |
| 2026-11-23 | v1.2.5 实现/验证：claim 分解 + patch v125 + tests | `design_draft` / implemented/verified；待 freeze；未跑 Judge |
| 2026-11-23 | v1.2.5 metadata-only freeze | `frozen` / `active=false`；默认 v1.0.0；未激活 |
| 2026-11-23 | 提交 C 单案例申请（Q23 F×3 + C/R×1 + Q21/Q11） | `approved` / preauthorized；18 calls / CNY 0.40；未执行 |
| 2026-11-23 | C 单案例执行：Q23 F 0/3 valid；Q21/Q11 F invalid | `collected` / diagnostic failed；15 calls / CNY 0.183756；未写 PASS |
| 2026-11-24 | failure-mode diagnostic（10 条 × 1 次） | `collected`；F 6/3/1；invalid Q23/Q35/Q36；D2 mixed；32 calls / CNY 0.3747 |
| 2026-11-24 | 回滚 OpenCode/deepseek 产物到 `0b4a226` | 严格回到 qwen 欠费前；工作树 clean |
| 2026-11-24 | DashScope 充值后 flash 对比（qwen3.8-flash，no thinking） | `collected`；5/5 evaluated、0 invalid；Q23/Q35/Q36 target hit；Q17/Q21 miss；6 calls / CNY 0.1577 |
| 2026-11-24 | Q17/Q21 M1-A target 复核（desk，0 Judge） | `read_only_review`；Q17→`[0.4,0.7]`、Q21→`[0.7,0.9]`；v1.0.2 未改 |
| 2026-11-24 | target 复核 r2：Q21 cl3 判 insufficient | Q17/Q21 均改建议 `[0.5,0.7]`；重算 flash 0.5 / qwen-max 0.6 |
| 2026-11-24 | 生成 target v1.0.3 draft（不激活） | `draft_pending_m1a_review`；validation 21/21；v1.0.2 仍 active |
| 2026-11-24 | 提交 5-case 模型对比申请（qwen-max + flash） | `pending_approval`；23 calls / CNY 0.60；未执行 |

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
>
> **2026-11-23 方向校准**：单案例诊断不单独判死版本；先做 Q23 target/Gold 复核，再用 10 条 `diagnostic_only` 批处理测量分布。规则见 `13-phase3e-acceptance-plan.md` §5.4。

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

**M1-D-3 执行结果（stopped / blocked）**：

| 项 | 结果 |
|---|---|
| attempted | Q01/Q04/Q11/Q17/Q21/Q23 |
| PASS | Q01/Q04/Q11/Q17 |
| target FAIL | Q21 F=1.0，超出 0.6–0.7 |
| invalid | Q23 F `StructuredOutputError` → `contract_violation`；strict 同步 |
| unprocessed | Q29/Q31/Q35/Q36 |
| calls | 18 / 51 |
| tokens | 58,335 input / 5,039 output |
| cost | CNY 0.188378 / 1.00 |
| stop condition | Q23 invalid；未重跑、未跑 40 |

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
8. M1-D-3 v1.2.1 10 条 Judge 已执行 6 个 case，Q23 F invalid 后停止；结果见 `34-m1d3-judge-only-results.md`。
9. M1-D-4 v1.2.2 absence / evidence-directness patch 已实现/验证并 metadata-only `frozen`（`36-…`、`37-m1d4-v1.2.2-freeze-record.md`）；`active=false`、默认仍 v1.0.0。
10. 已提交 Q23/Q21/Q11 单案例诊断申请（`38-…`），状态 `pending_approval`；未运行 Judge。
11. 单案例诊断已执行：Q23 F invalid（3× `quote_not_found`）、cl5 混合句未拆分，按停止条件停止；Q21/Q11 未运行。结果见 `39-…`，3 calls / CNY 0.03726。
12. v1.2.4 单案例已执行：Q23 patch 输出 `evidence_refs=null`，`patch_schema_invalid`；按停止条件停止。结果见 `49-…`，4 calls / CNY 0.0422808；Q21/Q11 未运行。

**后续执行计划见 §5.6。**

### 5.4 并行线

| 线 | 状态 | 启动条件 | 第一交付 |
|---|---|---|---|
| M2 最小只读工作台 | 审计完成 | 用户明确批准写前端；建议等 M1 有 10 条诊断报告后再开工 | Run 列表 + 详情 + Case + Evidence；只读 |
| M4-A 生产约束 | 未开始 | 可与 M1 并行 | 用户/租户、保留期、审计、成本、告警、数据权利决策 |
| M3 优化闭环 | 未开始 | M1 可信 + M2 可用 | 首个受控优化实验 |

### 5.5 工作量估算（人日，非承诺日期）

| 工作包 | 估算 |
|---|---|
| M1-B 冻结（含目标 revision） | 0.5–1 |
| M1-C 实现与测试 | 5–8 |
| M1-D 实验 | 2–4（不含模型等待） |
| Q23 target/Gold 复核 | 0.5–1 |
| v1.2.5 版本包（claim 分解 + patch v125 + tests + freeze） | 2–4 |
| Q23×3 + Q21/Q11 单案例 | 0.5（不含调用费） |
| 10 条诊断批处理 | 0.5（不含调用费） |
| 正式 10 条闸门 | 0.5（不含调用费） |
| 40 条规模/回归 | 1–2（不含调用费） |
| M1-E 验收 | 1–2 |
| M2 P0 前端 | 6–9 |
| M2 compare 接口（P1） | +2–3 |
| M3 首个优化实验 | TBD |
| M4-A 约束文档 | 2–3 |

### 5.6 后续执行计划表（2026-11-23 校准）

#### 5.6.1 主计划

| # | 阶段 | 动作 | 交付 | 批准/门禁 | 预算 |
|---:|---|---|---|---|---|
| 0 | **v1.2.5 版本包** | 按 51/52 + P1 修订；实现 F claim 分解、内部矛盾、patch v125/refusal、tests、freeze | 一份版本包（scope + impl + tests + freeze + validation + leakage 0） | **一次版本包审核**；不再分设计/实现/freeze 三次审 | 2–4 人日；0 Judge |
| 1 | **Q23×3 + Q21/Q11 单案例** | freeze 后预授权；Q23 F×3、C/R×1；Q21/Q11 各 1 次 ×3 指标；ledger | 结果报告：median/min/max、claim 分解、patch/refusal、C/R snapshot | 只审结果；不是 acceptance | 18 calls / CNY 0.40 |
| 2 | **10 条 `diagnostic_only`（推荐）** | 固定 10 条 + Q23/Q35/Q36 repeats；允许记录 invalid 后继续 | 分布报告：invalid rate、target pass、claim_count、C/R、unprocessed | 单独批准；不写 PASS | 51 calls / CNY 1.00 |
| 3 | **正式 10 条闸门** | 10/10 目标通过；无 invalid/failed；HG 按 §5.2 重复 | 官方 10 条报告 | 单独批准 | 51 calls / CNY 1.00 |
| 4 | **40 条规模/回归** | 40 条 + 6 条缺失 baseline；HG/provisional 分开 | 40 条报告 + known issues + SHA | 单独批准 | CNY 1.4–1.8 |
| 5 | **M1-E 验收** | M1-C/M1-D/M1-E 一并验收；四组报告 + 已知问题接受/修复/延期 + SHA 追溯 | M1-E acceptance record | 决策角色 | 1–2 人日 |
| 6 | **M2 P0 只读工作台** | Run 列表/详情/Case/Evidence | 前端 P0；只读 | 10 条诊断/正式 10 报告后 + 单独批准 | 6–9 人日 |
| 7 | **M3 优化闭环** | 首个受控优化实验 | 对比报告 | M1 accepted + M2 可用 | TBD |
| 8 | **M4-A 生产约束** | 租户/保留期/审计/告警/成本/数据权利 | 决策文档 + 迁移计划（不执行） | 可并行；单独批准 | 2–3 人日 |

> 固定 10 条沿用 `pilot-10-v1.1.5-gate.json`：Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36；Q23/Q35/Q36 按 HG 规则重复。40 条沿用 `pilot-40-final-labels.json` + target v1.0.2；6 条缺失 baseline 标 `baseline_delta: unavailable`。

#### 5.6.2 决策点

| 决策点 | 时点 | 选项 | 默认/建议 |
|---|---|---|---|
| **D1** | v1.2.5 单案例后 | 通过 → 10 条；失败 → A target 复核 / 10 条 diagnostic / known limitation；**不出 v1.2.6** | 通过则 10 条；失败先 A/诊断 |
| **D2** | 10 条 diagnostic 后 | 系统性问题 → 修；仅 Q23 → known limitation + 正式 10；target 问题 → M1-A | 仅 Q23 不阻塞 40 |
| **D3** | 正式 10 条后 | 10/10 → 40 条；否则停止/修复 | 不跳过 40 |
| **D4** | 40 条后 | M1-E；否则 known issues/修复 | M1-E 前不启动 M3 |
| **D5** | M1-E 后 | M2/M3/M4 | 按并行线推进 |

#### 5.6.3 预算汇总

| 项 | 估算 |
|---|---|
| v1.2.5 版本包 | 2–4 人日；0 Judge |
| Q23×3 + Q21/Q11 单案例 | 18 calls / CNY 0.40 |
| 10 条 diagnostic | 51 calls / CNY 1.00 |
| 正式 10 条闸门 | 51 calls / CNY 1.00 |
| 40 条规模/回归 | CNY 1.4–1.8 |
| M1 剩余 Judge 成本 | 约 CNY 3.8–4.2（diagnostic + 正式 10 + 40）；跳过 diagnostic 约 2.8–3.2 |
| M2 P0 / M4-A | 6–9 / 2–3 人日 |

> 以上是人日/调用估算，不是日历承诺；10/40 仍需单独批准。

#### 5.6.4 出口标准

- **v1.2.5**：tests 全绿；leakage 0；freeze candidate；v1.2.4 行为不变。
- **单案例**：Q23 median F=`0.400`；cl1 `unsupported` + `is_contradictory`；cl3/cl4 合并为 1 条 derived；Q21/Q11 目标内；ledger 干净。
- **10 条 diagnostic**：分布报告可解释；不写 PASS。
- **正式 10 条**：10/10 目标通过；无 `invalid` / `failed`；HG 按 §5.2。
- **40 条**：40/40 完成；target pass + known issues 分开；不得写“40 条 Human Gold 通过”。
- **M1-E**：四组报告 + 已知问题决定 + SHA 追溯；M1-C/M1-D/M1-E 一并 accepted；M1 只在 M1-E 后 accepted。

#### 5.6.5 停止/时间盒

- v1.2.5 是最后一个 claim 分解版本；单案例失败不自动出 v1.2.6。
- 不得“复跑直到通过”；不得静默改 target；target 变更只走 M1-A。
- 预算/凭证/指纹/ledger 任一异常 → 硬停止。
- 诊断批处理允许记录 invalid 后继续；正式 10/40 不允许。
- Q23 若只是单案例 outlier，写入 known issues，不阻塞 40；若系统性 invalid/quote 问题，先修 Agent/patch。

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
