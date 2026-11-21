# RAG 评测与优化平台 · 现状基线（Phase 0）

> 生成时间：2026-11-13
> 范围：`D:\code\AI Project Engineering\ai-insight-hub`（后端 `backend/`、前端 `frontend/`、部署 `docker-compose*.yml`）
> 方法：只读代码核查 + 实际执行测试/迁移/健康检查。**本文件不改动任何业务代码。**
> 结论以**当前代码**为准；与《企业级 RAG 评测与优化系统功能审计报告》不一致处，见第 9 节。

---

## 1. 结论摘要

| 问题 | 结论 |
|---|---|
| 当前系统是什么 | 客服**对话质量分析平台**：清洗 → 结构化 → 5 维质量评估 → 洞察 → 报告 |
| 距离 RAG 评测平台的目标 | 缺三件决定性能力：**数据集实体**、**`query→contexts→answer` 三元组**、**可复算的检索指标** |
| 可复用资产 | LLM-as-Judge 引擎、批次对比、Celery 任务体系、分层架构与 CI 门禁、BYOK 凭据加密 |
| 现有 RAG 评测资产在哪 | **不在本仓库**：459 条 Gold 与 RAGAS 结果在 `工作台自动化人机应答\知识库测试`；原始 case 在 `会话分类统计` |
| 本次升级的性质 | 在既有平台内**新增三条垂直链路**（数据集 / RAG 执行 trace / 实验），复用现有 Agent、任务、鉴权与前端骨架 |

---

## 2. 项目定位与实际能力边界

### 2.1 自述定位

`README.md`：「AI 客服数据分析平台 —— 通过 AI Agent 自动清洗、评估和分析客服对话数据」。
**不是** RAG 评测系统：全仓库检索 `ragas|faithfulness|context_precision|context_recall|ndcg|mrr|hit_rate|rerank|bm25|query_rewrite` 命中 **0**。

### 2.2 实际链路（已验证调用链）

```
HTTP API（42 个端点，backend/app/api/v1/*.py）
  → services（编排 + 事务 + 归属校验）
    → application（structure_service 内容路由 / task_control / media_pipeline）
      → agents（BaseAgent：校验→降级→重试→结构化输出→成本记账）
        → repositories（SQL 唯一入口）
          → models（18 张表）
            → PostgreSQL 14 + pgvector / Redis / MinIO
异步：api → composition.enqueue（唯一 .delay 处）→ tasks/*（Celery）→ services.run_*_task
```

分层由 `backend/.importlinter` 强制 5 条契约（`declared-layers` / `http-layer-not-depended-on` / `data-layer-is-leaf` / `ports-are-inner` / `repositories-are-inner`），CI 中 `lint-imports` 阻塞。

### 2.3 技术栈（核实）

| 层 | 事实 |
|---|---|
| 后端 | Python 3.11、FastAPI、SQLAlchemy 2.0（async）、Celery 5、Alembic |
| 存储 | PostgreSQL 14 + pgvector（384 维，HNSW）、Redis（限流/黑名单/broker）、MinIO（对象存储） |
| LLM | 自研 httpx 客户端（OpenAI 兼容），默认 `deepseek-flash`，BYOK（Fernet 加密，fail-closed） |
| 前端 | React 18、Vite 5、Tailwind、React Query v5、Zustand、8 个页面 |
| 部署 | docker compose 九服务（postgres/redis/minio/api/worker/beat/nginx/prometheus/grafana） |
| 观测 | Loguru、Sentry、Prometheus `/metrics`、Grafana、`llm_calls` 成本表、任务进度 SSE |

---

## 3. 现有能力清单（含代码位置）

### 3.1 可直接复用（本次升级的底座）

