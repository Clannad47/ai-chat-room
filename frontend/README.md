# 前端

React 19 + TypeScript + Vite。

## 启动

```bash
npm install
npm run dev
```

打开 http://127.0.0.1:5173。Vite 会把 `/api` 和 `/ws` 代理到 http://127.0.0.1:8000。

## Docker

根目录的 `docker-compose.yml` 使用 `frontend/Dockerfile`：

- 多阶段构建：Node 执行 `npm ci` 和 `npm run build`
- 最终镜像只包含 nginx 和 `dist/`
- `nginx.conf` 提供 SPA fallback，并代理 `/api`、`/ws`、`/docs`、`/openapi.json`
- 默认通过 http://localhost:8080 访问

在仓库根目录执行 `./start.sh` 或 `.\start.ps1` 即可构建并启动。详见根目录 [`README.md`](../README.md)。

## 主要模块

```text
src/App.tsx             工作区状态、房间选择、实时事件合并
src/components/         侧栏、聊天区、输入框、检查器、模型设置、头像
src/useRoomSocket.ts    自动重连的房间 Socket
src/api.ts              带类型的 REST 客户端
src/i18n.tsx            中英文文案、语言上下文与持久化
src/types.ts            API/领域类型
src/utils.ts            消息/任务合并工具
src/App.css             应用样式
```

## 行为要点

- 当前房间写入 URL hash（`#/rooms/<uuid>`），刷新后可恢复。
- 消息按 ID 合并、按 `seq` 排序；内存中最多保留最近 300 条。
- 断线后最多重试六次，指数退避，上限 8 秒；遇到关闭码 `4404` 停止。
- 重连成功后会重新拉取房间详情、最近 100 条消息和任务。
- 任务取消只对 `queued` / `running` 状态显示。
- 左下角设置按钮打开 **Model settings**；保存后后端新任务立即使用新配置，API Key 不会回显到浏览器。
- 创建 Bot 的表单不暴露温度和 `max_steps`，两者可通过 REST API 设置。
- 没有路由库和状态管理库；服务端状态集中在 `App.tsx`。
- 界面文案集中在 `src/i18n.tsx`，支持中文/英文切换；默认中文，偏好写入 `localStorage` 的 `ai-chat-room.language`，同时更新 `<html lang>`。
- 新增文案时同时补充 `en` 与 `zh` 字典，组件通过 `useI18n().t(key, params)` 读取。

## 检查

```bash
npm run lint
npm run build
```

前端没有单元测试框架。UI 改动应连接运行中的后端在浏览器验证。修改后端字段时，需要同步更新 `src/types.ts`、`src/api.ts` 和组件。

架构约束和修改流程见仓库根目录的 [`AGENTS.md`](../AGENTS.md)；完整 API 和协议见 [`README.md`](../README.md)；生产部署、TLS 和备份见 [`DEPLOYMENT.md`](../DEPLOYMENT.md)。
