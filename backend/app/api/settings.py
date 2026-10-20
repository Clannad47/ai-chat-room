from __future__ import annotations

from fastapi import APIRouter

from app.agents.llm import LLMRuntimeConfig
from app.dependencies import ServicesDep
from app.schemas import LLMSettingsOut, LLMSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/llm", response_model=LLMSettingsOut)
async def get_llm_settings(services: ServicesDep) -> LLMSettingsOut:
    return _to_out(await services.model_config.get())


@router.put("/llm", response_model=LLMSettingsOut)
async def update_llm_settings(
    payload: LLMSettingsUpdate,
    services: ServicesDep,
) -> LLMSettingsOut:
    config = await services.model_config.update(
        provider=payload.provider,
        model=payload.model,
        base_url=payload.base_url,
        api_key=payload.api_key,
        clear_api_key=payload.clear_api_key,
    )
    return _to_out(config)


def _to_out(config: LLMRuntimeConfig) -> LLMSettingsOut:
    hint = None
    if config.api_key:
        hint = f"••••{config.api_key[-4:]}" if len(config.api_key) > 4 else "••••"
    return LLMSettingsOut(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        api_key_set=bool(config.api_key),
        api_key_hint=hint,
        updated_at=config.updated_at,
    )
