#!/bin/bash

# AI Insight Hub - 开发环境启动脚本

echo "🚀 启动 AI Insight Hub 开发环境..."
echo ""

# 检查 Docker 服务是否运行
if ! docker ps >/dev/null 2>&1; then
    echo "❌ Docker 未运行，请先启动 Docker"
    exit 1
fi

# 检查 Docker Compose 服务
echo "🐳 检查 Docker 服务..."
if ! docker-compose ps | grep -q "Up"; then
    echo "⚠️  Docker 服务未启动，正在启动..."
    docker-compose up -d
    echo "⏳ 等待服务就绪..."
    sleep 5
fi

# 使用 tmux 或并行启动（如果安装了 tmux）
if command -v tmux &> /dev/null; then
    echo "🔀 使用 tmux 启动多个服务..."

    # 创建新会话
    tmux new-session -d -s aiinsight

    # 后端窗口
    tmux rename-window -t aiinsight:0 'backend'
    tmux send-keys -t aiinsight:0 'cd backend && source venv/bin/activate && uvicorn app.main:app --reload' C-m

    # 前端窗口
    tmux new-window -t aiinsight:1 -n 'frontend'
    tmux send-keys -t aiinsight:1 'cd frontend && npm run dev' C-m

    echo "✅ 服务已在 tmux 中启动"
    echo ""
    echo "📚 使用方式："
    echo "  - 连接到会话：tmux attach -t aiinsight"
    echo "  - 切换窗口：Ctrl+B 然后按 0(后端) 或 1(前端)"
    echo "  - 退出会话：Ctrl+B 然后按 D"
    echo "  - 停止所有服务：tmux kill-session -t aiinsight"
    echo ""
    echo "🌐 访问："
    echo "  - 前端：http://localhost:5173"
    echo "  - 后端 API：http://localhost:8000/docs"

    # 自动连接到会话
    tmux attach -t aiinsight
else
    echo "⚠️  tmux 未安装，请手动启动服务："
    echo ""
    echo "终端 1 - 后端："
    echo "  cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
    echo ""
    echo "终端 2 - 前端："
    echo "  cd frontend && npm run dev"
fi