| 能力 | 代码位置 | 说明 |
|---|---|---|
| Agent 基座（重试/降级/结构化/成本/幂等） | `app/agents/base.py` | `invoke()` 全流水线；`AgentConfig`（model/temperature/max_tokens） |
| 评估 Agent（5 维 LLM Judge） | `app/agents/evaluation_agent.py` + `app/prompts/evaluation/dimensions/*.txt` | 维度权重 0.35/0.25/0.20/0.10/0.10，阈值 70，输出 `issue_items` 七分类 |
| 评测结果持久化 | `app/models/analysis.py: AnalysisResult` | `result JSONB` + `task_id`（批次，迁移 016） |
| 批次对比 | `app/services/run_service.py: compare_runs / compare_insights` | 总分/维度/档位/单条对话差集/问题分类变化 |
| 任务体系 | `app/services/task_service.py`、`app/api/v1/tasks.py`、`app/composition/{executors,enqueue}.py` | 5 类任务、状态机、取消/重试、进度、SSE |
| 凭据（通用表） | `app/models/llm_credential.py`、`app/services/credential_service.py` | `(user_id, provider)` 唯一；迁移 013 起为「通用用户凭据」，可扩展 provider |
| 鉴权/RBAC/归属 | `app/api/deps.py`、`app/core/ownership.py` | admin/user/viewer + `assert_owner` |
| 前端骨架 | `frontend/src/components/*`、`pages/*` | 表格/抽屉/弹窗/筛选/空态/错误态组件齐全 |
| 备份/恢复 | `ops/backup/{backup,restore,drill}.sh` | 已做过恢复演练 |

### 3.2 部分实现（质量不足，本次要修）

| 能力 | 现状 | 缺口 |
|---|---|---|
| 知识检索 | `app/repositories/knowledge_base.py: search`：`trgm*0.4 + vector*0.6` | 权重硬编码；只搜 FAQ 表；无 rerank；无检索日志；`cleaned_data.embedding` 从未写入（`scripts/reembed_knowledge.py` 注释自证） |
| 覆盖率 | `knowledge_service.coverage`（向量优先，退化 trgm） | 只对 `knowledge_base`；空库仍显示 0% |
| 评测上下文 | `evaluation_service._knowledge_snippets`：取**前 5 条 active FAQ** | 不是检索结果，无法归因检索/生成 |
| Prompt 版本 | 文件版 `app/prompts/<agent>/{system.txt,version.txt}` | DB 表 `prompt_versions` 存在但零引用 |
| 数据集导出 | `frontend/src/pages/KnowledgeBase/index.jsx: handleExport` | 仅导出当前页 FAQ；无导入、无版本 |

### 3.3 仅有结构（死代码，本次禁止继续加码）

| 对象 | 证据 | 状态 |
|---|---|---|
| `prompt_versions` / `prompt_usage_logs` / `version_rollback_logs` | `app/models/prompt.py` + 迁移 004 | 无 service / 无 API / 无引用 |
| `api_keys` / `webhooks` / `audit_logs` | `app/models/security.py` | 仅凭据服务写 `AuditLog`；API Key 与 Webhook 无路由 |
| `cleaned_data.embedding` + HNSW 索引 | `app/models/datasource.py`、迁移 002 | 列与索引存在，代码从不写入 |

### 3.4 完全缺失（本次目标）

数据集（含版本/条目/证据）、RAG Adapter、RAG Trace、检索指标（HitRate/MRR/Context Recall/Precision）、实验与运行记录、失败归因、Trace 回放。

---

## 4. 数据模型现状

### 4.1 表清单（18 张，Alembic head = `9a4d2f8c6e15`，迁移 001–018）

`users`、`data_sources`、`datasource_types`、`raw_data`、`cleaned_data`、`knowledge_base`、`knowledge_gaps`、`analysis_results`、`reports`、`tasks`、`llm_calls`、`user_llm_credentials`、`prompt_versions`、`prompt_usage_logs`、`version_rollback_logs`、`api_keys`、`audit_logs`、`webhooks`。

