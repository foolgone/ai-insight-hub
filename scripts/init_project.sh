#!/bin/bash
set -e

echo "🚀 初始化 AI Insight Hub 项目..."
echo ""

# 检查必要工具
echo "📋 检查必要工具..."
command -v docker >/dev/null 2>&1 || { echo "❌ Docker 未安装，请先安装 Docker"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python3 未安装"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js 未安装"; exit 1; }
echo "✅ 工具检查通过"
echo ""

# 1. 启动 Docker 服务
echo "🐳 启动 Docker 服务..."
docker-compose up -d
echo "⏳ 等待服务启动..."
sleep 10
echo "✅ Docker 服务已启动"
echo ""

# 2. 后端设置
echo "🐍 设置后端..."
cd backend

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建 Python 虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📦 安装后端依赖..."
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 复制环境变量
if [ ! -f ".env" ]; then
    echo "📝 创建后端 .env 文件..."
    cp .env.example .env
    echo "⚠️  请编辑 backend/.env 填入必要的配置（如 ANTHROPIC_API_KEY）"
fi

# 初始化数据库
echo "🗄️  初始化数据库..."
alembic upgrade head

echo "✅ 后端设置完成"
cd ..
echo ""

# 3. 前端设置
echo "⚛️  设置前端..."
cd frontend

# 安装依赖
echo "📦 安装前端依赖..."
npm install

# 复制环境变量
if [ ! -f ".env" ]; then
    echo "📝 创建前端 .env 文件..."
    cp .env.example .env
fi

echo "✅ 前端设置完成"
cd ..
echo ""

# 4. 完成
echo "🎉 项目初始化完成！"
echo ""
echo "📚 下一步："
echo "  1. 编辑 backend/.env，填入 ANTHROPIC_API_KEY"
echo "  2. 启动后端：cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "  3. 启动前端：cd frontend && npm run dev"
echo "  4. 访问：http://localhost:5173"
echo ""
echo "📖 文档：http://localhost:8000/docs"
