#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PORT="${1:-${APP_PORT:-8080}}"

if ! command -v docker >/dev/null 2>&1; then
    echo "未找到 docker 命令，请先安装 Docker。" >&2
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "未找到 curl 命令，无法执行健康检查。" >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "未找到 Docker Compose v2，请升级 Docker。" >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Docker 引擎未运行，请先启动 Docker。" >&2
    exit 1
fi

if [ ! -f backend/.env ]; then
    cp backend/.env.example backend/.env
    echo "已从 backend/.env.example 创建 backend/.env。"
    echo "模型配置可在启动后从界面左下角的 Model settings 填写。"
fi

export APP_PORT="$PORT"

echo "正在构建并启动 AI Chat Room（端口 $PORT）..."
docker compose up -d --build

echo "等待服务就绪..."
health=""
for _ in $(seq 1 60); do
    if health="$(curl -fsS "http://127.0.0.1:${PORT}/api/health" 2>/dev/null)"; then
        break
    fi
    health=""
    sleep 2
done

if [ -z "$health" ]; then
    echo "等待服务超时。以下是最近日志：" >&2
    docker compose ps || true
    docker compose logs --tail=100 backend frontend || true
    exit 1
fi

echo
echo "AI Chat Room 已启动"
echo "界面:     http://localhost:${PORT}"
echo "API 文档: http://localhost:${PORT}/docs"
echo "查看日志: docker compose logs -f"
echo "停止服务: docker compose down"

if ! printf '%s' "$health" | grep -Eq '"llm_configured"[[:space:]]*:[[:space:]]*true'; then
    echo
    echo "模型尚未配置，Bot 任务会失败。"
    echo "  打开界面左下角的 Model settings，填写 API Key、Base URL 和模型后保存。"
    echo "  保存后立即生效，无需重启。"
fi
