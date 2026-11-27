# P0-B 端到端演示实测记录

> 状态：`FUNCTIONAL_VERIFIED_BY_AI / PENDING_NON_DEVELOPER_TEST`
> 测试者：**AI agent（owner 指定）**；不是独立人类，且同一 AI 参与过 P0-B 实现。
> 因此本记录**只作为功能证据，不作为 P0-B 验收通过**。
> Runbook：`docs/releases/p0b-e2e-demo-runbook.md`
> 环境：`aiinsight_demo`，**未写 `aiinsight_preprod` / 未碰生产**

## 0. Owner 决策（2026-11-27）

| 项 | 结论 |
|---|---|
| P0-B 实现 | 功能链路通过，`functional_verified` |
| P0-B 验收 | **`pending_non_developer_test`**，不标 accepted |
| 原因 | AI 参与过实现，不是独立非开发者；2 分 03 秒是自动化时间；空状态 CTA 未逐项点击；demo 关闭限流后成功，默认限流未验证；手工 FAQ embedding 超时为 P1 |
| P0-C | **不开始**，等 P0-B 人类测试通过 |

> 本记录后续内容为 AI 功能实测证据；人类验收记录需另起一份或在本文件末尾追加“人类测试”章节。
>
> 2026-11-27：AI 功能证据归档后，`aiinsight_demo` 已重置为空库并保持默认限流，供下一次人类测试。本记录中的 ID 是当时的历史数据，当前 demo 库中已不存在；截图、CSV、报告和 `p0b_ai_test_result.json` 保留在证据目录。

## 1. 测试者

| 项 | 内容 |
|---|---|
| 姓名/标识 | OpenCode AI agent（owner 本机执行，非人类） |
| 角色/团队 | owner-authorized AI executor；未参与人机可用性评审 |
| 是否参与 P0-A/P0-B 开发 | **是**（同一 AI 参与 P0-B 实现，因此不满足“独立非开发者”条件） |
| 日期 | 2026-11-27 |
| 开始 / 结束 | 21:04:35 / 21:06:39（UTC+8） |
| 总耗时 | **2 分 03 秒**（自动化执行时间，不代表人类操作耗时） |
| 浏览器/版本 | Microsoft Edge (Chromium) headless；Playwright 1.64.1；视口 1440×900 |

> 测试方式偏差：所有业务操作由 Playwright 驱动浏览器 UI 完成；异步任务等待和证据 ID 捕获使用**只读 API 轮询**，未使用 CLI/SQL 修改业务数据。环境重置与账号 seed 由开发/运维在测试前完成，不属于测试者操作。

## 2. 环境确认

| 项 | 值 |
|---|---|
| 前端 | `http://127.0.0.1:5173` |
| API | `http://127.0.0.1:8000` |
| DB | `aiinsight_demo`（测试前从空库迁移到 head 025） |
| Redis | DB 6 app / 7 broker / 8 result |
| Storage | `backend/.storage/demo-p0b`，local |
| RAG | `mock` |
| flag | `TENANT_ENFORCEMENT_ENABLED=false` |
| 限流 | 本轮 AI 预跑临时设为 `RATE_LIMIT_ENABLED=false`（见卡点 2）；**人类验收必须保持默认开启** |
| 凭据来源 | 本地安全文件，不记录密码、不进 repo |

隔离确认：

- API/worker 的 `DATABASE_URL` 只指向 `aiinsight_demo`；
- API/worker 日志中未出现 `aiinsight_preprod` / 生产库连接；
- 未访问生产 bucket，未执行生产 migration，未激活 M1；
- demo 库最终计数：`data_sources=1, tasks=6, reports=1, qa_datasets=1, rag_evaluation_runs=2`。

## 3. 步骤与耗时

