# AI Insight Hub

> AI 客服数据分析平台 - 通过 AI Agent 自动清洗、评估和分析客服对话数据

**项目状态**：后端 MVP 已交付（P0~P7 完成；5 Agent + 42 个 HTTP 端点 + 462 个后端用例 + 323 个前端用例 + 8 条真栈 E2E）  
**文档版本**：v2.4  
**更新日期**：2026年10月26日

> 口径说明：端点 = `/api/v1` 下 39 个（37 个模块路由 + `/api/v1/health` + `/tasks/stream`）+ 系统级 3 个（`/`、`/health`、`/metrics`）；
> 用例数取自 `pytest --collect-only`（默认排除 255 个 prompt 标记用例）与前端 `vitest run`。当前项目状态与待办见
> [docs/07-review/01-项目现状与待办清单.md](./docs/07-review/01-项目现状与待办清单.md)。

---

## 📖 项目简介

AI Insight Hub 是一个智能数据中台，专门为 AI 客服/对话系统提供：

- 🔧 **数据清洗**：自动将非结构化对话数据标准化
- 📊 **质量评估**：5 维度评估 AI 回复质量（准确性、完整性、语气、合规性、幻觉）
- 📚 **知识提取**：自动构建 FAQ 知识库，发现知识盲区
- 💡 **洞察分析**：客户诉求分析、情感趋势、痛点识别
- 📄 **报告生成**：自动生成专业分析报告

---

## 🛠️ 技术栈

### 后端
- **Python 3.11+** | FastAPI | SQLAlchemy 2.0
- **自研 LLM 客户端**（httpx，OpenAI 兼容协议） | **DeepSeek V4.1 Flash**（不引入 LangChain/LangGraph，见 [ADR-001](./docs/04-development/13-ADR-001-移除LangChain与LangGraph.md)）
- 模型 id 由 `DEFAULT_LLM_MODEL` 配置决定，业务代码不写死

### 前端
- **React 18** | Vite 5 | TailwindCSS 3
- **React Query v5**（服务端状态） | **Zustand 4**（客户端状态）
- **Vitest**（单元测试）

### 数据库 / 存储
- **PostgreSQL 14 + pgvector**（384 维向量，HNSW 索引）
- **Redis 7** | **MinIO**（S3 兼容对象存储）

### 可观测（自建，不使用 LangSmith SaaS）
- **Loguru** 结构化日志
- **数据库调用记录**（每次 LLM 调用的 token / 成本 / 耗时）
- **Prometheus** 指标（`/metrics`）+ **Grafana** 看板（`--profile monitoring`，`ops/grafana/`）
- **Sentry** 错误追踪（前后端，`SENTRY_DSN` / `VITE_SENTRY_DSN` 为空时关闭）
- **任务进度 SSE**（`GET /api/v1/tasks/stream`，替代前端轮询）

### DevOps
- **Docker** | **Docker Compose** | **GitHub Actions**（`.github/workflows/test.yml` + `.github/workflows/e2e.yml`）

---

## 🚀 快速开始

### 前置要求

- **本地虚拟机**（VMware，提供 PostgreSQL + Redis，见 [`docs/00-本地VM数据库接入.md`](./docs/00-本地VM数据库接入.md)）
- **Python 3.11+**
- **Node.js 20+**
- **Git**

> 本机 Docker 已暂停使用；`docker-compose.yml` 保留为备选方案（见下文「方式 B」）。

### 安装步骤

#### 1. 克隆仓库

```bash
git clone https://github.com/foolgone/ai-insight-hub.git
cd ai-insight-hub
```

#### 2. 配置环境变量

```bash
# 后端
cd backend
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 等必要配置

# 前端
cd ../frontend
cp .env.example .env
```

> 后端配置项的事实源是 `backend/.env.example`，必须与 `backend/app/core/config.py` 一一对应。

#### 3. 准备基础服务（数据库 / 缓存）

**方式 A（默认，推荐）：使用本地虚拟机**

PostgreSQL 14 + pgvector 与 Redis 7 跑在本地 VMware 虚拟机 `192.168.150.100` 的 Docker 里，由宿主机直接连接：

| 服务 | 地址 | 说明 |
|------|------|------|
| PostgreSQL 14 + pgvector | `192.168.150.100:5433` | 容器 `aiinsight-postgres`，库/用户/密码 `aiinsight` / `aiinsight` / `dev_password` |
| Redis 7 | `192.168.150.100:6379` | 容器 `aiinsight-redis` |

