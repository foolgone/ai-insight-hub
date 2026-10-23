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
    Write-Host "📦 创建 Python 虚拟环境..." -ForegroundColor Yellow
    python -m venv (Join-Path $backend "venv")
    & $python -m pip install -r (Join-Path $backend "requirements.txt")
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
