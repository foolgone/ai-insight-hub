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