| # | 步骤 | 结果 | 耗时 | 卡点/重试 |
|---|---|---|---|---|
| 1 | 登录 | 进入 Dashboard | 3s | 无 |
| 2 | 新建数据源 | 创建成功，类型“客服对话” | 2s | 无 |
| 3 | 上传 TXT + 清洗 | 任务 100% completed，5 条清洗结果 | 6s | 无 |
| 4 | 质量评估 | 5 条结果，平均分 71.5 | 22s | 无 |
| 5 | 知识库 | “提取知识（异步）”完成，生成 5 条 FAQ | 37s | 预跑曾用手工 FAQ，首次 embedding 超过前端 30s，见卡点 1 |
| 6 | 新建 QA 数据集 | 创建并自动选中 | ≤1s | 无 |
| 7 | 新建草稿版本 → 导入 JSON → 发布 | 导入 5 条，发布成功，显示“已发布 · 不可变” | ≤1s（与步骤 6 连续完成） | 无 |
| 8 | 发布后「发起评测」 | 弹窗已预选数据集/版本 v1 | 含在步骤 9 | 无 |
| 9 | Run1（top_k=3，limit=5） | completed，5/5 已评分 | 22s | 无 |
| 10 | Run2（top_k=5，limit=5） | completed，5/5 已评分 | 19s | 无 |
| 11 | 两 Run 对比 / 导出 CSV | 未出现 same-config 提示；CSV 下载成功 | 1s | 无 |
| 12 | 报告生成 / 下载 | Markdown 报告 completed，1.8 KB，下载成功 | 7s | 无 |
| 13 | Beta 提示 | RAG 评测页与 Run 详情均可见 | 1s | 无 |

> 有效流程总计 123 秒。此前有两次预跑（手工 FAQ 超时、429 限流）未计入本表，见第 6 节。

## 4. 证据 ID

| 项 | 值 |
|---|---|
| 数据源 ID | `46f247aa-f050-4f0b-a2f1-7e3ca8222aa0` |
| 清洗 Task ID | `0c1484cc-1c3b-4ef2-a3cf-e522e9d88ad1`（completed） |
| 质量 Task / 结果 ID | `929c39d0-f47c-4f68-86db-02e6e9c7a738` / `f68f1efc-932c-4711-a8f2-ae8594a4e604` |
| 知识提取 Task ID | `f7ddfc56-098f-4850-90c3-f5c692e806bd`（completed，5 条 FAQ） |
| QA 数据集 ID | `5ce71172-1471-46da-b415-82b15fe96473` |
| 版本 ID | `6b4edf7b-8031-4e3f-a7ac-a20d59848e98`（v1，published，5 条） |
| Run1 ID / top_k | `382a0146-36de-48c8-ac9b-f90b666b6206` / `3`（F 0.600 / C 0.300 / R 0.480） |
| Run2 ID / top_k | `41556235-9c96-4577-b0e0-8c4b43fc984b` / `5`（F 0.600 / C 0.300 / R 0.460） |
| 对比页提示 | 未出现“同配置比较”强警告；两条 Run 均为 completed，5/5 已评分 |
| Report ID | `90c8af98-99e6-44f4-9ca3-f5d7741fd399`（completed，Markdown） |
| 导出文件 | `compare.csv`、`report.md` |
| 证据目录 | `docs/releases/evidence/p0b-20261127/` |

### 截图索引

| 文件 | 内容 |
|---|---|
| `01-dashboard.png` | 登录后 Dashboard |
| `02-datasource-form.png` | 新建数据源表单 |
| `15-datasource-list-loaded.png` | 数据源列表（已就绪、5 条清洗） |
| `16-data-cleaning-loaded.png` | 清洗任务 completed + 5 条结果 |
| `04-quality.png` | 质量评估结果（平均 71.5） |
| `05-knowledge.png` | 知识库 5 条 FAQ |
| `06-dataset-published.png` | 数据集 v1 已发布 · 不可变 |
| `13-evaluation-modal-preselected.png` | 发布后发起评测，版本已预选 |
| `11-run1-detail.png` | Run1 详情（completed，5/5） |
| `12-run2-detail.png` | Run2 详情（completed，5/5） |
| `08-compare.png` | 两 Run 对比（含 Beta / 噪声提示） |
| `09-report.png` | 报告 completed + 下载 |
| `10-beta.png` | RAG 评测页 Beta 提示 |
| `compare.csv` | 对比导出 |
| `report.md` | 报告正文 |
| `p0b_ai_test_result.json` | 自动化执行原始记录（含时间/ID/步骤） |

