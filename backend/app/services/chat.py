from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import (
    Bot,
    MemberType,
    Message,
    Room,
    RoomMember,
    SenderType,
    Task,
    TaskStatus,
    now_ms,
)
from app.realtime import RealtimeHub
from app.scheduler import RoomScheduler
from app.schemas import MessageOut, TaskOut

MENTION_RE = re.compile(r"(?<![\w@])@([\w\-]{1,32})", re.UNICODE)


class ServiceError(Exception):
    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404


class PermissionError(ServiceError):
    status_code = 403


@dataclass
class PostResult:
    message: Message
    tasks: list[Task]


class ChatService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        hub: RealtimeHub,
        scheduler: RoomScheduler,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._hub = hub
        self._scheduler = scheduler

    async def post_message(
        self,
        room_id: uuid.UUID,
        *,
        sender_type: SenderType,
        sender_id: uuid.UUID | None,
        sender_name: str,
        content: str,
        message_task_id: uuid.UUID | None = None,
        parent_task_id: uuid.UUID | None = None,
        origin_run_id: uuid.UUID | None = None,
        create_tasks_from_mentions: bool | None = None,
    ) -> PostResult:
        content = content.strip()
        if not content:
            raise ServiceError("Message is empty")
        content = content[: self._settings.agent_reply_max_chars]

        async with self._session_factory() as session:
            room = await session.get(Room, room_id)
            if room is None:
                raise NotFoundError("Room not found")

            await self._assert_member(session, room_id, sender_type, sender_id)

            bots = (
                await session.scalars(
                    select(Bot)
                    .join(
                        RoomMember,
                        (RoomMember.member_id == Bot.id)
                        & (RoomMember.member_type == MemberType.BOT),
                    )
                    .where(RoomMember.room_id == room_id)
                )
            ).all()
            bot_by_name = {bot.name.lower(): bot for bot in bots}
            mentions = self._parse_mentions(content, bot_by_name, sender_type, sender_id)

            parent = None
            if parent_task_id is not None:
                parent = await session.get(Task, parent_task_id)
                if parent is None:
                    raise NotFoundError("Parent task not found")

            seq = (
                await session.execute(
                    update(Room)
                    .where(Room.id == room_id)
                    .values(next_seq=Room.next_seq + 1)
                    .returning(Room.next_seq)
                )
            ).scalar_one() - 1

            message = Message(
                id=uuid.uuid4(),
                room_id=room_id,
                seq=seq,
                sender_type=sender_type,
                sender_id=sender_id,
                sender_name=sender_name,
                content=content,
                mentions=[
                    {"type": MemberType.BOT.value, "id": str(bot.id), "name": bot.name}
                    for bot in mentions
                ],
                task_id=message_task_id,
                origin_run_id=origin_run_id,
            )
            session.add(message)

            tasks: list[Task] = []
            should_route = (
                create_tasks_from_mentions
                if create_tasks_from_mentions is not None
                else sender_type == SenderType.USER
            )
            if should_route:
                for bot in mentions:
                    task = await self._create_task(session, room_id, bot, message, parent)
                    if task is not None:
                        tasks.append(task)

            await session.commit()

            message_out = MessageOut.model_validate(message)
            task_outs = [TaskOut.model_validate(task) for task in tasks]

        await self._hub.broadcast(
            room_id,
            "message.created",
            {"message": message_out.model_dump(mode="json")},
            seq=message.seq,
        )
        for task, task_out in zip(tasks, task_outs, strict=True):
            await self._hub.broadcast(
                room_id,
                "task.updated",
                {"task": task_out.model_dump(mode="json")},
            )
            self._scheduler.enqueue(room_id, task.id)

        return PostResult(message=message, tasks=tasks)

    async def list_messages(
        self,
        room_id: uuid.UUID,
        *,
        limit: int = 100,
        after_seq: int | None = None,
    ) -> list[Message]:
        async with self._session_factory() as session:
            if await session.get(Room, room_id) is None:
                raise NotFoundError("Room not found")
            query = select(Message).where(Message.room_id == room_id)
            if after_seq is not None:
                query = query.where(Message.seq > after_seq).order_by(Message.seq).limit(limit)
                return list((await session.scalars(query)).all())

            query = query.order_by(Message.seq.desc()).limit(limit)
            rows = list((await session.scalars(query)).all())
            rows.reverse()
            return rows

    async def recent_messages(self, room_id: uuid.UUID, limit: int) -> list[Message]:
        return await self.list_messages(room_id, limit=limit)

    async def _assert_member(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        sender_type: SenderType,
        sender_id: uuid.UUID | None,
    ) -> None:
        if sender_type == SenderType.SYSTEM:
            return
        if sender_id is None:
            raise PermissionError("Sender is required")
        member_type = MemberType.BOT if sender_type == SenderType.BOT else MemberType.USER
        member = await session.scalar(
            select(RoomMember.id).where(
                RoomMember.room_id == room_id,
                RoomMember.member_type == member_type,
                RoomMember.member_id == sender_id,
            )
        )
        if member is None:
            raise PermissionError("Sender is not a member of this room")

    @staticmethod
    def _parse_mentions(
        content: str,
        bot_by_name: dict[str, Bot],
        sender_type: SenderType,
        sender_id: uuid.UUID | None,
    ) -> list[Bot]:
        found: list[Bot] = []
        seen: set[uuid.UUID] = set()
        for match in MENTION_RE.finditer(content):
            bot = bot_by_name.get(match.group(1).lower())
            if bot is None or bot.id in seen:
                continue
            if sender_type == SenderType.BOT and sender_id == bot.id:
                continue
            seen.add(bot.id)
            found.append(bot)
        return found

    async def _create_task(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        bot: Bot,
        message: Message,
        parent: Task | None,
    ) -> Task | None:
        depth = parent.depth + 1 if parent is not None else 0
        if depth > self._settings.agent_max_depth:
            return None

        root_id = parent.root_id if parent is not None else uuid.uuid4()
        if parent is not None:
            count = await session.scalar(
                select(func.count(Task.id)).where(Task.root_id == parent.root_id)
            )
            if (count or 0) >= self._settings.agent_max_tasks_per_root:
                return None

        task_id = uuid.uuid4()
        task = Task(
            id=task_id,
            room_id=room_id,
            root_id=root_id if parent is not None else task_id,
            parent_id=parent.id if parent is not None else None,
            assignee_bot_id=bot.id,
            trigger_message_id=message.id,
            goal=message.content[:8000],
            depth=depth,
            status=TaskStatus.QUEUED,
            created_at=now_ms(),
        )
        session.add(task)
        await session.flush()
        return task
