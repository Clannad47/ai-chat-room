from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.agents.llm import LLMClient, build_llm_client
from app.agents.runtime import AgentRuntime
from app.agents.tools import ToolRegistry
from app.core.config import Settings
from app.db import create_engine, init_db
from app.realtime import RealtimeHub
from app.scheduler import RoomScheduler
from app.services.chat import ChatService
from app.services.model_config import ModelConfigService


@dataclass
class Services:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    hub: RealtimeHub
    registry: ToolRegistry
    llm: LLMClient
    scheduler: RoomScheduler
    chat: ChatService
    model_config: ModelConfigService
    runtime: AgentRuntime

    async def close(self) -> None:
        await self.scheduler.stop()
        await self.llm.aclose()
        await self.engine.dispose()


async def build_services(settings: Settings, llm_client: LLMClient | None = None) -> Services:
    engine = create_engine(settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    await init_db(engine, session_factory, settings)

    hub = RealtimeHub()
    scheduler = RoomScheduler(session_factory)
    chat = ChatService(session_factory, settings, hub, scheduler)
    registry = ToolRegistry()
    llm = llm_client or build_llm_client()
    model_config = ModelConfigService(session_factory, settings)
    runtime = AgentRuntime(session_factory, settings, hub, chat, registry, llm, model_config)

    scheduler.start(runtime.execute_task)
    await scheduler.recover()

    return Services(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        hub=hub,
        registry=registry,
        llm=llm,
        scheduler=scheduler,
        chat=chat,
        model_config=model_config,
        runtime=runtime,
    )