### 4.2 与 RAG 评测直接相关的关键字段

| 表 | 关键字段 | 问题 |
|---|---|---|
| `analysis_results` | `datasource_id`(FK)、`data_id`(无 FK)、`task_id`、`analysis_type ∈ quality/knowledge/insight/other`、`result JSONB` | 强绑定 `cleaned_data` 语义；**承载不了 dataset item** |
| `knowledge_base` | `question/answer/category/tags/confidence/quality_score/raw_data_id`(逻辑外键) + `embedding` | 无 gold evidence / 无 chunk 正文 |
| `cleaned_data` | `user_message`、`ai_response`、`quality_score`、`embedding`(空) | **单轮**，无多轮/无上下文 |
| `tasks` | `task_type ∈ clean/structure/evaluate/extract/analyze/report`、`params`、`progress`、`result` | 需扩展新任务类型 |

### 4.3 数据完整性风险（本次迁移需一并处理或明确不处理）

1. `analysis_results.data_id` **无外键**，重切/删除 `cleaned_data` 后会留下悬空结果；
2. `knowledge_base.raw_data_id` 为「逻辑外键」，无约束；
3. `tasks` 在 worker 重启后可能永久停留 `running`（2026-11-13 E2E 实测），会阻塞同数据源同类任务（409）。

---

## 5. 评测能力现状（本次核心）

### 5.1 已实现：对话质量 LLM-as-Judge

- 输入：`dialogue{user_message, ai_response, timestamp}` + `knowledge_base[:5]` + `config{dimensions, threshold}`；
- 输出：`overall_score`、5 维分、`has_issues`、`critical/minor issues`、`suggestions`、`issue_items[7 类]`、`needs_review`、`quality_level`；
- 持久化：`analysis_results.result`（JSONB）+ `task_id` 批次；
- 人工复核：`POST /analysis/quality/{id}/review`（通过/驳回/改分）；
- 统计：均分、维度均分、needs_review、TOP 问题分类；
- 测试：`tests/unit/test_evaluation_agent.py`、`tests/integration/test_evaluation_api.py`。

### 5.2 缺失：RAG 三元组与检索指标

| 目标指标 | 现状 |
|---|---|
| HitRate@K / MRR / Context Recall / Context Precision | **无** |
| Faithfulness（claim 级） | 只有对话级 `hallucination` 0–100 主观分 |
| Answer Correctness / Relevancy | 无标准答案概念，只有 `accuracy` 主观分 |
| Context 是否存在/无关/冲突/缺失 | 无 contexts 概念 |

### 5.3 Judge 可信度现状

无重复评测、无人工一致性（kappa）、无置信区间、无 Judge 输出原文留存（`llm_calls` 只存 token/cost/duration，不存 prompt/response）。
→ 本次改造必须补上「Judge 原始输出 + Prompt 版本 + 模型」三件套。

---

## 6. 外部已有资产盘点（本次要接入的数据）

### 6.1 原始 case（`会话分类统计`）

| 资产 | 规模 | 可用性 |
|---|---|---|
| `sessions.db` | **28,581 行**，其中 26,740 行同时含访客+客服发言；2,985 家公司 | 可解析为 `user_message/ai_response`；含系统消息/链接（22,754 行）需过滤 |
| `knowledge_items.csv` | 16,993 行（标准问 + 可答性 + 优先级 + 冲突） | 可作「知识需求」，**不是**评测金标 |
| `taxonomy_v2.json` | 四级分类 + Agent 可解比例 | 可作 `category` 取值来源 |

### 6.2 Gold Dataset（`工作台自动化人机应答\知识库测试\03_RAGAS评测\evalset_ragas_full.json`）