## 5. 验收检查

- [x] 测试者业务操作全程 UI，未执行 CLI/SQL/seed；
- [ ] 空状态 CTA 逐项验证：本轮未单独逐项点击（自动化从顶部按钮进入）；
- [x] 发布后直接发起评测，版本已预选（截图 `13-evaluation-modal-preselected.png`）；
- [x] 两个 Run 的 top_k 不同（3 / 5），对比页未提示 same-config；
- [x] Beta 提示可见（`10-beta.png`、Run 详情）；
- [x] 报告 completed / 可下载；
- [x] 未写 `aiinsight_preprod`，未碰生产；
- [ ] 默认限流下无阻塞：本轮 demo 关闭了 `RATE_LIMIT_ENABLED`，默认限流未验证；
- [ ] 独立非开发者人类测试：未执行；
- [x] 有效流程 2 分 03 秒 ≤30 分钟（自动化时间，**不能**证明人类 ≤30 分钟）。

> 环境准备说明：测试前由开发/运维执行了 demo 库重置、migration 025、demo 账号 seed；这是 runbook 第 2 节允许的环境准备，不计入测试者的 UI 操作，但**不能**据此声称“全程零 SQL/seed”。

## 6. 卡点与结论

| 项 | 内容 |
|---|---|
| 预跑卡点 1 | 手工新建 FAQ 首次同步加载 embedding，超过前端 30s，UI 报网络异常；后端实际 `201 Created`。按 runbook 允许路径改用“提取知识（异步）”。建议记 P1。 |
| 预跑卡点 2 | AI 直连 API 每 3s 轮询评测状态，触发 demo 默认限流 429 `RATE_LIMIT_EXCEEDED`。重启 demo API（`RATE_LIMIT_ENABLED=false`）并重置 demo 库后重跑；属测试方式/环境问题，非产品缺陷，但**默认限流下的人类轮询行为仍未验证**。 |
| 有效流程阻塞步骤 | 无 |
| 是否重试 | 是（两次预跑后重跑成功） |
| 是否影响验收 | **是**：AI 不是独立非开发者，空状态 CTA 未逐项验证，默认限流未验证 |
| 测试结论 | **functional_verified**（仅功能链路） |
| 验收结论 | **pending_non_developer_test** |

> 结论边界：本次是 owner 指定的 AI 自动化实测，只作为功能证据，不能替代“未参与开发的非开发者”可用性测试。P0-B 保持 pending；P0-C 不开始。

## 7. 下一次人类测试要求

| 项 | 要求 |
|---|---|
| 测试者 | QA / 产品 / 业务同学，未参与 P0-B 开发；找不到时 owner 本人，记录标 `owner acceptance`，不冒充独立测试；不能是开发或 AI |
| 环境 | `aiinsight_demo` 空库；**保持默认限流，不关闭 `RATE_LIMIT_ENABLED`**；RAG mock；flag=false；不写 preprod/生产 |
| 必测 | 空状态 CTA 逐项点击（数据源 / 数据清洗 / 质量 / 知识库 / 报告 / QA 数据集 / RAG 评测）；数据集创建→导入→发布→发起评测；两个不同 top_k 的 Run；对比 + CSV；报告 + 下载；Beta 提示 |
| 记录 | 真实人类姓名/角色、开始/结束/总耗时、卡点、截图、Run/Report ID、是否使用 CLI、隔离确认 |
| 通过 | 人类全程浏览器、无 CLI；≤30 分钟；空状态 CTA 全部勾选；默认限流下无阻塞；未写 preprod/生产；记录完整 |

> 人类测试通过后，由 owner 给 P0-B accepted/blocked；AI 不再代填验收结论。
