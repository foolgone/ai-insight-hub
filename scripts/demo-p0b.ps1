# P0-B demo stack launcher (Windows PowerShell)
# 用途：在独立终端中稳定运行 API + Celery worker + Vite，供人类测试使用。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\demo-p0b.ps1
# 说明：本脚本只负责环境进程；测试者仍然只用浏览器，不执行本脚本。

param(
    [string]$DatabaseUrl = "postgresql://aiinsight:dev_password@192.168.150.100:5433/aiinsight_demo",
    [string]$RedisUrl = "redis://192.168.150.100:6379/6",
    [string]$CeleryBrokerUrl = "redis://192.168.150.100:6379/7",
    [string]$CeleryResultBackend = "redis://192.168.150.100:6379/8",
    [string]$StorageDir = ".storage/demo-p0b"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend "venv\Scripts\python.exe"
$celery = Join-Path $backend "venv\Scripts\celery.exe"
$storage = Join-Path $backend $StorageDir

foreach ($port in @(8000, 5173)) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        throw "端口 $port 已被占用（PID $($listener.OwningProcess)）。先停止旧进程，避免重复启动。"
    }
}

if (-not (Test-Path $python)) { throw "找不到 backend/venv；请先按仓库说明创建虚拟环境。" }
if (-not (Test-Path $celery)) { throw "找不到 celery.exe；请检查 backend/venv。" }
if (-not (Test-Path $storage)) { New-Item -ItemType Directory -Force -Path $storage | Out-Null }

$env:DATABASE_URL = $DatabaseUrl
$env:REDIS_URL = $RedisUrl
$env:CELERY_BROKER_URL = $CeleryBrokerUrl
$env:CELERY_RESULT_BACKEND = $CeleryResultBackend
$env:STORAGE_BACKEND = "local"
$env:STORAGE_LOCAL_DIR = $storage
$env:RAG_ADAPTER = "mock"
$env:TENANT_ENFORCEMENT_ENABLED = "false"
$env:RATE_LIMIT_ENABLED = "true"
$env:ALLOW_SERVER_KEY_FALLBACK = "true"
# 离线 embedding：API 和 worker 都继承；避免访问 huggingface.co 超时
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
if (-not $env:EMBEDDING_CACHE_DIR) {
    $hfHome = $env:HF_HOME
    if (-not $hfHome) { $hfHome = Join-Path $env:USERPROFILE ".cache\huggingface" }
    $hfHub = Join-Path $hfHome "hub"
    if (Test-Path $hfHub) { $env:EMBEDDING_CACHE_DIR = $hfHub }
}
if (-not $env:DEEPSEEK_BASE_URL) { $env:DEEPSEEK_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1" }
if (-not $env:DEEPSEEK_API_KEY) { $env:DEEPSEEK_API_KEY = $env:DASHSCOPE_API_KEY }
if (-not $env:DEFAULT_LLM_MODEL) { $env:DEFAULT_LLM_MODEL = "qwen-flash" }

Write-Host "预热 embedding（离线缓存）..." -ForegroundColor Yellow
Push-Location $backend
try {
    $warmOutput = & $python -c "import asyncio; from app.services.embedding_service import encode_text; print(len(asyncio.run(encode_text('prewarm'))))"
    if ($LASTEXITCODE -ne 0 -or -not $warmOutput) {
        throw "Embedding 预热失败：检查 HF_HOME/模型缓存，或先在线预热一次。"
    }
} finally {
    Pop-Location
}
Write-Host "Embedding 预热通过（维度 $warmOutput）" -ForegroundColor Green

Write-Host "启动 P0-B demo（保持本窗口打开；Ctrl+C 停止全部）" -ForegroundColor Cyan
$api = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000" `
    -WorkingDirectory $backend -PassThru -NoNewWindow
$worker = Start-Process -FilePath $celery -ArgumentList "-A", "app.core.celery.celery_app", "worker", "-l", "info", "-P", "solo", "-Q", "default,clean" `
    -WorkingDirectory $backend -PassThru -NoNewWindow
$web = Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173" `
    -WorkingDirectory $frontend -PassThru -NoNewWindow

function Wait-Endpoint([string]$Url, [int]$TimeoutSeconds = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) { return }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "等待 $Url 超时；检查端口/日志后重试。"
}

try {
    Wait-Endpoint "http://127.0.0.1:8000/health"
    Wait-Endpoint "http://127.0.0.1:5173"
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 5
    if (-not $health.embedding.ready) {
        throw "embedding ready=false：模型缓存不可用，停止测试，不要让人等待网络超时。"
    }
    Write-Host "✅ API 8000 / Vite 5173 已就绪（限流默认开启，embedding ready=true）" -ForegroundColor Green
    Write-Host "   人类测试者：http://127.0.0.1:5173"
    Write-Host "   本窗口保持打开；若任一进程退出，脚本会停止以便记录重启。" -ForegroundColor DarkGray
    Wait-Process -Id $api.Id, $worker.Id, $web.Id
}
finally {
    Write-Host "正在停止 P0-B demo..." -ForegroundColor Yellow
    foreach ($process in @($api, $worker, $web)) {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
