# AI Insight Hub - Backend

## 快速开始

### 环境要求

- Python 3.11+
- PostgreSQL 14+
- Redis 7+

### 安装

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 配置

创建 `.env` 文件：

```bash
# 数据库
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_insight_hub

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=your-secret-key-change-in-production

# AI API Keys (可选)
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
```

### 运行

```bash
# 开发模式（热重载）
uvicorn app.main:app --reload --port 8000

# 或者直接运行
python app/main.py
```

访问：
- API: http://localhost:8000
- 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

## 项目结构

```
backend/
├── app/
│   ├── main.py           # 应用入口
│   ├── api/              # API 路由
│   ├── agents/           # AI Agents
│   ├── services/         # 业务服务
│   ├── models/           # 数据模型
│   └── core/             # 核心配置
│       └── config.py     # 配置文件
├── tests/                # 测试
├── requirements.txt      # 依赖
└── README.md            # 本文件
```

## 下一步

- [ ] 数据库初始化
- [ ] API 路由开发
- [ ] AI Agent 集成
- [ ] 测试编写
