# 后端

FastAPI、SQLAlchemy async、SQLite 与 Agent 运行时。

## 启动

```bash
uv sync
uv run uvicorn app.main:app --reload
```

API Key、Base URL 和默认模型可在前端 **Model settings** 中配置。`backend/.env` 可选；其中的 `LLM_*` 只在首次启动、`llm_settings` 表为空时作为种子值，之后以数据库配置为准并支持热更新。

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health
- SQLite 文件：`data/app.db`（启动时创建）
- 必须从 `backend/` 目录启动；默认数据库地址和 `data/` 都相对于工作目录

## Docker

根目录的 `docker-compose.yml` 使用 `backend/Dockerfile` 构建后端镜像：

- Python 3.12 + uv，非 root 用户，固定单 Worker
- 后端端口不发布到宿主机，由前端 nginx 通过 `backend:8000` 代理
- SQLite 挂载到命名卷 `backend-data` 的 `/app/data`
- 健康检查访问 `/api/health`

在仓库根目录执行 `./start.sh` 或 `.\start.ps1` 即可构建并启动。详见根目录 [`README.md`](../README.md)。

## 模块

```text
app/models.py          users、bots、rooms、messages、tasks、runs、tool_calls
app/schemas.py         Pydantic 请求/响应模型
app/services/chat.py   seq 分配、提及路由、任务创建、消息广播
app/services/model_config.py  数据库模型配置、缓存与热更新
app/agents/context.py  System Prompt 与对话记录组装
app/agents/runtime.py  持久化 Agent 循环、取消检查、Run 收尾
app/agents/llm.py      OpenAI 兼容适配器
app/agents/tools.py    工具注册表与 fetch_url 防护
app/scheduler.py       每房间 FIFO Worker
app/realtime.py        WebSocket 广播
app/api/               REST + WebSocket 端点
app/container.py       服务组装与生命周期
app/db.py              引擎、PRAGMA、种子数据、重启恢复
app/core/config.py     Settings
```

## 关键行为

- 所有消息通过 `ChatService.post_message` 写入；`seq` 与消息在同一事务中分配。
- 人类消息中的 `@BotName` 会为每个房间成员 Bot 创建深度为 `0` 的任务。
- Bot 文本中的普通提及不创建任务；只有 `delegate_to_bot` 会创建子任务。
- 每个房间一个 FIFO Worker，同一房间的 Agent 任务串行执行。
- 模型配置存于 `llm_settings` 单行表；`GET/PUT /api/settings/llm` 修改后，新任务立即使用新配置，无需重启。
- `ModelConfigService` 缓存配置；直接改数据库不会让运行中的进程感知，需通过 API/界面更新或重启。
- `LLM_*` 环境变量只在首次建库、`llm_settings` 表为空时作为种子；之后修改 `.env` 不会覆盖数据库配置。
- API Key 以明文存于 `llm_settings`，接口只返回是否设置和末四位提示；设置接口没有认证，Base URL 可指向任意 `http(s)` 地址，部署时必须保护访问。
- 启动时把中断的 `running` 任务/Run 标记失败，并重新入队 `queued` 任务。
- 调度器和 WebSocket Hub 在进程内，只能运行一个后端进程。
- 没有认证；所有请求都以预设用户身份执行。

## 测试

```bash
uv run ruff check .
uv run ruff format --check .
uv run python -m pytest
```

测试使用 `tests/fakes.py` 的脚本化 LLM，不访问网络，也不需要 API Key。每个测试使用临时 SQLite 数据库。`tests/test_model_settings.py` 覆盖模型配置的读取、热更新、持久化和 Key 不回显。

## 修改指南

架构约束、工具/端点/Schema 的修改流程和完成标准见仓库根目录的 [`AGENTS.md`](../AGENTS.md)。用户文档、API 和协议说明见 [`README.md`](../README.md)；生产部署、备份和升级见 [`DEPLOYMENT.md`](../DEPLOYMENT.md)。
