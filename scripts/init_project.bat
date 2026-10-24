@echo off
echo ============================================
echo  AI Insight Hub - 项目初始化 (Windows)
echo ============================================
echo.

REM 检查必要工具
echo 📋 检查必要工具...
where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Docker 未安装，请先安装 Docker Desktop
    pause
    exit /b 1
)

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Python 未安装
    pause
    exit /b 1
)

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Node.js 未安装
    pause
    exit /b 1
)

echo ✅ 工具检查通过
echo.

REM 1. 启动 Docker 服务
echo 🐳 启动 Docker 服务...
docker-compose up -d
echo ⏳ 等待服务启动...
timeout /t 10 /nobreak >nul
echo ✅ Docker 服务已启动
echo.

REM 2. 后端设置
echo 🐍 设置后端...
cd backend

REM 创建虚拟环境
if not exist "venv" (
    echo 📦 创建 Python 虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
echo 📦 安装后端依赖...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

REM 复制环境变量
if not exist ".env" (
    echo 📝 创建后端 .env 文件...
    copy .env.example .env
    echo ⚠️  请编辑 backend\.env 填入必要的配置（如 ANTHROPIC_API_KEY）
)

REM 初始化数据库
echo 🗄️  初始化数据库...
alembic upgrade head

echo ✅ 后端设置完成
cd ..
echo.

REM 3. 前端设置
echo ⚛️  设置前端...
cd frontend

REM 安装依赖
echo 📦 安装前端依赖...
call npm install

REM 复制环境变量
if not exist ".env" (
    echo 📝 创建前端 .env 文件...
    copy .env.example .env
)

echo ✅ 前端设置完成
cd ..
echo.

REM 4. 完成
echo ============================================
echo 🎉 项目初始化完成！
echo ============================================
echo.
echo 📚 下一步：
echo   1. 编辑 backend\.env，填入 ANTHROPIC_API_KEY
echo   2. 启动后端：cd backend ^&^& venv\Scripts\activate ^&^& uvicorn app.main:app --reload
echo   3. 启动前端：cd frontend ^&^& npm run dev
echo   4. 访问：http://localhost:5173
echo.
echo 📖 API 文档：http://localhost:8000/docs
echo.
pause
