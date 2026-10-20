# AGENTS.md

`ai_chat_room` 的贡献者与编码 Agent 指南。产品介绍、API 和用户行为见 [`README.md`](README.md)；本文只讲如何在不破坏现有约束的前提下修改仓库。

## 仓库地图

```text
DEPLOYMENT.md         生产部署：服务器、TLS、备份、升级、回滚、监控
docker-compose.yml    backend/frontend 服务、健康检查、命名数据卷
docker-compose.prod.yml 生产端口绑定（仅 127.0.0.1）
start.ps1             Windows 一键构建/启动/等待
start.cmd             Windows 双击包装
start.sh              Linux/macOS 一键构建/启动/等待
backend/
  Dockerfile          Python 3.12 + uv 运行镜像（非 root、单 Worker）
  .dockerignore
  app/
    agents/
      context.py      Prompt 与对话记录组装
      llm.py          OpenAI 兼容适配器与 LLM 协议
      runtime.py      持久化任务执行循环
      tools.py        工具注册表、参数 Schema、fetch_url 防护
    api/              FastAPI 路由：system、settings、bots、rooms、tasks、ws
    core/config.py    pydantic-settings 环境配置与模型种子值
    services/chat.py  消息入口、seq 分配、提及解析、任务创建
    services/model_config.py  数据库模型配置、缓存与热更新
    container.py      依赖组装与启动
    db.py             引擎、PRAGMA、种子数据、重启恢复
    models.py         SQLAlchemy 2 模型
    realtime.py       进程内 WebSocket 广播
    scheduler.py      进程内每房间 FIFO Worker
    schemas.py        Pydantic 请求/响应模型
    main.py           应用工厂与异常映射
  tests/              使用脚本化 LLM 的确定性 API/集成测试
frontend/
  Dockerfile          Node 构建 + nginx 静态镜像
  nginx.conf          SPA、`/api`、`/ws`、`/docs` 代理
  .dockerignore
  src/
    App.tsx           工作区状态、实时合并、hash 路由
    api.ts            带类型的 REST 客户端
    types.ts          API/领域类型（与 schemas.py 手工保持同步）
    useRoomSocket.ts  自动重连的房间 Socket
    components/       Sidebar、ChatPanel、Composer、Inspector、ModelSettings、Avatar
    i18n.tsx           中英文文案与语言状态
    App.css           全部应用样式
```

运行时数据位于 `backend/data/`（本地开发）或命名卷 `backend-data`（Docker），已被 gitignore。仓库没有 Makefile 或 CI；根目录提供一键启动脚本。

## 技术栈与运行约束

- 后端：Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2 async、SQLite（`aiosqlite`）、OpenAI SDK。
- 前端：React 19、TypeScript、Vite、`oxlint`、`lucide-react`。没有路由库或状态管理库。
- 调度器和 WebSocket Hub 都在**内存**中。同一个 SQLite 数据库只能有一个后端进程。不支持多 Worker uvicorn。
- **没有认证。** 每个请求都解析为配置的预设用户。不要把应用描述成多租户或已生产加固。
- SQLite Schema 通过 `Base.metadata.create_all` 创建，没有 Alembic 历史。修改模型后必须手工迁移或删除开发数据库。
- 前端写死 `/api` 和 `/ws`，Vite 将两者代理到 `127.0.0.1:8000`。只改 `API_PREFIX` 而不改前端会导致应用不可用。
- Docker 栈同样只能有一个后端副本。Compose（v2.24+）不发布后端端口，nginx 通过 `backend:8000` 访问；SQLite 挂载在命名卷 `backend-data`。
- `docker-compose.prod.yml` 使用 `!override` 把前端端口绑定到 `127.0.0.1`。生产必须同时加载该文件；基础 Compose 绑定 `0.0.0.0`，只适合本地。
- `frontend/nginx.conf` 负责 SPA fallback、API/WebSocket 代理和 API 文档代理。新增顶层 HTTP 路径（不是 `/api` 下）时要同步更新它。

## 环境准备

后端，在 `backend/` 下：

```bash
cp .env.example .env        # 可选；PowerShell：Copy-Item .env.example .env
# 模型配置也可在启动后从界面 Model settings 写入数据库，支持热更新
uv sync
uv run uvicorn app.main:app --reload
```