- 共 **459 条**：`conv:knowledge` 237 + `doc:yuliu-agent` 112 + `doc:robot-backend` 110；
- 字段：`id / question / ground_truth / category / source / session_id / evidence_doc_id / evidence_status / answer_type / priority / llm / original_question / restored`；
- **证据状态**：`mapped` 222（全部 doc 类），`pending` 237（全部 conv 类，只有答案文本，无文档证据）；
- **无 `contexts`**（检索上下文只存在于 `coverage_classified.json` 的 `top_kids / top_titles`）。

### 6.3 已有的 RAGAS 结果（`04_结果报告/result-json/ragas_results.json`）

459 条，逐条含 `answer`、`context_titles`、`n_contexts`、`metrics{score, reason}`：

| 指标 | 均值 | <0.5 占比 |
|---|---|---|
| faithfulness | 0.783 | 18.1% |
| context_precision | 0.566 | 39.6% |
| context_recall | 0.446 | **52.1%** |
| answer_correctness | 0.545 | 49.0% |
| semantic_similarity | 0.562 | 47.1% |

覆盖归因（`coverage_classified.json` + `coverage_report.md`）：`context_recall<0.5` 的 172 条中，**B 型（事实在库、检索没捞到）18 条**，**A 型（事实不在库）154 条**。

### 6.4 已有的检索层评测（文档级）

`01_数据构建/机器人后台/retrieval_eval_result_机器人后台设置.json`（110 题）：

```
Recall@1 0.618 / @3 0.755 / @5 0.791 / @10 0.873；MRR 0.699
```

这是本次指标的**现实基线**，也证明「文档级锚点」可用但会低估（脚本注释自述）。

### 6.5 WeKnora 接口契约（从外部脚本实测反推，**无密钥入库**）

| 能力 | 方法与路径 | 请求 | 响应要点 |
|---|---|---|---|
| 建会话 | `POST /api/v1/sessions` | `{title, description}`，Header `X-API-Key` | `data.id` |
| 智能体问答 | `POST /api/v1/agent-chat/{session_id}` | `{query, agent_enabled:true, agent_id}` | JSON 或 **SSE**（`answer` 事件拼接答案；`tool_result.data.results` 为检索片段） |
| 纯检索 | `POST /api/v1/knowledge-bases/{kb_id}/hybrid-search` | `{query_text, match_count, vector_threshold, keyword_threshold}`，Header `X-API-Key` + `X-Tenant-ID` | `knowledge_id / knowledge_title / content`，**实测无 score** |

证据：`ragas_runner.py`（sessions/agent-chat + SSE 解析）、`rag_retrieval_eval.py`（hybrid-search + Recall/MRR）。

> ⚠️ 外部脚本中出现过明文 API Key / Agent ID，**不得复制进本仓库**；本次通过环境变量/凭据表注入。

---

## 7. 基线验证结果（本次实跑）

| 检查 | 命令 | 结果 |
|---|---|---|
| Python/依赖 | `backend/venv` | 正常 |
| 数据库迁移 | `alembic current` / `alembic heads` | `9a4d2f8c6e15 (head)`，无多 head |
| 迁移数量 | `migrations/versions` | 18 |
| 后端测试 | `pytest -m "not prompt"` | **730 passed**（collected 985，deselected 255 条 prompt 用例） |
| 类型检查 | `mypy app` | `Success: no issues found in 143 source files` |
| 分层契约 | `lint-imports` | **5 kept, 0 broken** |
| 前端 | `npm run test:coverage` | 77 文件全绿；行 95.58% / 分支 83.38% / 函数 81.26% |
| 环境健康 | `GET /health`（云端 8443、VM） | 均 200 |
| 本地 Docker | `docker ps` | **未启动**（本机依赖远程 VM 的 PG/Redis） |

> 说明：本机测试连接 `192.168.150.100:5433`（`backend/.env` 的 `DATABASE_URL`），不依赖本地 Docker。

---

## 8. 与《功能审计报告》的差异（以代码为准）

