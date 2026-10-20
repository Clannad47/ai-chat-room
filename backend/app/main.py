from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.llm import LLMClient
from app.api import bots, rooms, system, tasks, ws
from app.api import settings as settings_api
from app.container import build_services
from app.core.config import Settings, get_settings
from app.services.chat import ServiceError


def create_app(settings: Settings | None = None, llm_client: LLMClient | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        services = await build_services(settings, llm_client)
        app.state.services = services
        try:
            yield
        finally:
            await services.close()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ServiceError)
    async def service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    for router in (
        system.router,
        settings_api.router,
        bots.router,
        rooms.router,
        tasks.router,
    ):
        app.include_router(router, prefix=settings.api_prefix)
    app.include_router(ws.router)

    return app


app = create_app()
