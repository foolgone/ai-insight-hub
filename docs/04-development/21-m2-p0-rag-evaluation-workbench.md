# M2 P0：RAG 评测工作台

> 状态：`implemented`；前端页面 + 现有 API 接入；真实环境端到端 Run 待执行（本机未启动 Docker/Postgres/Redis）。
> 日期：2026-11-24
> 上游决策：停止 M1 校准，Judge 降级为 beta；平台验收改为“能完成一次完整评测并看到可解释结果与报告”。

## 1. 交付范围

| 页面 | 路由 | 内容 |
|---|---|---|
| Run 列表 | `/rag-evaluations` | 状态、时间、数据集/模式、F/C/R、invalid/failed 计数、新建评测 |
| Run 详情 | `/rag-evaluations/:runId` | 指标卡、样本进度、known issues、Case 列表、失败/invalid 列表、报告入口 |
| Case 详情 | `/rag-evaluations/:runId/cases/:itemId` | question、answer、contexts、claims/evidence、invalid 原因、raw output |

侧边栏新增一级入口 **RAG 评测**（位于“质量评估”之后）。

## 2. 复用的现有 API

| 用途 | API |
|---|---|
| Run 列表 / 详情 | `GET /api/v1/rag/evaluations`、`GET /api/v1/rag/evaluations/{run_id}` |
| 结果 / 失败 | `GET /api/v1/rag/evaluations/{run_id}/results`、`/failures` |
| 新建 / 重试 / 取消 | `POST /api/v1/rag/evaluations`、`/{run_id}/retry`、`/{run_id}/cancel` |
| Trace（question/answer/contexts） | `GET /api/v1/rag/traces/{trace_id}` |
| 数据集 / 版本 / 条目 | `GET /api/v1/qa-datasets`、`/{id}/versions`、`/{id}/versions/{version_id}/items` |
| 报告 | 复用 `/reports` 现有页面与导出 |

后端唯一改动：`RagEvaluationRunListItem` 增加 `aggregate` 只读字段（列表页展示 F/C/R），无新路由、无分层变化。

## 3. 展示口径

- F/C/R 取 `aggregate.metrics[metric].mean`；无有效评分为 `—`，不显示 0。
- `invalid`、`failed`、`skipped`、`unprocessed` 原样显示：
  - 列表页：invalid / failed 徽章；
  - 详情页：known issues 面板 + 失败列表；
  - Case 页：逐指标 status + `invalid_reason`。
- Beta 提示固定在页面顶部：v1.2.5 为 frozen/inactive beta；人工复核可覆盖。
- 不把 invalid 隐藏或折算成 0；不用 target 通过率作为平台门槛。

## 4. 真实流程 Runbook（环境可用后执行）

前置：Postgres(pgvector)、Redis、MinIO 已启动；API、worker、前端已运行。

1. 登录平台，进入 **Dashboard**。
2. **数据源管理**：创建数据源并上传对话/问答数据。
3. **数据清洗**：创建清洗任务，等待完成并抽查清洗结果。
4. **质量评估**：触发一次质量评估，确认结果可查看。
5. **RAG 评测** → 新建评测：
   - 选择数据集版本；
   - 模式选 `query`（或 `retrieve`）；
   - 适配器先用 `mock` 验证链路，再切 `weknora`；
   - 条数上限 20；
   - 创建并运行。
6. 打开 Run 详情：确认 F/C/R、样本进度、invalid/known issues 可见；进入任一 Case 查看 question/answer/contexts 与 claims/evidence。
7. **报告中心**：生成/查看报告，确认可导出。
8. 记录：Run ID、任务状态、指标、invalid 数、报告 ID。

验收：上述 8 步无需改代码即可完成；Judge 的 invalid/known issues 在页面上可见。

## 5. 测试证据

| 项 | 结果 |
|---|---|
| `npm run lint` | pass（0 warning） |
| `npm run test:coverage` | pass；新增页面/库/API 均有单测；全局阈值 80/80/80/70 通过 |
| `npm run build` | pass |
| 后端 `pytest tests/integration/test_rag_evaluations.py` + 两个 unit 规则文件 | pass（49 条） |
| `black` / `flake8` / `mypy`（改动文件） | pass |

新增测试：`src/api/ragEvaluations.test.js`、`src/lib/ragEvaluation.test.js`、`src/pages/RagEvaluations/*.test.jsx`。

## 6. 已知限制（P0）

- 列表最多展示最近 100 条结果；更大 Run 需要分页/虚拟滚动（P1）。
- Run 详情暂未提供“重试失败样本”按钮（API 已存在，P1 接入）。
- 报告入口跳转现有 Reports 页；尚未把 Run 指标注入报告模板（P1）。
- 数据集创建/导入仍走 API；M2 P0 不提供数据集管理页。
- 本机未启动 Docker/Postgres/Redis，真实 Run 未在本轮执行；代码与测试已就绪。

