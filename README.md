# AI Insight Hub

> AI 客服数据分析平台 - 通过 AI Agent 自动清洗、评估和分析客服对话数据

**项目状态**：开发准备阶段  
**文档版本**：v1.0  
**创建日期**：2026年10月23日

---

## 📖 项目简介

AI Insight Hub 是一个智能数据中台，专门为 AI 客服/对话系统提供：

- 🔧 **数据清洗**：自动将非结构化对话数据标准化
- 📊 **质量评估**：5 维度评估 AI 回复质量（准确性、完整性、幻觉检测等）
- 📚 **知识提取**：自动构建 FAQ 知识库，发现知识盲区
- 💡 **洞察分析**：客户诉求分析、情感趋势、痛点识别
- 📄 **报告生成**：自动生成专业分析报告

---

## 🛠️ 技术栈

### 后端
- **Python 3.11+** | FastAPI | SQLAlchemy 2.0
- **LangChain + LangGraph** | Claude 5.5 (Sonnet/Opus/Haiku)

### 前端
- **React 18** | Vite 5 | TailwindCSS 3
- **React Query** (服务端状态) | **Zustand** (客户端状态)

### 数据库
- **PostgreSQL 14+** (pgvector) | **Redis 7+** | **MinIO**

### DevOps
- **Docker** | **Docker Compose** | **GitHub Actions**

---

## 🚀 快速开始

### 前置要求

- **Docker Desktop** 或 **Docker + Docker Compose**
- **Python 3.11+**
- **Node.js 20+**
- **Git**

### 安装步骤

#### 1. 克隆仓库

```bash
git clone https://github.com/your-org/ai-insight-hub.git
cd ai-insight-hub
```

#### 2. 配置环境变量

```bash
# 后端
cd backend
cp .env.example .env
# 编辑 .env，填入必要的配置（API Key 等）

# 前端
cd ../frontend
cp .env.example .env
```

#### 3. 启动基础服务（Docker）

```bash
# 在项目根目录
docker-compose up -d

# 检查服务状态
docker-compose ps
```

这将启动：
- PostgreSQL (with pgvector) - `localhost:5432`
- Redis - `localhost:6379`
- MinIO - `localhost:9000` (控制台: `localhost:9001`)

#### 4. 初始化数据库

```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate

# 运行数据库迁移
alembic upgrade head
```

#### 5. 启动后端

```bash
# 在 backend 目录
uvicorn app.main:app --reload --port 8000
```

访问：
- API 文档：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc

#### 6. 启动前端

```bash
# 在 frontend 目录
npm install
npm run dev
```

访问：http://localhost:5173

---

## 📁 项目结构

```
ai-insight-hub/
├── README.md                    # 本文件
├── docker-compose.yml           # Docker 服务编排
├── .gitignore
│
├── docs/                        # 📚 文档（20+ 份完整文档）
│   ├── 00-AI应用开发基调.md
│   ├── 01-requirements/
│   ├── 02-design/
│   ├── 03-architecture/
│   └── 04-development/
│
├── backend/                     # 🐍 Python 后端
│   ├── .env.example
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py             # FastAPI 入口
│   │   ├── core/               # 核心配置
│   │   ├── api/                # API 路由
│   │   ├── models/             # 数据库模型
│   │   ├── schemas/            # Pydantic Schemas
│   │   ├── agents/             # AI Agents
│   │   ├── prompts/            # Prompt 资产库
│   │   ├── services/           # 业务服务
│   │   └── utils/              # 工具函数
│   ├── migrations/             # 数据库迁移
│   └── tests/                  # 测试
│
├── frontend/                    # ⚛️ React 前端
│   ├── .env.example
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── components/         # 通用组件
│   │   ├── pages/              # 页面
│   │   ├── features/           # 功能模块
│   │   ├── stores/             # Zustand stores
│   │   ├── lib/                # 工具库
│   │   └── hooks/              # 自定义 Hooks
│   └── tests/
│
└── scripts/                     # 🔧 工具脚本
    ├── init_project.sh         # 项目初始化
    ├── dev.sh                  # 启动开发环境
    └── seed_data.py            # 填充测试数据
```

---

## 🧪 开发

### 后端开发

```bash
# 创建虚拟环境
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 代码格式化
black app/
flake8 app/

# 类型检查
mypy app/

# 运行测试
pytest tests/ -v --cov=app

# 启动开发服务器
uvicorn app.main:app --reload
```

---

### 前端开发

```bash
cd frontend

# 安装依赖
npm install

# 代码检查
npm run lint

# 运行测试
npm run test

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

---

## 🧪 测试

### 运行所有测试

```bash
# 后端
cd backend
pytest tests/ -v --cov=app --cov-report=html

# 前端
cd frontend
npm run test:coverage
```

### 测试覆盖率目标

- 单元测试覆盖率：**> 80%**
- Prompt 测试：每个 Agent **50+ 用例**

---

## 📊 成本预算

### 中型企业（10万条/月）

| 服务 | 月成本 |
|------|--------|
| Claude API | $849 |
| 基础设施 | $380 |
| LangSmith | $39 |
| **总计** | **$1,268** |

**单条处理成本**：~$0.0127

详见：`docs/04-development/03-成本管理.md`

---

## 🎯 开发里程碑

| 里程碑 | 时间 | 状态 |
|--------|------|------|
| M1: 环境就绪 | Week 1 | 🔄 进行中 |
| M2: POC 完成 | Week 2 | ⏸️  待开始 |
| M3: 基础架构 | Week 4 | ⏸️  待开始 |
| M4: 数据清洗 | Week 6 | ⏸️  待开始 |
| M5: 质量评估 | Week 8 | ⏸️  待开始 |
| M6: 知识提取 | Week 10 | ⏸️  待开始 |
| M7: MVP 完成 | Week 12 | ⏸️  待开始 |
| M8: 上线就绪 | Week 14 | ⏸️  待开始 |

详见：`docs/04-development/04-开发方案.md`

---

## 📚 文档

完整文档请查看 `docs/` 目录：

- **需求文档**：产品概述、用户调研
- **设计文档**：Prompt 工程规范、版本管理
- **架构文档**：系统架构、Agent 设计、数据库设计、API 设计
- **开发文档**：开发规范、技术栈、成本管理、开发方案

---

## 🤝 贡献指南

### 开发流程

1. 从 `develop` 分支创建功能分支
2. 遵循代码规范（见 `docs/04-development/01-开发规范.md`）
3. 编写测试（覆盖率 > 80%）
4. 提交前运行检查：
   ```bash
   # 后端
   black app/ && flake8 app/ && pytest tests/
   
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

- [LangChain](https://github.com/langchain-ai/langchain) - AI 应用框架
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Web 框架
- [React](https://react.dev/) - UI 框架
- [Anthropic Claude](https://www.anthropic.com/) - 强大的 LLM

---

**准备开始开发了吗？** 🚀

查看 [开发方案](./docs/04-development/04-开发方案.md) 了解详细的开发计划！
