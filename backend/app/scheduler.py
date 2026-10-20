from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Task, TaskStatus

logger = logging.getLogger(__name__)
TaskHandler = Callable[[uuid.UUID], Awaitable[None]]


class RoomScheduler:
    """In-process per-room FIFO worker.

    A single process owns scheduling. Durable task status in SQLite is the recovery
    source; on startup queued tasks are re-enqueued and interrupted tasks are failed.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._handler: TaskHandler | None = None
        self._queues: dict[uuid.UUID, asyncio.Queue[uuid.UUID]] = {}
        self._workers: dict[uuid.UUID, asyncio.Task[None]] = {}
        self._running: dict[uuid.UUID, asyncio.Task[None]] = {}
        self._queued: set[uuid.UUID] = set()
        self._closed = False

    def start(self, handler: TaskHandler) -> None:
        self._handler = handler

    def enqueue(self, room_id: uuid.UUID, task_id: uuid.UUID) -> None:
        if self._closed or self._handler is None:
            return
        if task_id in self._queued or task_id in self._running:
            return
        queue = self._queues.setdefault(room_id, asyncio.Queue())
        self._queued.add(task_id)
        queue.put_nowait(task_id)
        if room_id not in self._workers or self._workers[room_id].done():
            self._workers[room_id] = asyncio.create_task(
                self._worker(room_id), name=f"room-worker-{room_id}"
            )

    async def recover(self) -> None:
        async with self._session_factory() as session:
            tasks = (
                await session.scalars(
                    select(Task).where(Task.status == TaskStatus.QUEUED).order_by(Task.created_at)
                )
            ).all()
        for task in tasks:
            self.enqueue(task.room_id, task.id)

    def cancel(self, task_id: uuid.UUID) -> None:
        job = self._running.get(task_id)
        if job is not None and not job.done():
            job.cancel()

    async def _worker(self, room_id: uuid.UUID) -> None:
        queue = self._queues[room_id]
        while True:
            task_id = await queue.get()
            self._queued.discard(task_id)
            try:
                if self._closed or self._handler is None:
                    break
                job = asyncio.create_task(self._handler(task_id), name=f"task-{task_id}")
                self._running[task_id] = job
                try:
                    await job
                except asyncio.CancelledError:
                    if self._closed:
                        raise
                except Exception:
                    logger.exception("Task %s crashed", task_id)
                finally:
                    self._running.pop(task_id, None)
            finally:
                queue.task_done()

    async def stop(self) -> None:
        self._closed = True
        for job in list(self._running.values()):
            job.cancel()
        for worker in list(self._workers.values()):
            worker.cancel()
        await asyncio.gather(
            *self._running.values(), *self._workers.values(), return_exceptions=True
        )
        self._running.clear()
        self._workers.clear()