## 7. 下一步

1. 在可用环境跑通第 4 节流程，记录 Run/报告。
2. M3：两个 Run 的前后对比（复用 `RunComparisonPanel` 的交互模式）。
3. M4-A：租户、保留期、审计、告警、成本、数据权利。

## 8. 执行记录（2026-11-24，VM Docker 拓扑）

### 8.1 环境

| 组件 | 位置 | 说明 |
|---|---|---|
| PostgreSQL | VM `192.168.150.100:5433` | `aiinsight` 容器；`alembic upgrade head` 通过 |
| Redis | VM `192.168.150.100:6379` | `aiinsight-redis`；Celery broker `/1`、result `/2` |
| API | Windows 宿主机 `:8000` | uvicorn；`STORAGE_BACKEND=local`、`RAG_ADAPTER=mock` |
| Celery worker | Windows 宿主机 | `-P solo`；任务 `tasks.rag_evaluation` 正常消费 |
| 前端 | Windows 宿主机 `:5173` | Vite dev server |
| MinIO | 未使用 | 本轮 `STORAGE_BACKEND=local` |
| RAG | `mock` | 不依赖 WeKnora |

### 8.2 测试数据

| 项 | 值 |
|---|---|
| seed 脚本 | `backend/scripts/seed_rag_eval.py`（幂等，仅本地测试） |
| dataset_id | `d3a7071f-1385-4cf0-9fbb-8c607646ba14` |
| version_id | `9e7e73cb-f4f2-486e-a75d-b347c722e0d1` |
| items | 5 条（M2P0-01..05，mock 上下文对齐） |

### 8.3 真实 Run

| 项 | 值 |
|---|---|
| Run ID | `67596d50-5782-456e-a96a-63929b9a9a80` |
| 状态 | **completed** |
| 样本 | 5 / 5 evaluated；invalid 0；failed 0；skipped 0 |
| F / C / R | **0.700 / 0.120 / 0.540** |
| faithfulness_strict | 1.000 |
| Judge 模型 | `qwen-flash`（DashScope；v1.2.5 frozen/inactive；非校准） |
| 任务 | Celery 正常消费，API 轮询到 completed |

机读摘要：`docs/04-development/assets/m2-p0/run-67596d50-summary.json`（含逐 case F/C/R 与失败 Run 原因）。

失败 Run（保留展示，作为 known issues 证据）：

| Run ID | 原因 |
|---|---|
| `574476ec-b5bd-49fe-8ebc-8381f057e40f` | BYOK 未配置 DeepSeek Key（`LLMCredentialNotConfiguredError`） |
| `33298d98-dcce-4250-9210-37fd134674d7` | DeepSeek 账户 402 Insufficient Balance |

### 8.4 页面验收（6/6）

| 验收项 | 结果 |
|---|---|
| 真实 Run，不是 mock 页面数据 | ✅ 来自 VM PG + Celery |
| 列表显示真实 F/C/R | ✅ 0.70 / 0.12 / 0.54 |
| 详情指标与 API 一致 | ✅ F 0.700、C 0.120、R 0.540 |
| Case 详情能看到 answer/contexts/claims/evidence | ✅ question/answer/gold、3 条 contexts、claims + quote |
| invalid/skipped/failed 不隐藏、不折算 0 | ✅ 失败 Run 显示 failed；成功 Run 显示 0 |
| 报告入口可用 | ✅ `/reports` 打开“报告中心”，可进入生成报告 |

截图：

- `docs/04-development/assets/m2-p0/run-list.jpeg`
- `docs/04-development/assets/m2-p0/run-detail.jpeg`
- `docs/04-development/assets/m2-p0/case-detail.jpeg`

### 8.5 已知问题（P0）

- 页面加载初期 `/datasources`、`/users/me/llm-credential` 偶发 401（auth hydration 竞态），随后恢复，不影响页面数据；建议 P1 修。
- Judge 依赖运行账号的 LLM 可用性；本轮 DeepSeek 402 时改用 DashScope `qwen-flash` 完成验收。
- 失败 Run 不会自动清理，列表会同时显示 failed 与 completed（符合“known issues 不隐藏”）。
- 数据集仍通过 seed 脚本创建，M2 P0 无数据集管理页。

### 8.6 状态

- M2 P0：**accepted**（2026-11-24，项目决策角色确认）。
- accepted 范围：**RAG 评测工作台 P0 的页面与真实 Run 流程**；不包含 Judge 质量，也不包含 M1。
- 本轮 Judge 使用 `qwen-flash` 仅为运行时配置，不是模型切换、不是 baseline；F/C/R 不得作为 M1 证据。
- 已知问题转 P1 backlog（不阻塞 accepted）：auth hydration 401 竞态、无数据集管理页、failed Run 不自动清理。
- 下一步：M3 P0 两 Run 对比；M4-A 约束文档并行。
