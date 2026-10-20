# 部署指南

最简单的部署方式：在项目根目录执行一条命令。

```bash
docker compose up -d --build
```

启动后打开 <http://localhost:8080>。模型配置可以在页面左下角的 **Model settings** 中填写，不需要提前改 `.env`。

## 环境要求

- Docker Engine 或 Docker Desktop
- Docker Compose v2.24+（执行 `docker compose version` 能正常输出版本；生产覆盖文件使用 `!override`）
- 首次构建需要能访问 Docker Hub 和依赖源
- 使用 `start.sh` 时需要 `curl`

## 启动

### 方式一：直接使用 Docker Compose

```bash
git clone https://github.com/Clannad47/ai-chat-room.git
cd ai-chat-room
docker compose up -d --build
```

### 方式二：使用启动脚本

Linux / macOS：

```bash
./start.sh
```

Windows PowerShell：

```powershell
.\start.ps1
```

脚本会自动创建缺失的 `backend/.env`、执行 `docker compose up -d --build`、等待健康检查，并输出访问地址。

指定端口：

```bash
./start.sh 9090
```

```powershell
.\start.ps1 -Port 9090
```

直接使用 Docker Compose 时：

```bash
APP_PORT=9090 docker compose up -d --build
```

```powershell
$env:APP_PORT = "9090"
docker compose up -d --build
```

## 公网部署（可选）

基础 `docker-compose.yml` 会把前端端口绑定到 `0.0.0.0`，只适合本机或可信内网。公网或生产环境必须同时加载 `docker-compose.prod.yml`，把端口限制到 `127.0.0.1`，再由外层反向代理提供 HTTPS 和访问控制：

```bash
export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
docker compose up -d --build
docker compose ps
```

确认绑定地址：

```bash
docker compose port frontend 80
# 期望：127.0.0.1:8080
```

然后配置 Caddy/Nginx 反向代理、TLS、Basic Auth 或 VPN/IP 白名单。不要直接把 8080 暴露到公网。更多日常命令见 [`README.md`](README.md) 的 Docker 章节。

## 配置模型

模型连接配置全部支持页面热更新，不需要改环境变量或重启。

启动后打开页面，点击左下角的 **Model settings**，填写：

- Provider（当前为 OpenAI 兼容）
- Base URL（留空使用服务商默认地址；必须是 `http(s)` URL）
- API Key（留空表示保留已保存的 Key；也可以勾选移除）
- 默认模型（Bot 未设置模型覆盖时使用）

保存后立即对**之后创建的任务**生效，不需要重启或重建容器。正在运行的任务在启动时已经取了配置快照，会继续使用旧配置直到结束。

### 存储与 API

- 配置保存在 SQLite 的 `llm_settings` 单行表中，容器重建不会丢失。
- `GET /api/settings/llm` 返回当前配置；原始 API Key 永远不会返回，只返回 `api_key_set` 和末四位提示。
- `PUT /api/settings/llm` 修改配置，立即更新内存缓存和数据库。
- `ModelConfigService` 会缓存当前配置；不要直接改 SQLite 的 `llm_settings` 行，进程不会感知，必须通过 API/界面修改或重启服务。
- `GET /api/health` 的 `llm_configured` 直接反映当前数据库中的 Key 是否非空，保存后立即变化。

`PUT` 示例：

```json
{
  "provider": "openai",
  "model": "deepseek-v4.1-flash",
  "base_url": "https://api.example.com/v1",
  "api_key": "sk-...",
  "clear_api_key": false
}
```

### 环境变量只负责首次播种

也可以在第一次启动前复制 `backend/.env.example` 为 `backend/.env`，填写 `LLM_PROVIDER`、`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`。这些值只在数据库第一次创建、`llm_settings` 表为空时作为初始配置：

- 数据库已有配置后，修改 `.env` 不会覆盖页面配置，也不会热更新。
- 需要重新用环境变量播种时，只能停止服务并删除数据库/数据卷，这会同时清空房间、消息和任务。
- `backend/.env` 已被 Git 忽略，不会上传。

### 安全注意

- API Key 以**明文**存储在 `llm_settings` 表中，没有磁盘加密或访问审计。
- 备份数据库会同时备份 API Key，备份文件必须按密钥管理。
- 模型设置没有独立权限，任何能访问页面的人都能修改 API Key、模型和 Base URL。
- Base URL 允许任意 `http(s)` 地址；能修改配置的人可以让服务端把 Key 发送到自己的地址。公网部署必须加认证或限制访问。

## 访问地址

| 地址 | 用途 |
|---|---|
| `http://localhost:8080` | 界面 |
| `http://localhost:8080/docs` | API 文档 |
| `http://localhost:8080/api/health` | 健康检查 |

