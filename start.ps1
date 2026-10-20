[CmdletBinding()]
param(
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

if ($Port -le 0) {
    if ($env:APP_PORT) {
        $Port = [int]$env:APP_PORT
    } else {
        $Port = 8080
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "未找到 docker 命令，请先安装 Docker Desktop。" -ForegroundColor Red
    exit 1
}

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "未找到 Docker Compose v2，请升级 Docker Desktop。" -ForegroundColor Red
    exit 1
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker 引擎未运行，请先启动 Docker Desktop。" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "backend/.env")) {
    Copy-Item "backend/.env.example" "backend/.env"
    Write-Host "已从 backend/.env.example 创建 backend/.env。" -ForegroundColor Yellow
    Write-Host "模型配置可在启动后从界面左下角的 Model settings 填写。" -ForegroundColor Yellow
}

$env:APP_PORT = "$Port"

Write-Host "正在构建并启动 AI Chat Room（端口 $Port）..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "启动失败，请检查上方 Docker 输出。" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "等待服务就绪..." -ForegroundColor Cyan
$health = $null
for ($i = 0; $i -lt 60; $i++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        if ($health.status -eq "ok") {
            break
        }
    } catch {
        # 服务尚未就绪，继续等待。
    }
    Start-Sleep -Seconds 2
}

if ($null -eq $health -or $health.status -ne "ok") {
    Write-Host "等待服务超时。以下是最近日志：" -ForegroundColor Red
    docker compose ps
    docker compose logs --tail=100 backend frontend
    exit 1
}

Write-Host ""
Write-Host "AI Chat Room 已启动" -ForegroundColor Green
Write-Host "界面:     http://localhost:$Port"
Write-Host "API 文档: http://localhost:$Port/docs"
Write-Host "查看日志: docker compose logs -f"
Write-Host "停止服务: docker compose down"

if (-not $health.llm_configured) {
    Write-Host ""
    Write-Host "模型尚未配置，Bot 任务会失败。" -ForegroundColor Yellow
    Write-Host "  打开界面左下角的 Model settings，填写 API Key、Base URL 和模型后保存。"
    Write-Host "  保存后立即生效，无需重启。"
}
