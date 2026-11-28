# 产品 P0 scope：QA 数据集管理页 + 端到端演示

> 状态：`draft_scope`（2026-11-27 初始范围，保留作决策记录）
> 决策背景：产品优先，生产多租户 migration `deferred_by_product_priority`
> 环境：P0-B 本轮验收使用 `aiinsight_demo`（preprod 证据冻结）；生产未碰、未迁移、未激活
> 验收：一个未参与开发的人类，不碰命令行，完成「空状态 CTA → 建数据集 → 跑评测 → 看对比 → 导出/报告」

> **2026-11-27 状态更新**
>
> | 阶段 | 状态 |
> |---|---|
> | P0-A | accepted |
> | P0-B | **`blocked / ready_for_human_retest`**：F1/F2/F3 + F7 + stale localStorage + HF 离线/预热已修复，AI 自检通过；仍待人类复测后才能 accepted |
> | P0-C | 未开始，等 P0-B 人类测试通过 |
> | 生产 migration | deferred / blocked |
> | M1 | v1.2.5 beta / inactive |
>
> P0-B 验收要求与证据模板见 `docs/releases/p0b-e2e-demo-runbook.md`；AI 功能证据见 `docs/releases/p0b-e2e-test-record.md`，不作为验收通过。

## 1. 现状事实

| 项 | 现状 |
|---|---|
| QA 数据集后端 | API 完整：创建/列表/详情/更新、版本、导入、发布、条目读写、统计 |
| 前端数据集 | **没有 `/qa-datasets` 路由/页面**；只在「新建 RAG 评测」弹窗里只读选择数据集 |
| 前端 API client | 只有 `listDatasets/listVersions/items` 只读；无 create/import/publish |
| 空状态 | 新建评测弹窗提示「先通过 /qa-datasets API 导入数据」，用户无法自助 |
| 现有页面 | Dashboard、数据源、数据清洗、质量评估、知识库、RAG 评测/详情/对比、报告 |
| 失败 Run | retry/cancel API 已有；前端未接按钮（P1） |
| 演示数据 | `seed_demo.py` / `seed_rag_eval*.py` 需要 CLI |

## 2. P0 范围

### P0-A：QA 数据集管理页

| 功能 | 说明 |
|---|---|
| 路由/导航 | 新增 `/qa-datasets`，Sidebar 增加“QA 数据集”，Breadcrumb 映射 |
| 列表 | 分页、名称搜索、来源类型、创建时间、条目/版本概览 |
| 创建 | 名称、描述、来源类型（doc/conv/mixed）；创建后进入详情 |
| 详情/版本 | 版本列表、状态（draft/published/archived）、item_count、发布时间 |
| 新建版本 | 空版本或从已有版本 copy-on-write；note |
| 导入条目 | JSON 粘贴/文件；逐条校验错误（1-based 行号）；整批失败不写入；提供模板 |
| 发布 | 二次确认；说明“发布后不可变”；发布后刷新版本/统计 |
| 条目管理 | draft 版本内查看、编辑、删除；published 只读 |
| 统计 | 条目数、split、分类、证据覆盖率 |
| 错误/空状态 | 无数据集、无版本、导入失败、发布冲突均给出可操作提示 |

实现约束：

- 复用现有 `/api/v1/qa-datasets` 路由，不新增后端 migration；
- 只补前端 API client + hooks + 页面 + 组件测试；
- 导入格式 P0 先支持 JSON（`QaDatasetImportRequest.items`）；CSV 映射放 P1；
- 权限沿用现有 RBAC（tenant_admin/user 可写；viewer 只读）。

### P0-B：端到端演示流程

目标：用户只用 UI，从空环境完成一次完整流程：

```
数据源 → 上传 → 清洗 → 质量评估 → 知识库
  → QA 数据集（创建/导入/发布）
  → RAG 评测（新建 Run）
  → 详情 / 两 Run 对比
  → 报告 / 导出
```

| 项 | 内容 |
|---|---|
| 页面串联 | 空状态 CTA：无数据集 → 去数据集页；数据集发布后 → 新建评测；Run 完成 → 对比/报告 |
| 演示脚本 | 一份 UI 操作 runbook；preprod 预置演示数据（脚本/管理员一键，不需要终端用户 CLI） |
| 演示数据 | 测试租户/测试数据；不导入真实客户数据 |
| 验收 | 新用户按 runbook 在 preprod 完成全流程，≤30 分钟，无需命令行 |
| 失败提示 | 明确 invalid/skipped/失败原因，不用“模型能力”解释产品缺陷 |

### P0-C：Beta / Known issues 产品化

| 项 | 内容 |
|---|---|
| Beta 提示 | 复用 `RagBetaNotice`，统一文案：Judge beta、invalid/噪声、人工复核 |
| 演示话术 | 明确“哪些分数可解释、哪些需要人工复核”，不承诺 target 通过率 |
| 文档 | 演示 runbook + 已知限制；与 preprod 环境绑定 |

## 3. P1（P0 验收后）

- 失败 Run 清理/重试按钮（retry/cancel API 已有）；
- Dashboard / 质量 / 洞察页面 polish；
- 一键 seed（管理员）与演示数据重置；
- CSV 导入映射、数据集归档/删除策略（需后端评审）；
- 手工 FAQ 首次 embedding 同步加载超过前端 30s（演示改用异步提取）；
- 默认限流下的轮询/429 体验；
- gold_evidence 编辑；
- ~~质量任务完成后结果列表不自动刷新~~（2026-11-27 已修复）；
- ~~知识提取完成后 FAQ 列表不自动刷新~~（2026-11-27 已修复）。

## 4. 非目标

- 生产多租户 migration / 023–025 生产化；
- PR-4 代码（后台 context / audit outbox）；
- M1 Judge 校准 / target / baseline / 模型对比 / 10/40；
- RLS / retention / alerting / cost；
- MinIO/S3 生产验证、nginx/TLS；
- 真实客户数据导入。

## 5. 交付拆分

| 阶段 | 内容 | 验收 |
|---|---|---|
| P0-A | 数据集页 + client/hooks + 组件/单测 | 创建/导入/发布/条目/统计可用；错误可读 |
| P0-B | 页面 CTA 串联 + preprod 演示 runbook + 演示数据 | 新用户无 CLI 完成全流程 |
| P0-C | Beta/known issues 文案 + 演示话术 | 演示中不误导、不承诺 |
| P1 | 失败 Run 重试/清理、页面 polish、seed | 另开 review |

## 6. 验收标准

1. preprod 上创建 QA 数据集、创建版本、导入 ≥5 条、发布成功；
2. 发布后版本不可变；draft 可编辑/删除；
3. 从数据集页直接发起 RAG 评测，Run 完成；
4. 两个 Run 可对比，Case 详情/失败原因可查看；
5. 报告可生成/导出；
6. 全流程无需命令行、无需手工 SQL/seed；
7. 演示话术明确 Judge beta 与 invalid/噪声；
8. 不触碰生产、不新增 tenant 生产功能。

## 7. 待确认

1. 导入 P0 是否只做 JSON，CSV 放 P1；
2. 数据集是否允许删除/归档（后端目前无删除路由）；
3. 演示数据归属：固定测试租户还是按登录用户创建；
4. P0 是否包含“从对话/知识库生成 QA 集”的自动草稿（建议不做，先手工/JSON）。