前端，在 `frontend/` 下：

```bash
npm install
npm run dev
```

后端必须从 `backend/` 启动，因为默认 SQLite 地址和 `data/` 目录相对于工作目录。测试不需要 API Key，也不访问网络。

Docker 一键启动（在仓库根目录）：

```bash
./start.sh                 # Linux/macOS
.\start.ps1                # Windows PowerShell
```

Windows 也可以双击 `start.cmd`。脚本会检查 Docker、按需创建 `backend/.env`、执行 `docker compose up -d --build`，并轮询 `/api/health`。默认访问 http://localhost:8080，API 文档位于 `/docs`。Docker 模式不需要本地 Python/Node。

## 命令

交付前运行相关检查。不要每改一行就重复跑；在改动完成后统一运行一次。

| 区域 | 命令 | 工作目录 |
|---|---|---|
| Lint | `uv run ruff check .` | `backend/` |
| 格式检查 | `uv run ruff format --check .` | `backend/` |
| 测试 | `uv run python -m pytest` | `backend/` |
| 格式化写入 | `uv run ruff format .` | `backend/` |
| 前端 Lint | `npm run lint` | `frontend/` |
| 前端类型检查 + 构建 | `npm run build` | `frontend/` |
| 前端开发服务器 | `npm run dev` | `frontend/` |
| Compose 配置校验 | `docker compose config --quiet` | 仓库根目录 |
| Compose 构建并启动 | `docker compose up -d --build` | 仓库根目录 |
| 生产构建并启动 | `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` | 仓库根目录 |
| Compose 日志 | `docker compose logs -f` | 仓库根目录 |
| Compose 停止 | `docker compose down` | 仓库根目录 |

修改 `backend/.env` 后执行 `docker compose up -d`；`docker compose restart` 不会重新加载 `env_file`。**例外：** `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` 只在首次建库时作为种子；模型配置请在界面 **Model settings** 或 `PUT /api/settings/llm` 修改，立即生效，不需要重启。

`pytest` 配置了 `asyncio_mode = "auto"`，异步测试不需要额外装饰器。

## 架构契约

除非任务明确要求重构，否则保持以下约束。

1. **所有消息都通过 `ChatService.post_message` 写入。** 它负责成员校验、房间 `seq` 分配、提及持久化、任务创建、广播和入队。API 和运行时不要直接插入 `Message` 行。
2. **`seq` 与消息在同一事务中分配**，使用原子操作
   `UPDATE rooms SET next_seq = next_seq + 1 RETURNING next_seq`。不要用 Python 计数器，也不要按时间戳排序。
3. **一次 Bot 调用对应一个持久化 `Task`；每次尝试对应一个 `Run`；每次工具调用对应一个 `ToolCall`。** SQLite 中的任务状态是事实来源，内存队列不是。
4. **只有 `ChatService` 会根据提及创建任务。** 人类消息自动路由提及；Bot 消息不路由，只有 `delegate_to_bot` 显式传入 `create_tasks_from_mentions=True`。这可以防止 Bot 的最终文本重复制造任务。
5. **每个房间一个 FIFO Worker。** 房间内任务按创建顺序执行。委派产生的子任务要等发起委派的任务结束后才运行。
6. **任务执行前必须原子抢占**，把状态从 `QUEUED` 改为 `RUNNING`。保持 `execute_task` 幂等；重复入队不能启动第二个 Run。
7. **提交后再广播。** WebSocket 事件只是尽力而为的通知，不是事实来源。客户端通过重新拉取 REST 数据恢复。
8. **启动恢复属于契约。** `init_db` 把中断的 `running` 任务/Run 标记失败；`scheduler.recover` 重新入队 `queued` 任务。不要留下孤立的 `running` 行。
9. **工具输出对模型可见并会持久化。** 使用 `TOOL_RESULT_MAX_CHARS` 截断；工具失败会变成对话中的错误结果，不一定会让任务失败。
10. **运行配置统一来自 `app.core.config.Settings`，例外是模型连接配置。** `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` 只在首次启动且 `llm_settings` 表为空时作为种子；之后以数据库为准，通过 `ModelConfigService` 读取并热更新。业务模块不要直接读 `os.environ`。其他新配置要加到 Settings 和 `backend/.env.example`。