- `backend/.env` 已按此地址配置，无需改动
- 启动/停止：登录 VM 后 `cd /root/ai-insight-hub-infra && docker compose up -d` / `down`
- 详细说明（含 VM 侧 compose 文件、扩展初始化、已知问题）：[`docs/00-本地VM数据库接入.md`](./docs/00-本地VM数据库接入.md)

**方式 B（备选）：沿用本机 Docker**

```bash
# 在项目根目录
docker-compose up -d
docker-compose ps
```

将启动 `aiinsight-postgres`（`localhost:5432`）、`aiinsight-redis`（`localhost:6379`）、`aiinsight-minio`（`localhost:9000`，控制台 `9001`）。
此时需把 `backend/.env` 的 `DATABASE_URL` / `REDIS_URL` / `CELERY_*` 改回 `localhost`。

首次启动会自动执行 `backend/scripts/init_db.sql`，创建 `vector` / `pg_trgm` / `pgcrypto` 扩展（VM 那套已执行过）。

#### 4. 安装后端依赖并初始化数据库

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows PowerShell: .\venv\Scripts\Activate.ps1

pip install -r requirements.txt -r requirements-dev.txt

# 运行数据库迁移
alembic upgrade head

# （可选）填充演示数据
python ../scripts/seed_data.py
```

#### 5. 启动后端

```bash
# 在 backend 目录
uvicorn app.main:app --reload --port 8000
```

访问：
- API 文档：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc
- 健康检查：http://localhost:8000/api/v1/health
- Prometheus 指标：http://localhost:8000/metrics

#### 6. 启动前端

```bash
# 在 frontend 目录
npm install
npm run dev
```

访问：http://localhost:5173

#### 一键启动（Windows）

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
```

---

## 🚀 生产部署（前端 + Nginx）

前端生产镜像采用多阶段构建（Node 构建 → Nginx 托管），SPA 路由由 `try_files` 回退，`/api` 反向代理到后端，gzip 在 Nginx 层开启：

```bash
# 1. 构建并启动全部服务（PG/Redis/MinIO/API/worker/beat/前端 Nginx）
docker compose -f docker-compose.prod.yml up -d --build

# 2. 仅构建前端镜像（构建上下文为仓库根目录）
docker build -f frontend/Dockerfile -t aiinsight-frontend .

# 3. 访问（默认 80 端口）
# http://<host>/dashboard 刷新不应 404
```

- `frontend/Dockerfile`：`VITE_API_URL` 构建参数（默认空 = 相对路径 `/api/v1`）
- `nginx/nginx.conf`：SPA 回退、`/assets` 长缓存、`/api` `/docs` `/health` 代理、gzip
- 前端环境变量见 `frontend/.env.example`
- 上线验收清单（含前端章节）：[`docs/04-development/15-上线验收清单.md`](./docs/04-development/15-上线验收清单.md)

## 📁 项目结构

> 当前前后端 MVP 均已交付：后端 5 个 Agent + 41 个端点，前端 7 个业务页面（含登录/404 共 9 个路由）。
> 目录注释与实现进度以 `backend/app`、`frontend/src` 实际内容为准。