本地或可信内网可以用 `http://<服务器IP>:8080` 访问。默认端口是 `8080`，可通过 `APP_PORT` 修改。

公网部署使用 `docker-compose.prod.yml` 后，8080 只绑定在 `127.0.0.1`，应通过反向代理的 HTTPS 域名访问。

## 常用命令

在项目根目录执行：

```bash
docker compose ps                 # 查看状态
docker compose logs -f            # 查看日志
docker compose restart            # 重启
docker compose down               # 停止并删除容器，保留数据
docker compose up -d --build      # 重新构建并启动
docker compose down -v            # 停止并删除数据卷（会清空所有数据）
```

## 数据与备份

数据保存在 Docker 命名卷 `backend-data` 中，容器重建不会丢失。执行 `docker compose down` 不会删除数据；只有 `docker compose down -v` 会清空。

备份数据库：

```bash
docker compose exec -T backend python -c "
import sqlite3
src = sqlite3.connect('/app/data/app.db')
dst = sqlite3.connect('/app/data/backup.db')
src.backup(dst)
dst.close()
src.close()
"
docker compose cp backend:/app/data/backup.db ./backup.db
docker compose exec -T backend rm -f /app/data/backup.db
```

备份文件包含对话记录和模型配置（包括明文 API Key），请设置权限并妥善保管：

```bash
chmod 600 backup.db
```

恢复前先停止后端，并用备份覆盖数据库（会删除当前数据库和 WAL 文件）：

```bash
docker compose stop backend

docker compose run --rm --no-deps \
  --entrypoint sh \
  -v "$PWD:/backup:ro" \
  backend \
  -c 'rm -f /app/data/app.db /app/data/app.db-wal /app/data/app.db-shm && cp /backup/backup.db /app/data/app.db'

docker compose start backend
curl -fsS http://127.0.0.1:8080/api/health
```

恢复会同时恢复备份中的模型配置和 API Key。恢复前建议先备份当前数据库。

## 升级

```bash
git pull
docker compose up -d --build
```

升级前建议先备份。模型配置和 API Key 保存在数据库的 `llm_settings` 表中，普通代码升级、容器重建不会丢失，也不需要重新填；升级后仍以数据库中的配置为准。如果 `backend/.env` 中的 `LLM_*` 发生变化，不会覆盖已有配置。

项目没有数据库迁移工具；如果新版本修改了表结构，需要手工迁移，或删除数据卷后重新创建（会丢失数据，包括模型配置，之后会用 `LLM_*` 重新播种）。

## 注意事项

- 只能运行一个 `backend` 容器，不要扩容副本，也不要把 uvicorn 改成多 Worker。
- 基础 Compose 会监听 `0.0.0.0:8080`，只适合本机或可信内网。公网部署必须同时加载 `docker-compose.prod.yml`，通过 VPN、防火墙或反向代理的访问控制保护，并在反向代理层配置 HTTPS。
- **模型设置没有独立权限。** 任何能访问页面的人都能修改模型配置和 API Key；Base URL 允许任意 `http(s)` 地址，恶意配置可以让服务端把 Key 发往攻击者地址。
- API Key 以明文保存在 SQLite 和备份文件中，没有磁盘加密或访问审计；数据库和备份都要按密钥管理。
- 修改模型配置请用 **Model settings**，保存后对后续任务立即生效；改 `.env` 中的 `LLM_*` 只影响首次建库播种，不会覆盖已有配置。

## 故障排查

查看容器状态和日志：

```bash
docker compose ps
docker compose logs --tail=100 backend
```

常见问题：

- **端口被占用**：改用 `APP_PORT=9090 docker compose up -d --build`。
- **backend 不健康**：检查 `docker compose logs backend`，确认 `.env` 格式、数据库卷权限和端口正常。健康检查不校验 API Key 是否有效。
- **`llm_configured` 为 `false`**：数据库中的 Key 为空。打开 **Model settings** 填写并保存；保存后健康检查立即变化。
- **Bot 不回复**：打开 **Model settings** 检查 API Key、Base URL 和模型；也可以查看 **Tasks** 中的错误。
- **修改 `.env` 的 `LLM_*` 后没有变化**：这是预期行为。`LLM_*` 只在首次建库时作为种子；已有数据库时请用 **Model settings**。
- **修改模型配置后当前任务没有变化**：运行中的任务使用启动时的配置快照；新任务才会使用新配置。
- **切换 Key 或 Base URL**：在 **Model settings** 保存即可，不需要重启；旧 Key 不会从数据库历史中恢复，但备份可能仍包含旧 Key。
- **需要完全重置**：执行 `docker compose down -v` 后重新启动，会清空所有数据；模型配置会被清空，并用 `backend/.env` 中的 `LLM_*` 重新播种。
