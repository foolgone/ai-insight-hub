# AI Insight Hub

> AI 驱动的智能对话数据分析平台

## 📖 项目概述

AI Insight Hub 是一个专为 AI 客服/对话系统设计的数据中台，提供数据清洗、质量评估、知识库构建和洞察分析能力。

### 核心价值

- 🔧 **数据中台**：接入、清洗、标准化第三方对话数据
- 🤖 **AI 质量评估**：评估 AI 客服回答的准确性、完整性、合规性
- 📚 **知识库构建**：自动提取 FAQ、发现知识盲区、构建知识图谱
- 📊 **客户洞察**：分析客户诉求、发现趋势、生成数据报告

### 核心场景

1. **数据清洗与标准化**：将第三方系统导出的非结构化数据转换为标准 JSON
2. **AI 客服质量管理**：持续评估 AI 客服表现，发现问题并优化
3. **知识库智能构建**：从对话中自动提取 FAQ 和知识点
4. **数据驱动决策**：生成洞察报告，支持产品和运营决策

---

## 🎯 项目定位

**不是**：人工客服质检工具  
**而是**：AI 客服 + 数据中台 + 知识管理平台

**目标用户**：
- AI 产品经理
- 客服运营团队
- 数据分析师
- AI 训练工程师

---

## 🏗️ 技术架构

### 技术栈

**前端**
- React 18 + Vite 5
- TailwindCSS 3
- Recharts（数据可视化）
- Axios（HTTP 客户端）

**后端**
- Python 3.11+
- FastAPI（Web 框架）
- LangChain/LangGraph（AI Agent 框架）
- SQLAlchemy（ORM）
- Alembic（数据库迁移）

**数据存储**
- PostgreSQL（主数据库）
- Redis（缓存）
- ChromaDB / Pinecone（向量数据库）

**AI 模型**
- OpenAI GPT-4
- Claude
- DeepSeek

---

## 📁 项目结构

```
ai-insight-hub/
├── docs/                          # 📚 文档
│   ├── 01-requirements/          # 需求文档
│   ├── 02-design/                # 设计文档
│   ├── 03-architecture/          # 架构文档
│   ├── 04-development/           # 开发文档
│   └── 05-operations/            # 运维文档
│
├── backend/                       # 🐍 后端（Python）
│   ├── app/
│   │   ├── api/                  # API 路由
│   │   ├── agents/               # AI Agents
│   │   ├── services/             # 业务服务
│   │   ├── models/               # 数据模型
│   │   └── core/                 # 核心配置
│   ├── tests/                    # 测试
│   └── requirements.txt
│
├── frontend/                      # ⚛️ 前端（React）
│   ├── src/
│   │   ├── components/           # React 组件
│   │   ├── pages/                # 页面
│   │   ├── lib/                  # 工具库
│   │   └── api/                  # API 调用
│   ├── public/
│   └── package.json
│
├── shared/                        # 🔗 共享资源
│   ├── schemas/                  # 数据模型定义
│   └── constants/                # 常量定义
│
└── scripts/                       # 🛠️ 工具脚本
    ├── setup.sh                  # 环境搭建
    └── dev.sh                    # 开发启动
```

---

## 🚀 快速开始

### 环境要求

- Node.js 18+
- Python 3.11+
- PostgreSQL 14+
- Redis 7+

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd ai-insight-hub

# 安装后端依赖
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 安装前端依赖
cd ../frontend
npm install
```

### 开发

```bash
# 启动后端（终端 1）
cd backend
uvicorn app.main:app --reload --port 8000

# 启动前端（终端 2）
cd frontend
npm run dev
```

Windows 也可一键启动（自动创建虚拟环境、安装依赖）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
```

访问：
- 前端：http://localhost:5173
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs

---

## 📊 项目状态

**当前阶段**：🚧 需求收集与架构设计

**进度**：
- [x] 项目初始化
- [ ] 需求分析
- [ ] 产品设计
- [ ] 技术架构设计
- [ ] 后端开发
- [ ] 前端开发
- [ ] 测试
- [ ] 部署

---

## 📚 文档

- [产品概述](docs/01-requirements/01-产品概述.md)
- [用户调研](docs/01-requirements/02-用户调研.md)
- [技术架构](docs/03-architecture/01-系统架构.md)
- [API 文档](docs/03-architecture/03-API设计.md)
- [开发指南](docs/04-development/01-开发规范.md)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License

---

## 📞 联系方式

- 项目地址：[GitHub]()
- 问题反馈：[Issues]()

---

**最后更新**：2026年10月22日
