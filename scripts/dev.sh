#!/bin/bash

# AI Insight Hub 开发环境启动脚本

echo "🚀 启动 AI Insight Hub 开发环境..."
echo ""

# 检查是否在项目根目录
if [ ! -f "README.md" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本"
    exit 1
fi

# 启动后端
echo "📦 启动后端服务..."
cd backend
if [ ! -d "venv" ]; then
    echo "创建 Python 虚拟环境..."
    python -m venv venv
fi

source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows (需手动运行)

echo "安装 Python 依赖..."
pip install -r requirements.txt

echo "启动后端 API (端口 8000)..."
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

cd ..

# 启动前端
echo ""
echo "⚛️  启动前端服务..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "安装 Node 依赖..."
    npm install
fi

echo "启动前端开发服务器 (端口 5173)..."
npm run dev &
FRONTEND_PID=$!

cd ..

echo ""
echo "✅ 开发环境已启动！"
echo ""
echo "访问地址："
echo "  前端：http://localhost:5173"
echo "  后端：http://localhost:8000"
echo "  API 文档：http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待用户中断
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
