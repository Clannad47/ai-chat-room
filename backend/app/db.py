from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.models import Base, LLMSetting, Run, RunStatus, Task, TaskStatus, User, now_ms

DEMO_USER_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "ai-chat-room/demo-user")


def create_engine(settings: Settings) -> AsyncEngine:
    if settings.database_url.startswith("sqlite"):
        settings.data_dir.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(
        settings.database_url,
        connect_args={"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {},
    )

    if settings.database_url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


async def init_db(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.username == settings.default_user_name))
        if user is None:
            session.add(
                User(
                    id=DEMO_USER_ID,
                    username=settings.default_user_name,
                    display_name=settings.default_user_display_name,
                )
            )

        now = now_ms()
        llm_setting = await session.get(LLMSetting, 1)
        if llm_setting is None:
            api_key = (
                settings.llm_api_key.get_secret_value()
                if settings.llm_api_key is not None
                else None
            )
            session.add(
                LLMSetting(
                    id=1,
                    provider=settings.llm_provider,
                    api_key=api_key or None,
                    base_url=settings.llm_base_url or None,
                    model=settings.llm_model,
                    updated_at=now,
                )
            )
        await session.execute(
            update(Task)
            .where(Task.status == TaskStatus.RUNNING)
            .values(
                status=TaskStatus.FAILED,
                error="Interrupted by server restart",
                finished_at=now,
            )
        )
        await session.execute(
            update(Run)
            .where(Run.status == RunStatus.RUNNING)
            .values(status=RunStatus.FAILED, error="Interrupted by server restart", finished_at=now)
        )
        await session.commit()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    services = request.app.state.services
    async with services.session_factory() as session:
        yield session