## 修改流程

### 新增或修改 HTTP 端点

1. 在 `app/schemas.py` 添加请求/响应模型。
2. 在 `app/api/` 对应路由中添加端点。使用 `CurrentUser`、`SessionDep`、`ServicesDep`；房间级访问调用 `require_room`。
3. 业务逻辑放在 service 中，路由保持轻薄。
4. 如果前端会使用，更新 `frontend/src/api.ts` 和 `frontend/src/types.ts`。
5. 使用 `tests/conftest.py` 的 `app_client` 添加 API 级测试。
6. 更新 `README.md` 的端点表和请求/响应说明。

### 新增工具

1. 在 `app/agents/tools.py` 添加 Pydantic 参数模型和异步处理器：
   `async def handler(ctx: ToolContext, args: ArgsModel) -> str`。
2. 在 `ToolRegistry.__init__` 注册 `ToolSpec`。OpenAI Schema 由参数模型生成；描述中要明确副作用。
3. 预期内、模型可处理的失败抛 `ToolError`；内部崩溃不要伪装成普通工具错误。
4. 只有新创建的 Bot 应默认启用时，才把名称加入 `app/constants.py` 的 `DEFAULT_TOOL_NAMES`。
5. 在 `frontend/src/components/Inspector.tsx` 的 `TOOL_OPTIONS` 中添加选项。
6. 添加测试：成功、工具未授权、参数非法、超时/错误行为。
7. 更新 `README.md` 的工具表。

工具会收到带当前 `AsyncSession`、房间、Bot、任务、配置和 ChatService 的 `ToolContext`。不要在工具里另开 Session；使用传入的 Session，保证任务状态一致。

### 修改模型配置或设置页

- 模型连接配置存在 `llm_settings` 单行表（`id=1`），通过 `ModelConfigService` 读取和缓存；更新时必须同时写数据库和替换 `_config` 缓存，保证新任务立即生效。
- `LLM_*` 环境变量只在 `init_db` 首次创建 `LLMSetting` 行时作为种子；已有行时不要用环境变量覆盖数据库配置。
- `GET /api/settings/llm` 只暴露 `api_key_set` / `api_key_hint`，绝不能返回原始 Key；`PUT` 的 `api_key` 为空表示保留，`clear_api_key=true` 才清除。
- 运行中的任务在开始时取配置快照；修改只影响之后创建的任务。不要把配置读取放进每次 LLM 调用，否则会改变现有语义。
- API Key 以明文存储在 SQLite，接口没有认证；新增设置时保持这一安全边界在文档中可见，不要假设有多用户权限。
- 前端修改涉及 `ModelSettings.tsx`、`api.ts`、`types.ts` 和 `i18n.tsx` 的中英文文案。
- 测试参考 `tests/test_model_settings.py`：初始值、热更新后新任务使用新配置、Key 不回显、持久化、清除 Key、非法 Base URL。
- 同步更新 `README.md` 的配置/API/安全章节和 `DEPLOYMENT.md` 的模型配置章节。

### 修改 Agent 循环或 Prompt

- `context.py` 负责 System Prompt 和对话记录预算。每条记录截断到 2,000 字符；`AGENT_MAX_CONTEXT_CHARS` 只约束对话记录。
- `runtime.py` 负责抢占、创建 Run、工具循环、工具执行、取消检查和收尾。
- 循环次数为 `min(bot.max_steps, settings.agent_max_steps)`。
- 没有工具调用的响应必须包含非空文本，否则任务失败。
- 每次模型调用和每次工具调用前都检查取消状态。
- 不要自己发布最终消息；调用 `ChatService.post_message`，保证 `seq`、提及、广播和关联字段一致。
- 如果增加新的模型/Provider 能力，同时扩展 `LLMClient` 协议和 `tests/fakes.py` 中的 Fake。

### 修改数据库 Schema