| 审计表述 | 代码事实 | 处理 |
|---|---|---|
| 「459 条 Gold 已建设」 | 不在本仓库，在外部目录，且 237 条无证据 | 本次按「外部数据」接入，不假设已入库 |
| 「LLM-as-Judge 已实现」 | 正确，但评的是**对话质量**，非 RAG 三元组 | 保留引擎，新增 RAG 指标层 |
| 「混合检索已实现」 | 仅 FAQ 表，权重硬编码，无日志 | 不改造它，另建 Trace 记录外部检索 |
| 「Prompt 版本管理」 | 只有表，无任何调用 | 标记为死结构，本次不投入 |
| 「多租户」 | 仅用户级隔离 | 维持现状，不扩 |

---

## 9. 本次升级的风险清单

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | **WeKnora 不可达/无凭据** | Phase 2/3 真实联调阻塞 | Adapter 先做 Mock + 契约测试；凭据走 `user_llm_credentials(provider='weknora')`，不落盘明文 |
| R2 | WeKnora **不返回检索分数** | MRR/Precision 只能用排名，无法用分数阈值 | 指标定义以「排名/ID 命中」为准；`score` 允许为 null 并记录「外部未提供」 |
| R3 | 459 条中 **237 条无证据文档** | Context Recall 无法对这批计算 | 分数据集管理（doc / conv），conv 集仅算答案类指标；证据补齐单独任务 |
| R4 | 检索返回 **chunk 正文可能被截断**（外部脚本 `content[:1500]`） | 证据快照不完整 | Adapter 保存原始响应 + 截断标记；入库 `truncated: true` |
| R5 | 新增表与既有 `analysis_results` 语义冲突 | 数据混乱 | 独立表 `rag_eval_results`，不复用 `analysis_type` |
| R6 | 迁移影响线上（18 张表已有数据） | 停服/回滚成本 | 只新增表，不改旧表；迁移用 `create_table` + 索引，先备份（`ops/backup/backup.sh`） |
| R7 | 任务类型扩展遗漏注册 | worker 拒收（历史踩过：`tasks.structure_raw`） | 沿用「所有任务名必须已注册」的测试断言（`tests/unit/test_celery.py`） |
| R8 | 前端新增页面破坏覆盖率阈值 | CI 失败（80/70/80） | 每个新组件配最小测试；复用现有组件降低表面积 |

---

## 10. 阻塞项（需人工确认，Phase 0 不擅自假设）

| # | 事项 | 为什么必须确认 |
|---|---|---|
| Q1 | WeKnora 的 `BASE_URL` / `API_KEY` / `AGENT_ID` / `KB_ID` / `TENANT_ID` 由谁提供、放在哪 | 决定 Adapter 配置与真实联调能否进行 |
| Q2 | 评测时走「纯检索（hybrid-search）」还是「智能体问答（agent-chat）」 | 前者只能算检索指标，后者能算生成指标；决定一次评测的调用次数与成本 |
| Q3 | 459 条是否按 `source` 拆成两个数据集（doc 222 / conv 237） | 决定统计口径与 Context Recall 是否可算 |
| Q4 | Gold Evidence 的粒度：文档级（现有 `evidence_doc_id`）还是 chunk 级 | 决定 Context Recall 的匹配规则与是否需要回填 chunk 映射 |
| Q5 | 是否允许把 459 条原始文件复制进仓库/数据库 | 涉及业务数据外流与仓库体积 |

---

## 11. 基线结论

1. **底座可用**：Agent/Judge/任务/鉴权/前端/CI 都完整，且当天刚完成过一次线上止血（PR #38）；
2. **评测语义必须新增**，不能在 `analysis_results` 上硬改；
3. **外部数据已就绪**（459 条 + 真实 RAGAS 结果 + 真实检索基线），但**格式不标准、证据不完整、无版本**；
4. 本次升级的关键不是「写多少表」，而是**让每一条指标都能回到一条 trace、一条证据、一个数据集版本**。
