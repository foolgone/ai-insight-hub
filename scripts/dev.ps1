# AI Insight Hub 开发环境启动脚本（Windows PowerShell）
# 用法：在项目根目录执行  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "🚀 启动 AI Insight Hub 开发环境..." -ForegroundColor Cyan

# ---------- 后端 ----------
$backend = Join-Path $root "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "📦 创建 Python 虚拟环境并安装依赖（含开发依赖）..." -ForegroundColor Yellow
    python -m venv (Join-Path $backend "venv")
    & $python -m pip install -r (Join-Path $backend "requirements.txt") -r (Join-Path $backend "requirements-dev.txt")
}

# ---------- 环境变量 ----------
if (-not (Test-Path (Join-Path $backend ".env"))) {
    Copy-Item (Join-Path $backend ".env.example") (Join-Path $backend ".env")
    Write-Host "⚠️  已从 .env.example 创建 backend\.env，请填入 DEEPSEEK_API_KEY" -ForegroundColor Yellow
}
if (-not (Test-Path (Join-Path $root "frontend\.env"))) {
    Copy-Item (Join-Path $root "frontend\.env.example") (Join-Path $root "frontend\.env")
}

# ---------- 依赖服务检查（数据库/缓存默认在本地 VM 192.168.150.100）----------
$vmHost = "192.168.150.100"
$dbOk = Test-NetConnection -ComputerName $vmHost -Port 5433 -InformationLevel Quiet -WarningAction SilentlyContinue
$redisOk = Test-NetConnection -ComputerName $vmHost -Port 6379 -InformationLevel Quiet -WarningAction SilentlyContinue

if ($dbOk -and $redisOk) {
    Write-Host "🐳 依赖服务正常：VM $vmHost 的 PostgreSQL(5433) + Redis(6379)" -ForegroundColor DarkGray
} else {
    Write-Host "⚠️  连不上 VM $vmHost 的 PostgreSQL(5433)/Redis(6379)" -ForegroundColor Yellow
    Write-Host "   1) 先启动虚拟机（VMware Workstation）" -ForegroundColor Yellow
    Write-Host "   2) 在 VM 上执行： cd /root/ai-insight-hub-infra && docker compose up -d" -ForegroundColor Yellow
    Write-Host "   备选：改回本机 docker compose up -d（端口 5432/6379），并调整 backend\.env" -ForegroundColor DarkGray
    Write-Host "   详见 docs\00-本地VM数据库接入.md" -ForegroundColor DarkGray
}

Write-Host "🐍 启动后端 API (端口 8000)..." -ForegroundColor Yellow
$backendProc = Start-Process -FilePath $python `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000" `
    -WorkingDirectory $backend -PassThru

# ---------- 前端 ----------
$frontend = Join-Path $root "frontend"
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "📦 安装 Node 依赖..." -ForegroundColor Yellow
    npm install --prefix $frontend
}

Write-Host "⚛️  启动前端开发服务器 (端口 5173)..." -ForegroundColor Yellow
$frontendProc = Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" `
    -WorkingDirectory $frontend -PassThru

Write-Host ""
Write-Host "✅ 开发环境已启动！" -ForegroundColor Green
Write-Host "  前端：    http://localhost:5173"
Write-Host "  后端：    http://localhost:8000"
Write-Host "  API 文档：http://localhost:8000/docs"
Write-Host ""
Write-Host "按 Ctrl+C 停止所有服务" -ForegroundColor DarkGray

try {
    Wait-Process -Id $backendProc.Id, $frontendProc.Id
}
finally {
    Write-Host "🛑 正在停止服务..." -ForegroundColor Yellow
    foreach ($p in @($backendProc, $frontendProc)) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
}