1. 更新 `app/models.py` 和受影响的 Pydantic Schema。
2. 更新 `frontend/src/types.ts` 和 UI（如果字段对外暴露）。
3. 更新 `README.md` 的数据模型章节。
4. 没有迁移工具。开发环境删除 `backend/data/app.db` 后重启。需要保留数据时先建立真正的迁移路径；不要依赖 `create_all` 修改已有表。
5. 为新约束和状态流转添加测试，而不是只测序列化。

### 新增 WebSocket 事件

1. 在数据库提交后由 service 广播，Payload 必须是 JSON 可序列化内容。
2. 与消息顺序相关的事件传 `seq`；任务/Run 事件保持 `None`。
3. 在 `App.tsx` 中处理，必要时更新 `WsEvent` 类型。未知事件必须忽略。
4. 把投递当作尽力而为。客户端重连后需要的状态必须能通过 REST 重新获取。
5. 更新 `README.md` 的事件表。

### 前端修改

- 服务端状态集中在 `App.tsx`；组件只接收 props 和回调。
- 消息按 ID 合并、按 `seq` 排序（`utils.ts`）。不要按 `created_at` 排序。
- 任务事件用 `upsertTask`；当前选中的任务变化时刷新任务详情。
- 所有 REST 调用都走 `api.ts`；在界面中展示 `ApiError.message`。
- Socket 重连后已经会重新拉取房间详情、消息和任务。不要添加第二套重连循环。
- 样式集中在 `App.css`；沿用现有 CSS 变量和响应式断点。

### Docker / Compose 修改

- 后端镜像只复制 `pyproject.toml`、`uv.lock` 和 `app/`。新增运行时文件时要同步修改 `backend/Dockerfile` 和 `.dockerignore`。
- 前端镜像先 `npm ci` 再 `npm run build`，最终只保留 `dist/` 和 nginx。新增构建期文件时检查 `.dockerignore` 没有误排除。
- `/api`、`/ws`、`/docs`、`/openapi.json` 的代理在 `frontend/nginx.conf`。新增后端顶层路径时同步更新。
- Compose 健康检查固定访问 `/api/health`。修改 `API_PREFIX` 时必须同步修改 `docker-compose.yml`，否则前端不会启动。
- Compose 通过 `env_file` 读取 `backend/.env`，并覆盖 `DATABASE_URL`、`DATA_DIR` 指向 `/app/data`。不要把密钥写入镜像或 Compose 文件。
- 模型配置存在命名卷里的 `llm_settings` 表；`LLM_*` 只是首次播种。修改模型设置不要通过重建容器或改 Compose 环境变量期待生效。
- 后端固定单 Worker、非 root 用户。若修改用户或数据目录，确认命名卷可写。
- `start.ps1`、`start.sh` 和 `start.cmd` 的逻辑要保持一致：检查 Docker、按需创建 env、构建启动、轮询健康检查、打印 URL。修改端口变量或健康检查时三处一起改。
- 修改依赖后先更新 `uv.lock` / `package-lock.json`，再重新构建镜像。

## 编码约定

### Python

- 模块顶部使用 `from __future__ import annotations`。
- 完整类型标注；全程 async I/O。请求和 Agent 代码不要调用同步 SQLAlchemy API。
- Ruff 启用 `E`、`F`、`I`、`UP`、`B`，行宽 100，目标 Python 3.12。
- 持久化时间戳使用 `now_ms()`，ID 使用 UUID。
- 优先写小的 service 方法，不要把逻辑堆在路由里。
- 非预期异常要带上下文记录日志；只有预期失败才转换成 `ServiceError`、`HTTPException`、`ToolError` 或 `AgentError`。

### TypeScript / React

- 严格 TypeScript；`npm run build` 会先执行 `tsc -b` 再构建 Vite。
- 使用 `oxlint`。组件 props 要显式定义类型。
- 没有具体需求不要新增运行时依赖；前端刻意不使用路由和状态管理库。
- 外部边界尽量使用 `unknown` 加类型收窄；不要引入 `any`。
- API 类型必须与后端响应 Schema 结构一致。

### 文档

