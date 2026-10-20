from __future__ import annotations

import asyncio
import json
import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.context import build_conversation
from app.agents.llm import LLMClient, LLMRuntimeConfig
from app.agents.tools import ToolContext, ToolError, ToolRegistry
from app.core.config import Settings
from app.models import (
    Bot,
    MemberType,
    Room,
    RoomMember,
    Run,
    RunStatus,
    SenderType,
    Task,
    TaskStatus,
    ToolCall,
    now_ms,
)
from app.realtime import RealtimeHub
from app.schemas import TaskOut
from app.services.chat import ChatService
from app.services.model_config import ModelConfigService

logger = logging.getLogger(__name__)


class AgentError(RuntimeError):
    pass


class TaskCancelled(AgentError):
    pass


class AgentRuntime:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        hub: RealtimeHub,
        chat: ChatService,
        registry: ToolRegistry,
        llm: LLMClient,
        model_config: ModelConfigService,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._hub = hub
        self._chat = chat
        self._registry = registry
        self._llm = llm
        self._model_config = model_config

    async def execute_task(self, task_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            claimed = await session.scalar(
                update(Task)
                .where(Task.id == task_id, Task.status == TaskStatus.QUEUED)
                .values(status=TaskStatus.RUNNING, started_at=now_ms(), error=None)
                .returning(Task.id)
            )
            await session.commit()
            if claimed is None:
                return

            task = await session.get(Task, task_id)
            if task is None:
                return
            room = await session.get(Room, task.room_id)
            bot = await session.get(Bot, task.assignee_bot_id)
            if room is None or bot is None:
                await self._finalize_failure(
                    task_id, None, TaskStatus.FAILED, "Room or bot missing"
                )
                return

            await self._broadcast_task(task)

            is_member = await session.scalar(
                select(RoomMember.id).where(
                    RoomMember.room_id == room.id,
                    RoomMember.member_type == MemberType.BOT,
                    RoomMember.member_id == bot.id,
                )
            )
            if is_member is None:
                await self._finalize_failure(
                    task_id, None, TaskStatus.FAILED, "Bot is not a member of this room"
                )
                return

            model_config = await self._model_config.get()
            run = Run(
                task_id=task.id,
                bot_id=bot.id,
                attempt=(
                    await session.scalar(select(func.count(Run.id)).where(Run.task_id == task.id))
                    or 0
                )
                + 1,
                status=RunStatus.RUNNING,
                model=bot.model or model_config.model,
            )
            session.add(run)
            await session.commit()

            await self._hub.broadcast(
                room.id,
                "run.started",
                {
                    "run_id": str(run.id),
                    "task_id": str(task.id),
                    "bot_id": str(bot.id),
                    "model": run.model,
                },
            )

            try:
                content, input_tokens, output_tokens = await self._run_loop(
                    session, task, room, bot, run, model_config
                )
                if await self._current_status(session, task.id) == TaskStatus.CANCELLED:
                    raise TaskCancelled
                post = await self._chat.post_message(
                    room.id,
                    sender_type=SenderType.BOT,
                    sender_id=bot.id,
                    sender_name=bot.name,
                    content=content,
                    message_task_id=task.id,
                    parent_task_id=task.id,
                    origin_run_id=run.id,
                )
                await self._finalize_success(
                    task.id, run.id, post.message.id, input_tokens, output_tokens
                )
            except TaskCancelled:
                await self._finalize_failure(
                    task.id, run.id, TaskStatus.CANCELLED, "Cancelled by user"
                )
            except asyncio.CancelledError:
                asyncio.create_task(
                    self._finalize_failure(
                        task.id, run.id, TaskStatus.CANCELLED, "Cancelled by user"
                    )
                )
                raise
            except Exception as exc:
                logger.exception("Agent task %s failed", task.id)
                await session.rollback()
                await self._finalize_failure(task.id, run.id, TaskStatus.FAILED, _safe_error(exc))

    async def _run_loop(
        self,
        session: AsyncSession,
        task: Task,
        room: Room,
        bot: Bot,
        run: Run,
        model_config: LLMRuntimeConfig,
    ) -> tuple[str, int, int]:
        messages = await self._chat.recent_messages(room.id, self._settings.room_history_limit)
        room_bots = list(
            (
                await session.scalars(
                    select(Bot)
                    .join(
                        RoomMember,
                        (RoomMember.member_id == Bot.id)
                        & (RoomMember.member_type == MemberType.BOT),
                    )
                    .where(RoomMember.room_id == room.id)
                )
            ).all()
        )
        conversation = build_conversation(self._settings, room, bot, task, messages, room_bots)
        allowed_tools = [name for name in bot.allowed_tools if name in self._registry.names()]
        tool_specs = self._registry.specs(allowed_tools)
        model = bot.model or model_config.model
        input_tokens = 0
        output_tokens = 0

        for _ in range(min(bot.max_steps, self._settings.agent_max_steps)):
            await self._ensure_running(session, task.id)
            response = await self._llm.complete(
                conversation,
                tool_specs,
                model=model,
                temperature=bot.temperature,
                config=model_config,
            )
            input_tokens += response.input_tokens
            output_tokens += response.output_tokens

            if not response.tool_calls:
                content = (response.content or "").strip()
                if not content:
                    raise AgentError("The model returned an empty response")
                return content[: self._settings.agent_reply_max_chars], input_tokens, output_tokens

            conversation.append(response.assistant_message())
            for call in response.tool_calls:
                await self._ensure_running(session, task.id)
                result, error = await self._execute_tool(session, task, room, bot, run, call)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result if error is None else f"Tool error: {error}",
                    }
                )

        raise AgentError("The bot reached its step limit without a final answer")

    async def _execute_tool(
        self,
        session: AsyncSession,
        task: Task,
        room: Room,
        bot: Bot,
        run: Run,
        call,
    ) -> tuple[str, str | None]:
        try:
            parsed = json.loads(call.arguments or "{}")
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        tool_call = ToolCall(
            run_id=run.id,
            name=call.name,
            arguments=parsed,
            status="running",
        )
        session.add(tool_call)
        await session.commit()

        error: str | None = None
        result = ""
        if call.name not in bot.allowed_tools or call.name not in self._registry.names():
            error = f"Tool '{call.name}' is not available to this bot"
            result = error
        else:
            ctx = ToolContext(
                session=session,
                room=room,
                bot=bot,
                task=task,
                settings=self._settings,
                chat=self._chat,
            )
            try:
                result = await self._registry.execute(call.name, call.arguments, ctx)
            except ToolError as exc:
                error = str(exc)
                result = error
            except TimeoutError:
                error = "Tool timed out"
                result = error
            except Exception as exc:  # noqa: BLE001 - tool failures are model-visible
                logger.exception("Tool %s crashed", call.name)
                error = _safe_error(exc)
                result = error

        tool_call.status = "error" if error else "ok"
        tool_call.error = error
        tool_call.result_preview = result[: self._settings.tool_result_max_chars]
        tool_call.finished_at = now_ms()
        await session.commit()
        return result[: self._settings.tool_result_max_chars], error

    async def _ensure_running(self, session: AsyncSession, task_id: uuid.UUID) -> None:
        status = await self._current_status(session, task_id)
        await session.commit()
        if status != TaskStatus.RUNNING:
            raise TaskCancelled

    @staticmethod
    async def _current_status(session: AsyncSession, task_id: uuid.UUID) -> TaskStatus | None:
        return await session.scalar(select(Task.status).where(Task.id == task_id))

    async def _finalize_success(
        self,
        task_id: uuid.UUID,
        run_id: uuid.UUID,
        result_message_id: uuid.UUID,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        async with self._session_factory() as session:
            task = await session.get(Task, task_id)
            run = await session.get(Run, run_id)
            if task is None or run is None:
                return
            if task.status == TaskStatus.CANCELLED:
                run.status = RunStatus.CANCELLED
                run.finished_at = now_ms()
            else:
                task.status = TaskStatus.SUCCEEDED
                task.result_message_id = result_message_id
                task.finished_at = now_ms()
                run.status = RunStatus.SUCCEEDED
                run.finished_at = now_ms()
            run.input_tokens = input_tokens
            run.output_tokens = output_tokens
            await session.commit()
            await self._broadcast_task(task)
        await self._broadcast_run(room_id=None, task_id=task_id, run_id=run_id)

    async def _finalize_failure(
        self,
        task_id: uuid.UUID,
        run_id: uuid.UUID | None,
        status: TaskStatus,
        error: str | None,
    ) -> None:
        async with self._session_factory() as session:
            task = await session.get(Task, task_id)
            if task is None:
                return
            if task.status == TaskStatus.SUCCEEDED:
                return
            cancelled = task.status == TaskStatus.CANCELLED and status != TaskStatus.CANCELLED
            if not cancelled:
                task.status = status
                task.error = error
                task.finished_at = now_ms()
            run = await session.get(Run, run_id) if run_id is not None else None
            if run is not None and run.status == RunStatus.RUNNING:
                if cancelled or status == TaskStatus.CANCELLED:
                    run.status = RunStatus.CANCELLED
                    run.error = task.error or "Cancelled by user"
                else:
                    run.status = RunStatus.FAILED
                    run.error = error
                run.finished_at = now_ms()
            await session.commit()
            await self._broadcast_task(task)
        if run_id is not None:
            await self._broadcast_run(room_id=None, task_id=task_id, run_id=run_id)

    async def _broadcast_task(self, task: Task) -> None:
        payload = TaskOut.model_validate(task).model_dump(mode="json")
        await self._hub.broadcast(task.room_id, "task.updated", {"task": payload})

    async def _broadcast_run(
        self, *, room_id: uuid.UUID | None, task_id: uuid.UUID, run_id: uuid.UUID
    ) -> None:
        if room_id is None:
            async with self._session_factory() as session:
                task = await session.get(Task, task_id)
                if task is None:
                    return
                room_id = task.room_id
        async with self._session_factory() as session:
            run = await session.get(Run, run_id)
            if run is None:
                return
            payload = {
                "run_id": str(run.id),
                "task_id": str(run.task_id),
                "status": run.status.value,
                "model": run.model,
                "input_tokens": run.input_tokens,
                "output_tokens": run.output_tokens,
                "error": run.error,
                "finished_at": run.finished_at,
            }
        await self._hub.broadcast(room_id, "run.finished", {"run": payload})


def _safe_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    return message[:1000]
