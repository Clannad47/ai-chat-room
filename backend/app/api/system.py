from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CurrentUser, ServicesDep
from app.schemas import UserOut

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(services: ServicesDep) -> dict[str, object]:
    llm_config = await services.model_config.get()
    return {
        "status": "ok",
        "app": services.settings.app_name,
        "version": services.settings.app_version,
        "environment": services.settings.environment,
        "llm_configured": bool(llm_config.api_key),
    }


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