```
ai-insight-hub/
├── README.md                    # 本文件
├── LICENSE                      # MIT
├── docker-compose.yml           # 开发环境服务编排
├── docker-compose.test.yml      # 测试环境（PostgreSQL 5433 / Redis 6380）
├── .github/workflows/test.yml   # CI：后端 pytest + 前端 vitest
├── .github/workflows/e2e.yml    # CI：E2E（PG/Redis + 前后端 + Chromium）
│
├── docs/                        # 📚 文档（47 份：需求/设计/架构/开发/UI/测试/审查）
│   ├── 00-AI应用开发基调.md
│   ├── 00-技术栈优化总结.md
│   ├── 01-requirements/         # 需求
│   ├── 02-design/               # Prompt 设计
│   ├── 03-architecture/         # 架构 / Agent / 数据库 / API
│   ├── 04-development/          # 开发规范 / 成本 / 方案 / 状态管理 ...
│   ├── 05-design/               # UI 设计规范
│   ├── 06-testing/              # 测试规范
│   └── 07-review/               # 文档审查报告
│
├── backend/                     # 🐍 Python 后端
│   ├── .env.example
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── alembic.ini
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py              # FastAPI 入口（/、/health、/api/v1/health、/metrics）
│   │   ├── core/config.py       # 配置事实源
│   │   ├── api/                 # API 路由（v1，39 个端点）
│   │   ├── models/              # SQLAlchemy 模型（15 张表）
│   │   ├── schemas/             # Pydantic Schemas
│   │   ├── agents/              # 5 个 Agent + 自研工作流编排器
│   │   ├── prompts/             # Prompt 资产库
│   │   ├── services/            # 业务服务（清洗/评估/知识库/报告/成本）
│   │   └── utils/               # 工具函数（重试/幂等/脱敏等）
│   ├── migrations/              # Alembic 迁移（env.py 已就绪）
│   ├── scripts/init_db.sql      # 数据库扩展初始化
│   └── tests/                   # 单元 / 集成 / 安全 / Prompt / 性能测试
│
├── frontend/                    # ⚛️ React 前端
│   ├── .env.example
│   ├── package.json
│   ├── vite.config.js
│   ├── vitest.config.js         # 测试配置（jsdom + 覆盖率门禁）
│   ├── tailwind.config.js       # 设计 Token 事实源
│   ├── .eslintrc.json
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx              # 应用入口（路由挂载于 router.jsx）
│   │   ├── router.jsx           # 路由表（懒加载 9 个页面）
│   │   ├── components/          # 通用/业务组件（Table、Chart、Radix 封装等）
│   │   ├── pages/               # 7 个业务页面 + 登录 + 404
│   │   ├── api/                 # Axios 客户端与各模块 API
│   │   ├── stores/              # Zustand（auth / datasource）
│   │   ├── hooks/               # React Query hooks
│   │   ├── lib/                 # 工具（CSV 导出、格式化、错误映射）
│   │   └── test/                # setup.js、utils.jsx（renderWithProviders / preloadRoutes）
│
└── scripts/                     # 🔧 工具脚本
    ├── dev.ps1                  # Windows 一键启动
    ├── dev.sh
    ├── init_project.sh / .bat
    └── seed_data.py             # 填充演示数据
```

---

## 🧪 开发

### 后端开发

```bash
cd backend
source venv/bin/activate        # Windows: .\venv\Scripts\Activate.ps1

# 代码格式化 / 检查
black app/ tests/
flake8 app/ tests/
mypy app/

# 运行测试（默认排除需要真实 LLM 的 prompt 测试）
pytest
pytest -m "not prompt" --cov=app --cov-report=html

# 启动开发服务器
uvicorn app.main:app --reload
```

### 前端开发

```bash
cd frontend
npm install
npm run lint          # ESLint
npm run test          # Vitest
npm run dev           # 开发服务器
npm run build         # 生产构建
```

---

## 🧪 测试

```bash
# 后端：单元 + 集成（排除 prompt）
cd backend && pytest -m "not prompt"

# 后端：Prompt 测试（需真实 LLM，注意成本）
pytest -m prompt

# 前端
cd frontend && npm run test:coverage

# 前端 E2E（真栈：需前后端已启动；本地用系统 Edge，详见 frontend/e2e/README.md）
cd frontend && npm run test:e2e
# CI 自动执行：.github/workflows/e2e.yml（PR 触发，PG/Redis + Chromium）
```

### 测试覆盖率目标

| 类型 | 目标 |
|------|------|
| 后端单元测试 | ≥ **80%** |
| 后端集成测试 | ≥ **60%** |
| Prompt 测试 | 每个 Agent **≥ 50 条**（每个维度 ≥ 10 条） |
| 前端组件测试 | 行/函数/语句 ≥ **80%**，分支 ≥ **70%**（见 `frontend/vitest.config.js` 的 `thresholds`） |

---

## 📊 成本预算

单条成本受 **模型单价 × token 用量** 直接决定，因此本文档**不写死金额**：

```
月成本 = (月输入 token × P_IN + 月输出 token × P_OUT) / 1_000_000
```

- `P_IN` / `P_OUT`：DeepSeek V4.1 Flash 的输入/输出单价（USD / 百万 token），**以官方最新定价为准**
- token 用量结构（每 1000 条对话的输入/输出 token）见 `docs/04-development/03-成本管理.md`
- 成本监控与告警见 `docs/04-development/09-可观测与成本监控.md`
- 超限降级策略见 `docs/04-development/06-成本超限降级策略.md`