- `README.md` 面向用户和运维：安装、API、协议、限制、故障排查。
- `DEPLOYMENT.md` 是生产部署流程：TLS、访问控制、备份恢复、升级回滚；部署相关改动要同步更新。
- `backend/README.md` 和 `frontend/README.md` 是区域速查，命令必须准确。
- 行为变更与文档更新放在同一个改动里。不要把计划中的功能写成已实现。

## 测试要求

- 测试使用 `tests/fakes.py` 的 `FakeLLM`，绝不能调用真实 Provider 或网络。
- `app_client` 会启动完整 lifespan，包括调度器。用 `wait_for_task` 等待终态，不要固定 sleep。
- 使用 `settings` fixture 提供的临时 SQLite，不要碰 `backend/data/app.db`。
- 覆盖可观察行为：任务/消息顺序、提及路由、委派限制、工具持久化、取消、重启恢复和错误路径。
- 模型配置改动要验证：环境变量首次播种、热更新后新任务使用新配置、Key 不回显、持久化、清除 Key、非法 Base URL。
- 前端没有单元测试框架。UI 改动要连接运行中的后端在浏览器验证，并运行 `npm run lint` 和 `npm run build`。

## 常见陷阱

- 即使 Bot 设置了更高的 `max_steps`，`AGENT_MAX_STEPS` 仍是全局硬上限。
- `AGENT_MAX_DEPTH` 把根任务算作深度 0。只要 `parent.depth < AGENT_MAX_DEPTH` 就允许委派。
- `AGENT_MAX_TASKS_PER_ROOT` 在插入子任务前检查，并且把根任务计入总数。
- Bot 调用未授权的工具会记录为错误 `ToolCall`；模型会看到错误并可以继续。
- 工具参数 JSON 解析失败时仍会记录（参数为 `{}`）；随后注册表向模型返回校验错误。
- 把 Bot 移出房间不会取消它已有任务。运行时会让这些任务以“Bot is not a member of this room”失败。
- 失败任务不会发布 Bot 消息。检查 `Task.error` 及其 Run/工具调用。
- 对终态任务调用取消返回 `409`；取消运行中的任务会把 Run 标记为取消。
- `fetch_url` 在每次重定向时都会检查地址，但无法完全防御 DNS Rebinding。修改时保留私网/保留地址检查。
- 服务运行时删除数据库会让内存调度状态失效。先停止服务。
- 界面中的消息历史有上限；数据库保留全部行。
- `LLM_*` 只在首次建库时作为种子；数据库已有 `llm_settings` 行时，改 `.env` 不会改变模型配置，也不会热更新。
- 模型配置在任务开始时取快照；修改只影响之后创建的任务，运行中的任务继续使用旧 Key/模型/Base URL。
- API Key 明文存在 `llm_settings` 表，备份也会带走；`PUT /api/settings/llm` 没有认证，Base URL 可指向任意 `http(s)` 地址，必须保护页面/API 访问。
- `ModelConfigService` 缓存配置；直接改数据库不会让运行中的进程感知，必须通过界面/API 更新，或重启服务。
- Docker 模式下的 SQLite 在命名卷 `backend-data`，不是宿主机的 `backend/data/`。重置使用 `docker compose down -v`，这会同时删除数据库。
- `docker compose restart backend` 不会重新加载 `backend/.env`；使用 `docker compose up -d` 重建容器。
- 后端端口没有发布到宿主机，浏览器统一访问 8080；不要在前端里写死 `127.0.0.1:8000`。
- 如果 Docker 构建时拉取基础镜像失败，先确认 Docker 引擎和镜像仓库网络，再重试 `docker compose build --pull`。

## 完成标准

- 变更经过端到端验证（API 测试、浏览器冒烟或真实运行），而不是只通过类型检查。
- 后端：`uv run ruff check .`、`uv run ruff format --check .`、`uv run python -m pytest` 全部通过。
- 前端（如有改动）：`npm run lint` 和 `npm run build` 通过。
- Docker/Compose（如有改动）：`docker compose config --quiet` 通过；引擎可用时执行一次 `docker compose up -d --build` 并验证 `/api/health`。
- 调用方、Schema、前端类型、测试和文档同步更新。
- 不提交密钥、生成的数据库、构建产物或 `node_modules`。
- 日志、错误消息和 API 响应中不得出现原始 API Key。
