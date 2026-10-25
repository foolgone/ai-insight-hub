# AI Insight Hub - Backend

## 快速开始

### 环境要求

- Python 3.11+
- 数据库/缓存：本地 VMware 虚拟机 `192.168.150.100` 的 Docker（PostgreSQL 14 + pgvector 映射 5433 / Redis 7 映射 6379），
  详见 [`docs/00-本地VM数据库接入.md`](../docs/00-本地VM数据库接入.md)；本机 `docker-compose.yml` 保留为备选

### 安装

```bash
python -m venv venv

# 激活虚拟环境
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

# 安装依赖（含开发依赖：pytest、black、flake8、mypy 等）
pip install -r requirements.txt -r requirements-dev.txt
```

### 配置

```bash
cp .env.example .env
# 然后按需修改 .env
```

`.env.example` 是配置项的事实源，必须与 `app/core/config.py` 一一对应。常用项：

```dotenv
# 数据库（与 docker-compose.yml 的 POSTGRES_USER / POSTGRES_DB 一致）
DATABASE_URL=postgresql://aiinsight:dev_password@localhost:5432/aiinsight

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT（唯一来源，不再单独定义 SECRET_KEY）
JWT_SECRET_KEY=your-jwt-secret-key-change-this

# LLM：DeepSeek V4.1 Flash（langchain-deepseek 官方集成）
DEEPSEEK_API_KEY=your-deepseek-api-key-here
DEFAULT_LLM_MODEL=deepseek-flash   # 模型 id 由配置决定，业务代码不写死

# 可观测（自建：Loguru + DB 调用记录 + Prometheus；不使用 LangSmith）
PROMETHEUS_ENABLED=true
METRICS_PATH=/metrics
```

### 初始化数据库

```bash
# 1) 确认 VM 上的数据库/缓存已启动（在 VM 内执行）
cd /root/ai-insight-hub-infra && docker compose up -d

# 2) 执行迁移（VM 那套已在建库时创建 vector / pg_trgm / pgcrypto 扩展）
alembic upgrade head

# 3) 可选：填充演示数据
python ../scripts/seed_data.py
```

> 备选：改回本机 `docker-compose up -d` + `localhost:5432`（见仓库根目录 README「方式 B」）。

### 运行

```bash
# 开发模式（热重载）
uvicorn app.main:app --reload --port 8000

# 或直接运行
python app/main.py
```

访问：

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health
- 业务前缀健康检查：http://localhost:8000/api/v1/health
- Prometheus 指标：http://localhost:8000/metrics

### 测试

```bash
pytest                                  # 单元测试（-m "not prompt" 已在 CI 使用）
pytest -m "not prompt" --cov=app        # 带覆盖率
pytest -m prompt                        # Prompt 测试（需真实 LLM，注意成本）
```

测试分层标记见 `pytest.ini`：`unit` / `integration` / `prompt` / `slow`。
集成测试依赖：`docker-compose -f ../docker-compose.test.yml up -d`（PostgreSQL 5433 / Redis 6380）。
> 本机 Docker 暂停期间先用 VM 库做开发联调；集成测试库建议单独建（勿把用例跑在 `aiinsight` 开发库上）。

## 项目结构

```
backend/
├── app/
│   ├── main.py            # 应用入口（/、/health、/api/v1/health、/metrics）
│   ├── core/
│   │   └── config.py      # 配置事实源（与 .env.example 一一对应）
│   ├── api/               # 规划：API 路由
│   ├── agents/            # 规划：5 个 Agent
│   ├── models/            # 规划：SQLAlchemy 模型
│   ├── schemas/           # 规划：Pydantic Schemas
│   ├── prompts/           # 规划：Prompt 资产库
│   ├── services/          # 规划：业务服务
│   └── utils/             # 规划：工具函数
├── migrations/            # Alembic 迁移（env.py 从 settings 读取 DATABASE_URL）
├── scripts/
│   └── init_db.sql        # 数据库扩展初始化（vector / pg_trgm / pgcrypto）
├── tests/                 # 目前为冒烟测试（conftest.py + test_smoke.py）
├── alembic.ini
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## 约定

- **配置**：新增配置项时同时改 `app/core/config.py` 与 `.env.example`，两者必须一致。
- **模型**：LLM 调用统一走自研 `app/core/llm.py::LLMClient`（OpenAI 兼容协议，HTTP 客户端用 httpx），
  模型 id 读 `settings.DEFAULT_LLM_MODEL`；**不使用 LangChain/LangGraph**（见 `docs/04-development/13-ADR-001`）。
- **可观测**：每次 LLM 调用需记录到数据库（token / 成本 / 耗时）并上报 Prometheus 指标。
- **中文检索**：MVP 使用 `pg_trgm`；zhparser 需自建镜像，见 `docs/03-architecture/03-数据库设计.md` 附录。

## 下一步

- [x] 配置与依赖对齐（`config.py` / `.env.example` / `requirements*.txt`）
- [x] 数据库扩展初始化脚本、Alembic 骨架、pytest 骨架
- [ ] M2：POC（DeepSeek 调用 + pgvector 检索 + LangGraph 工作流 + 成本记录）
- [ ] API 路由开发
- [ ] 5 个 Agent 实现
- [ ] 测试补齐（单测 ≥ 80% / 集成 ≥ 60%）