> 早期文档中的 `$1,268 / 月`、`~$0.0127 / 条` 等数字基于 Claude 定价，已失效，不应再引用。

---

## 🎯 开发里程碑

| 里程碑 | 计划时间 | 状态 |
|--------|----------|------|
| M1: 环境就绪 | Week 1 | ✅ 完成 |
| M2: POC 完成 | Week 2 | ✅ 完成 |
| M3: 基础架构 | Week 4 | ✅ 完成 |
| M4: 数据清洗 | Week 6 | ✅ 完成 |
| M5: 质量评估 | Week 8 | ✅ 完成 |
| M6: 知识提取 | Week 10 | ✅ 完成 |
| M7: MVP 完成 | Week 12 | ✅ 完成 |
| M8: 上线就绪 | Week 14 | ✅ 完成 |

> 实际按后端 P0~P7、前端 P0~P5 的批次推进并交付；上表保留最初的计划口径，进度以
> [docs/07-review/01-项目现状与待办清单.md](./docs/07-review/01-项目现状与待办清单.md) 为准。

详见：`docs/04-development/04-开发方案.md`（总体方案）、[`docs/04-development/12-后端开发计划.md`](./docs/04-development/12-后端开发计划.md)（后端执行计划：阶段、任务 WBS、验收标准、决策清单）

---

## 📚 文档

完整文档见 `docs/` 目录（47 份，覆盖需求/设计/架构/开发/UI/测试/审查）：

- **需求**：`01-requirements/`（产品概述、用户调研、需求讨论记录）
- **设计**：`02-design/`（Prompt 工程规范、Prompt 版本管理）
- **架构**：`03-architecture/`（系统架构、Agent 详细设计、数据库设计、API 设计）
- **开发**：`04-development/`（开发规范、技术栈、成本管理、开发方案、状态管理、重试、降级、**后端开发计划**、**技术选型 ADR**...）
- **UI**：`05-design/`（视觉、组件、页面、响应式规范）
- **测试**：`06-testing/`（测试策略、后端单测/集成、Prompt 测试、前端测试）
- **审查**：`07-review/`（`00-文档审查报告`、`01-项目现状与待办清单`、`02-项目评估报告-代码复核版`，以及两份历史快照）

---

## 🤝 贡献指南

### 开发流程

1. 从 `main` 分支创建功能分支
2. 遵循代码规范（见 `docs/04-development/01-开发规范.md`）
3. 编写测试（覆盖率见上表）
4. 提交前运行检查：
   ```bash
   # 后端
   black app/ tests/ && flake8 app/ tests/ && pytest -m "not prompt"

   # 前端
   npm run lint && npm run test
   ```
5. 提交 PR，等待 Code Review

### Commit 规范

```
<type>(<scope>): <subject>

feat(agent): 实现数据清洗 Agent
fix(api): 修复数据源创建接口错误
docs(readme): 更新安装文档
```

类型：`feat` | `fix` | `docs` | `style` | `refactor` | `test` | `chore`

---

## 📞 联系方式

- **项目文档**：[docs/](./docs/)
- **问题反馈**：GitHub Issues
- **开发讨论**：GitHub Discussions

---

## 📄 许可证

[MIT License](./LICENSE)

---

## 🙏 致谢

- [httpx](https://www.python-httpx.org/) - HTTP 客户端（LLM 调用）
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Web 框架
- [React](https://react.dev/) - UI 框架
- [DeepSeek](https://www.deepseek.com/) - 本项目使用的 LLM

---

**准备开始开发了吗？** 🚀

后端已按 [后端开发计划](./docs/04-development/12-后端开发计划.md) 完成 P0~P7：
- 部署与运维：[部署与运维手册](./docs/04-development/14-部署与运维手册.md)
- 上线验收：[上线验收清单](./docs/04-development/15-上线验收清单.md)
- 架构决策：[ADR-001（去 LangChain/LangGraph）](./docs/04-development/13-ADR-001-移除LangChain与LangGraph.md)

前端按 [前端开发计划](./docs/05-design/05-前端开发计划.md) 执行 P0~P5（设计规范见 `docs/05-design/`，当前实现进度以 `frontend/src` 为准）：

```powershell
# 生产部署（容器启动前自动执行迁移）
docker compose -f docker-compose.prod.yml up -d --build
```
