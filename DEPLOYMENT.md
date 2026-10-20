# 部署指南

本文面向单台 Linux 服务器的生产/预发布部署，说明从服务器准备、配置、启动、TLS、备份、升级到回滚的完整流程。

项目当前的运行约束决定了部署方式：**单进程、单 Writer、SQLite、无认证**。在开始之前请先阅读[部署前必须知道](#部署前必须知道)。

## 目录

- [部署前必须知道](#部署前必须知道)
- [快速路径](#快速路径)
- [架构与端口](#架构与端口)
- [选择部署方式](#选择部署方式)
- [服务器准备](#服务器准备)
- [获取代码](#获取代码)
- [配置环境变量](#配置环境变量)
- [Docker Compose 生产部署](#docker-compose-生产部署)
- [TLS 与反向代理](#tls-与反向代理)
- [首次启动验证](#首次启动验证)
- [数据备份与恢复](#数据备份与恢复)
- [升级与回滚](#升级与回滚)
- [非 Docker 部署](#非-docker-部署)
- [监控与日常运维](#监控与日常运维)
- [安全加固](#安全加固)
- [故障排查](#故障排查)
- [上线检查清单](#上线检查清单)
- [已知限制](#已知限制)

## 部署前必须知道

1. **没有应用层认证。** 所有请求都以预设用户身份执行。公网部署必须在反向代理层加 Basic Auth、接入 VPN，或用防火墙限制来源 IP。不要直接把 8080 端口暴露到公网。
2. **只能运行一个后端实例。** 调度器和 WebSocket 广播在进程内存中，SQLite 也不适合多 Writer。不要扩缩 `backend` 副本，不要使用多 Worker uvicorn。
3. **没有数据库迁移工具。** Schema 通过 `create_all` 创建；`create_all` 不会修改已有表。升级前必须备份；涉及 Schema 变更的版本需要手工迁移，或清库重建。
4. **生产环境使用 `docker-compose.prod.yml`。** 基础 Compose 把前端端口绑定到 `0.0.0.0`，仅适合本地；生产覆盖文件会绑定到 `127.0.0.1`，由反向代理对外提供服务。
5. **没有 Token 流式输出、自动重试、限流或费用预算。** 这些需要在反向代理或外部系统中补齐。
6. **数据库包含完整对话、工具参数和工具结果。** 可能包含敏感数据，备份也要按敏感数据管理。

## 快速路径

已有 Linux 服务器和 Docker 时，最短流程如下。每一步的细节见后续章节。

```bash
# 1. 代码
sudo mkdir -p /opt/ai_chat_room
sudo chown deploy:deploy /opt/ai_chat_room
git clone <repo-url> /opt/ai_chat_room
cd /opt/ai_chat_room
git checkout <release-tag>

# 2. 配置
cp backend/.env.example backend/.env
chmod 600 backend/.env
# 编辑 backend/.env：ENVIRONMENT=production、LLM_*、CORS_ORIGINS

# 3. 生产 Compose（仅绑定 127.0.0.1:8080）
export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8080/api/health

# 4. 反向代理与 TLS（Caddy 示例见下文）
# 5. 立即做一次数据库备份
# 6. 配置外部健康检查和日志轮转
```

不要跳过：**访问控制、TLS、首次备份、恢复演练**。

## 架构与端口

```text
Internet
   │  443/TLS
   ▼
Caddy / Nginx（宿主机）
   │  http://127.0.0.1:8080
   ▼
frontend 容器（nginx）
   │  /api、/ws、/docs
   ▼
backend 容器（uvicorn :8000，仅 Compose 内网）
   │
   ▼
命名卷 backend-data → /app/data/app.db
```

对外只需要开放：

| 端口 | 用途 |
|---|---|
| `22/tcp` | SSH（建议限制来源 IP） |
| `80/tcp` | HTTP，仅用于跳转 HTTPS / ACME 验证 |
| `443/tcp` | HTTPS |

不要对外开放 `8080` 或 `8000`。后端在 Compose 中本来就只 `expose`，没有发布到宿主机。

## 选择部署方式

| 方式 | 适用场景 | 说明 |
|---|---|---|
| **Docker Compose（推荐）** | 单台 Linux 服务器、预发布、内部工具 | 本文主线，包含镜像构建、健康检查、持久化卷 |
| 裸机部署 | 不允许 Docker，或已有 systemd/nginx 管理体系 | 需要自行管理 Python、venv、Node 构建和静态文件 |
| Kubernetes / 多副本 | 当前版本不支持 | 内存调度器、WebSocket 和 SQLite 都不支持水平扩展 |
| Serverless | 当前版本不支持 | WebSocket、后台任务和本地 SQLite 不匹配 |

本文假设：

- 域名：`chat.example.com`（替换成你的域名）
- 部署目录：`/opt/ai_chat_room`
- 运行用户：`deploy`
- 反向代理：Caddy（推荐）或 Nginx
- 服务器：Ubuntu 22.04/24.04，1 vCPU / 1 GB 内存起步，构建时建议 2 GB

## 服务器准备

### 1. 安装 Docker

按 Docker 官方文档安装 Docker Engine 和 Compose 插件：

- <https://docs.docker.com/engine/install/>
- 安装后确认 Compose 版本不低于 v2.24（生产覆盖文件使用 `!override`）：

```bash
docker --version
docker compose version
sudo systemctl enable --now docker
```

如果使用 Docker Desktop 以外的 Linux 环境，把部署用户加入 `docker` 组（重新登录后生效）：

```bash
sudo usermod -aG docker deploy
```

### 2. 创建部署用户和目录

```bash
sudo useradd --create-home --shell /bin/bash deploy
sudo mkdir -p /opt/ai_chat_room
sudo chown deploy:deploy /opt/ai_chat_room
```

### 3. 防火墙

只开放 SSH、HTTP、HTTPS。Docker 发布的端口可能绕过部分 UFW 规则，因此生产环境还必须使用本文的 `docker-compose.prod.yml` 把前端绑定到本机回环地址。

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

### 4. 时间同步

```bash
sudo timedatectl set-ntp true
timedatectl
```

任务、消息和审计记录都使用 Unix 毫秒时间戳，服务器时间必须准确。

## 获取代码

```bash
sudo -iu deploy
cd /opt
git clone <repo-url> ai_chat_room
cd ai_chat_room
git fetch --tags
git checkout <release-tag>
```

生产环境固定到 release tag 或 commit，不要直接跟踪浮动的 `main`。

如果没有 Git，可以上传发布包并解压到 `/opt/ai_chat_room`，但要保证目录权限属于 `deploy`。

## 配置环境变量

### 1. 创建环境文件

```bash
cd /opt/ai_chat_room
cp backend/.env.example backend/.env
chmod 600 backend/.env
```

### 2. 填写生产配置

```dotenv
APP_NAME=AI Chat Room
APP_VERSION=0.1.0
ENVIRONMENT=production

LLM_PROVIDER=openai
LLM_API_KEY=<production-key>
LLM_BASE_URL=https://api.example.com/v1
LLM_MODEL=<tool-calling-model>

CORS_ORIGINS=["https://chat.example.com"]

DEFAULT_USER_NAME=demo
DEFAULT_USER_DISPLAY_NAME=Demo User

AGENT_MAX_STEPS=8
AGENT_MAX_CONTEXT_CHARS=16000
AGENT_MAX_DEPTH=3
AGENT_MAX_TASKS_PER_ROOT=24
AGENT_REPLY_MAX_CHARS=16000
TOOL_TIMEOUT_SECONDS=20
TOOL_RESULT_MAX_CHARS=8000
FETCH_MAX_BYTES=100000
ROOM_HISTORY_LIMIT=100
```

关键说明：

- `LLM_MODEL` 必须支持 Chat Completions 和工具调用，否则 Bot 任务会失败。
- 项目使用 `LLM_*` 而不是 `OPENAI_*`，避免宿主机的 `OPENAI_API_KEY` 覆盖项目配置。
- `CORS_ORIGINS` 填最终 HTTPS 源。通过同源反向代理访问时浏览器不会触发跨域，但保留精确值更安全。
- `DATABASE_URL` 和 `DATA_DIR` 在 Docker Compose 中会被强制覆盖为 `/app/data`，不要在 `.env` 里指向宿主机路径。
- `API_PREFIX` 保持 `/api`。前端、Compose 健康检查和 nginx 都按这个路径配置。
- `DEFAULT_USER_NAME` 只影响预设账号；当前版本没有登录和用户管理。

### 3. 保护密钥

```bash
chmod 600 backend/.env
sudo chown deploy:deploy backend/.env
```

不要把 `.env` 提交到 Git，不要把密钥写进 `docker-compose.yml` 或镜像。轮换 Key 时修改文件后执行 `docker compose up -d`，不要只执行 `restart`。

## Docker Compose 生产部署

### 1. 生产覆盖文件

仓库已包含 `docker-compose.prod.yml`：

```yaml
services:
  frontend:
    ports: !override
      - "127.0.0.1:${APP_PORT:-8080}:80"
```

它把前端端口从所有网卡改为仅本机回环地址。反向代理在同一台宿主机上访问 `127.0.0.1:8080`。

### 2. 启动

在仓库根目录执行：

```bash
cd /opt/ai_chat_room

docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  up -d --build
```

为了避免每次重复写 `-f`，可以在当前 shell 中设置：

```bash
export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
```

之后的命令可以简写为：

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f
```

注意：如果设置了 `COMPOSE_FILE`，`./start.sh` 也会使用生产覆盖文件；如果没有设置，一键脚本使用基础 Compose，会把 8080 绑定到所有网卡。生产环境不要依赖未设置 `COMPOSE_FILE` 的启动脚本直接暴露端口。

### 3. 确认端口绑定

```bash
ss -ltnp | grep 8080
```

期望看到 `127.0.0.1:8080`，而不是 `0.0.0.0:8080` 或 `[::]:8080`。

### 4. 确认容器状态

```bash
docker compose ps
curl -fsS http://127.0.0.1:8080/api/health
```

期望：

- `backend`、`frontend` 都是 `healthy`
- 健康检查返回 `{"status":"ok",...}`

### 5. 开机自启

`docker-compose.yml` 已设置 `restart: unless-stopped`。确保 Docker 服务开机自启：

```bash
sudo systemctl enable docker
```

容器会在 Docker 启动后自动恢复。数据库在命名卷 `backend-data` 中，容器重建不会丢数据。

## TLS 与反向代理

### 方案 A：Caddy（推荐）

Caddy 自动申请和续期证书，并原生支持 WebSocket 转发。

1. 安装 Caddy（按官方文档）。
2. 编辑 `/etc/caddy/Caddyfile`：

```caddyfile
chat.example.com {
    encode zstd gzip

    # 最小访问保护；没有应用层认证，至少加一层 Basic Auth。
    basic_auth {
        admin $2a$14$REPLACE_WITH_BCRYPT_HASH
    }

    reverse_proxy 127.0.0.1:8080
}
```

生成密码哈希：

```bash
caddy hash-password
```

把输出填入 `basic_auth`。然后：

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Caddy 会自动处理 `Upgrade` / `Connection` 头，WebSocket 不需要额外配置。

如果使用 VPN 或 IP 白名单，可以去掉 Basic Auth，但仍然不要把 8080 直接暴露。

### 方案 B：Nginx

如果已有 Nginx，可让它终止 TLS 并转发到前端 nginx：

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    server_name chat.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name chat.example.com;

    ssl_certificate     /etc/letsencrypt/live/chat.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/chat.example.com/privkey.pem;

    client_max_body_size 1m;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_read_timeout 3600s;
    }
}
```

`map` 必须放在 `http` 上下文中；如果使用发行版默认结构，可放在 `/etc/nginx/conf.d/` 的独立文件中。

### 证书与 HTTPS

- 证书续期后重载代理：`sudo systemctl reload caddy` 或 `sudo systemctl reload nginx`。
- 只允许 HTTPS 访问，HTTP 做 301 跳转。
- 可在外层代理添加 HSTS、安全响应头和请求体大小限制。
- 前端容器内部的 nginx 只监听 HTTP，TLS 在外层终止。

## 首次启动验证

按顺序执行：

```bash
cd /opt/ai_chat_room

# 1. 容器状态
docker compose ps

# 2. 本机健康检查
curl -fsS http://127.0.0.1:8080/api/health

# 3. 通过域名检查（如果启用了 Basic Auth，加上 -u）
curl -fsS -u admin:password https://chat.example.com/api/health

# 4. 页面与文档
curl -I -u admin:password https://chat.example.com/
curl -I -u admin:password https://chat.example.com/docs
```

然后在浏览器中：

1. 打开 `https://chat.example.com`。
2. 确认右上角连接状态为 `Live`。
3. 在 **Agents** 中创建一个 Bot。
4. 创建房间并加入该 Bot。
5. 发送 `@BotName 你好`，确认 Bot 回复出现在对话中。
6. 打开 **Tasks**，确认任务、Run 和工具调用记录完整。
7. 如果配置了 Basic Auth，确认 WebSocket 连接仍然正常。

`llm_configured: true` 只表示 Key 非空，不代表 Key 和模型一定有效；真正发一条消息才能验证 Provider 配置。

查看日志：

```bash
docker compose logs -f --tail=100 backend frontend
```

## 数据备份与恢复

### 备份策略

- 数据库：命名卷 `backend-data` 中的 `/app/data/app.db`。
- 配置：`backend/.env`（包含密钥，单独加密保存）。
- 建议每天备份，升级前强制备份，并定期演练恢复。
- 备份文件按敏感数据管理，限制权限并加密传输/存储。

SQLite 使用 WAL。**不要直接复制正在写入的 `app.db`**。使用 SQLite 的在线备份 API：

```bash
cd /opt/ai_chat_room
mkdir -p backups

docker compose exec -T backend python -c "
import sqlite3
src = sqlite3.connect('/app/data/app.db')
dst = sqlite3.connect('/app/data/app.db.bak')
src.backup(dst)
dst.close()
src.close()
"

docker compose cp \
  backend:/app/data/app.db.bak \
  "./backups/app-$(date +%Y%m%d-%H%M%S).db"

docker compose exec -T backend rm -f /app/data/app.db.bak
chmod 600 backups/*.db
```

说明：

- `sqlite3.Connection.backup()` 会生成一致性快照。
- `docker compose cp` 从容器复制到宿主机。
- 如果设置了 `COMPOSE_FILE`，上述 `docker compose` 命令会自动使用生产配置。
- 备份完成后检查文件大小非零：

```bash
ls -lh backups/
```

### 恢复

恢复会覆盖当前数据库。先停止后端，避免并发写入：

```bash
cd /opt/ai_chat_room
docker compose stop backend

docker compose run --rm --no-deps \
  --entrypoint sh \
  -v /opt/ai_chat_room/backups:/backup:ro \
  backend \
  -c 'rm -f /app/data/app.db /app/data/app.db-wal /app/data/app.db-shm && cp /backup/app-20261020-030000.db /app/data/app.db'

docker compose start backend
curl -fsS http://127.0.0.1:8080/api/health
```

把 `app-20261020-030000.db` 替换成实际备份文件名。恢复后：

1. 检查容器健康状态。
2. 打开界面确认房间、消息和任务。
3. 确认 `llm_configured` 为 `true`。
4. 发一条测试消息验证 Bot 流程。

恢复前建议先对当前数据库再做一次备份。

## 升级与回滚

### 升级前检查

1. 阅读目标版本的变更说明。
2. 确认是否有数据库 Schema 变更。
3. **先备份数据库**。
4. 确认服务器磁盘空间足够构建新镜像。
5. 选择低峰期，升级期间服务会短暂中断。

### 升级流程

```bash
cd /opt/ai_chat_room

# 1. 备份
# 使用上一节的在线备份命令

# 2. 拉取目标版本
git fetch --tags
git checkout <new-release-tag>

# 3. 重新构建并启动
docker compose up -d --build

# 4. 验证
docker compose ps
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS https://chat.example.com/api/health
docker compose logs --tail=100 backend frontend
```

升级时：

- 启动过程会把中断的 `running` 任务/Run 标记失败，并重新入队 `queued` 任务。
- 不会自动重试失败任务。
- 没有数据库迁移步骤。

### Schema 变更

当前项目没有 Alembic。`Base.metadata.create_all` 只创建缺失的表，不会给已有表加列、改类型或迁移数据。

如果新版本修改了模型：

- 有手工迁移脚本：先备份，再在数据库上执行，然后启动新版本。
- 没有迁移脚本：不要直接升级；要求提供迁移方案，或在可接受数据丢失的前提下清空数据卷重建。

不要在未备份的情况下依赖 `create_all` 完成升级。

### 回滚

```bash
cd /opt/ai_chat_room
git checkout <previous-release-tag>
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8080/api/health
```

如果新版本已经写入不兼容的 Schema，仅回滚代码不够，需要恢复升级前的数据库备份：

```bash
docker compose stop backend
# 按“数据备份与恢复”步骤恢复
docker compose start backend
```

## 非 Docker 部署

适用于不允许 Docker、但已有 systemd 和 Nginx 的服务器。

### 1. 安装依赖

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 20.19+ 或 22.12+（仅构建前端需要）
- Nginx

### 2. 后端

```bash
cd /opt/ai_chat_room/backend
uv sync --frozen --no-dev
cp .env.example .env
chmod 600 .env
# 编辑 .env，填入生产配置
```

先手动验证：

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

确认后创建 `/etc/systemd/system/ai-chat-room.service`：

```ini
[Unit]
Description=AI Chat Room backend
After=network.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/opt/ai_chat_room/backend
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/ai_chat_room/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ai-chat-room
sudo systemctl status ai-chat-room
curl -fsS http://127.0.0.1:8000/api/health
```

后端从工作目录读取 `.env`，所以 `WorkingDirectory` 必须是 `backend/`，数据库默认位于 `backend/data/app.db`。

### 3. 前端

```bash
cd /opt/ai_chat_room/frontend
npm ci
npm run build

sudo rm -rf /var/www/ai-chat-room
sudo mkdir -p /var/www/ai-chat-room
sudo cp -a dist/. /var/www/ai-chat-room/
sudo chown -R www-data:www-data /var/www/ai-chat-room
```

### 4. Nginx

以仓库的 `frontend/nginx.conf` 为基础，做两处调整：

1. 把 `proxy_pass http://backend:8000;` 改成 `proxy_pass http://127.0.0.1:8000;`。
2. 把 `root` 改成 `/var/www/ai-chat-room`，并放入站点的 `server` / TLS 配置。

需要保留的代理路径：

- `/api/` → 后端
- `/ws/` → 后端，带 `Upgrade` / `Connection` 头
- `/docs`、`/redoc`、`/openapi.json` → 后端
- `/` → SPA fallback `try_files $uri $uri/ /index.html`

### 5. 裸机升级

```bash
cd /opt/ai_chat_room
git fetch --tags
git checkout <new-release-tag>

cd backend
uv sync --frozen --no-dev
sudo systemctl restart ai-chat-room

cd ../frontend
npm ci
npm run build
sudo rm -rf /var/www/ai-chat-room
sudo mkdir -p /var/www/ai-chat-room
sudo cp -a dist/. /var/www/ai-chat-room/
sudo chown -R www-data:www-data /var/www/ai-chat-room
```

升级前同样先备份 `backend/data/app.db`。裸机模式没有 Docker 卷，备份时先停止后端，或用 SQLite 在线备份 API。

## 监控与日常运维

### 健康检查

```bash
# 未启用 Basic Auth
curl -fsS https://chat.example.com/api/health

# 启用 Basic Auth
curl -fsS -u admin:password https://chat.example.com/api/health
```

建议外部监控每 1–5 分钟检查一次，并在以下情况告警：

- HTTP 非 200
- `status != "ok"`
- `llm_configured != true`
- 容器不健康或反复重启

### 日志

```bash
docker compose ps
docker compose logs --tail=200 backend
docker compose logs --tail=200 frontend
```

Docker 默认日志可能持续增长。生产环境建议在 Docker daemon 或 Compose 中配置日志轮转，例如限制单文件大小和保留数量。

### 磁盘与数据库

```bash
df -h
docker system df
docker compose exec -T backend ls -lh /app/data
```

需要关注：

- 命名卷增长（消息、任务、Run、工具调用都会持久化）
- 镜像和构建缓存占用
- 备份目录占用

项目没有自动清理/保留策略，长期运行需要自行制定归档计划。

### 重启

```bash
# 重启容器（不会重新读取 env_file）
docker compose restart backend frontend

# 修改 .env 后重建容器
docker compose up -d
```

### Token 与任务排查

当前没有内置聚合指标。可以在界面的 **Tasks** 面板查看单次任务的 Run、Token 用量、工具调用和错误。需要长期统计时，从 `runs` 表导出数据或增加外部采集。

## 安全加固

- **必须加访问控制。** 当前没有登录；至少在 Caddy/Nginx 加 Basic Auth，或只允许 VPN / 固定 IP。
- **只暴露 80/443。** 用 `docker-compose.prod.yml` 绑定 `127.0.0.1:8080`，不要开放 8080/8000。
- **保护 `/docs`。** OpenAPI 会暴露接口结构；没有访问控制时不要公开。
- **使用 HTTPS。** 包括 WebSocket，浏览器会使用 `wss://`。
- **保护 `.env`。** `chmod 600`，不要进入 Git、镜像或备份明文。
- **轮换 API Key。** 修改后执行 `docker compose up -d`，确认新容器生效。
- **保持镜像更新。** 定期重建基础镜像并更新依赖；关注 Python、Node、nginx 的安全公告。
- **限制工具能力。** Bot 的工具白名单按最小权限配置；`fetch_url` 仍存在 DNS Rebinding 和 Prompt 注入风险。
- **备份加密。** 数据库包含对话和工具结果，备份按敏感数据管理。
- **限制 Docker 权限。** `docker` 组等价于 root，只授予可信用户。
- **反向代理限流。** 项目没有内置限流和费用预算，建议在代理层加请求速率限制。

## 故障排查

**容器启动失败或 backend 不健康。** 先看 `docker compose logs backend`。常见原因：`.env` 格式错误、Key 无效、`/app/data` 不可写、端口冲突。

**访问域名返回 502。** 反向代理无法连接 `127.0.0.1:8080`。检查 `docker compose ps`、`ss -ltnp | grep 8080` 和 frontend 日志。

**WebSocket 一直重连或 offline。** 外层代理必须转发 `Upgrade` / `Connection` 头，并允许长连接。Caddy 默认处理；Nginx 需要本文的 `map` 配置。确认浏览器访问的是 HTTPS 域名，而不是直接访问容器端口。

**`/api/health` 显示 `llm_configured: false`。** `.env` 没有被容器读取。检查文件路径、变量名，并执行 `docker compose up -d`（不是 `restart`）。

**Bot 任务失败。** 打开 **Tasks** 查看 `Task.error`。常见原因：模型不支持工具调用、Provider 401/超时、达到步数上限、Bot 被移出房间。

**SQLite 被锁或任务不推进。** 确认只有一个 backend 容器、一个 uvicorn Worker。不要使用 `--workers 2+`，不要复制 `backend` 服务。

**修改 `API_PREFIX` 后健康检查失败。** Compose 健康检查和前端 nginx 都固定使用 `/api`。保持 `/api`，或同时修改 `docker-compose.yml`、`frontend/nginx.conf` 和前端客户端。

**升级后接口报错或数据异常。** 很可能缺少 Schema 迁移。停止服务，恢复升级前备份，再评估迁移方案。

**磁盘满。** 检查 `docker system df`、`/var/lib/docker` 和备份目录。清理旧镜像/构建缓存前先确认不影响回滚。

**Basic Auth 开启后 WebSocket 失败。** 确认浏览器已经通过同一域名完成认证，并检查代理日志；必要时改用 VPN/IP 白名单。

## 上线检查清单

- [ ] 服务器时间同步正常
- [ ] Docker 和 Compose v2.24+ 可用，Docker 开机自启
- [ ] 只开放 22/80/443，8080/8000 未对公网开放
- [ ] 代码固定到 release tag
- [ ] `backend/.env` 已配置 `ENVIRONMENT=production`、`LLM_*`、`CORS_ORIGINS`
- [ ] `backend/.env` 权限为 `600`，未提交到 Git
- [ ] 使用 `docker-compose.prod.yml`，8080 绑定到 `127.0.0.1`
- [ ] 域名解析正确，TLS 证书有效且自动续期
- [ ] 已加 Basic Auth、VPN 或 IP 白名单
- [ ] `backend`、`frontend` 容器均为 healthy
- [ ] `https://<domain>/api/health` 返回 `status: ok`
- [ ] 页面可以打开，WebSocket 显示 `Live`
- [ ] 创建 Bot/房间并完成一次真实 Bot 回复
- [ ] 已执行一次数据库备份，并验证文件可读
- [ ] 已演练恢复流程（至少一次）
- [ ] 日志轮转、磁盘监控、健康检查告警已配置
- [ ] 已记录升级和回滚步骤

## 已知限制

- 单进程、内存调度器、内存 WebSocket Hub
- SQLite 单 Writer，无分布式队列
- 无认证、无多租户、无房间级权限
- 无 Alembic 迁移
- 无 Token 流式输出、自动重试、限流、费用预算
- 无文件上传、自定义工具、MCP
- 无内置指标、Tracing 或日志轮转
- 无法水平扩容后端

如果需要上述能力，应先改造调度、数据库和认证层，而不是直接增加副本。
