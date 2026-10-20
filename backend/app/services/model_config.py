from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.llm import LLMRuntimeConfig
from app.core.config import Settings
from app.models import LLMSetting, now_ms

logger = logging.getLogger(__name__)

LLM_SETTINGS_ID = 1


class ModelConfigService:
    """Caches the database-backed LLM settings and refreshes them on update.

    The settings row is seeded from the environment at startup; afterwards the
    database is authoritative so changes apply to new tasks without a restart.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._config: LLMRuntimeConfig | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> LLMRuntimeConfig:
        if self._config is None:
            async with self._lock:
                if self._config is None:
                    self._config = await self._load()
        return self._config

    async def update(
        self,
        *,
        provider: str,
        model: str,
        base_url: str | None,
        api_key: str | None,
        clear_api_key: bool,
    ) -> LLMRuntimeConfig:
        async with self._lock, self._session_factory() as session:
            row = await session.get(LLMSetting, LLM_SETTINGS_ID)
            if row is None:
                row = LLMSetting(id=LLM_SETTINGS_ID)
                session.add(row)
            row.provider = provider
            row.model = model
            row.base_url = base_url
            if clear_api_key:
                row.api_key = None
            elif api_key:
                row.api_key = api_key
            row.updated_at = now_ms()
            await session.commit()
            self._config = _from_row(row)
            logger.info("LLM settings updated via API (provider=%s, model=%s)", provider, model)
            return self._config

    async def _load(self) -> LLMRuntimeConfig:
        async with self._session_factory() as session:
            row = await session.get(LLMSetting, LLM_SETTINGS_ID)
            if row is not None:
                return _from_row(row)

        # A row is seeded by init_db, but keep the service usable without it.
        api_key = (
            self._settings.llm_api_key.get_secret_value()
            if self._settings.llm_api_key is not None
            else None
        )
        return LLMRuntimeConfig(
            provider=self._settings.llm_provider,
            api_key=api_key or None,
            base_url=self._settings.llm_base_url or None,
            model=self._settings.llm_model,
        )


def _from_row(row: LLMSetting) -> LLMRuntimeConfig:
    return LLMRuntimeConfig(
        provider=row.provider,
        api_key=row.api_key,
        base_url=row.base_url,
        model=row.model,
        updated_at=row.updated_at,
    )
