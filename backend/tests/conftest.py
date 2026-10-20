from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from asgi_lifespan import LifespanManager

from app.core.config import Settings
from app.main import create_app

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        data_dir=tmp_path,
        llm_api_key=None,
        llm_base_url=None,
        cors_origins=[],
    )


@asynccontextmanager
async def app_client(settings: Settings, llm) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings, llm)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def create_bot(
    client: httpx.AsyncClient,
    name: str,
    allowed_tools: list[str] | None = None,
) -> dict:
    response = await client.post(
        "/api/bots",
        json={
            "name": name,
            "description": f"{name} test bot",
            "persona": "Be concise.",
            "allowed_tools": allowed_tools or ["get_room_history", "delegate_to_bot", "fetch_url"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_room(client: httpx.AsyncClient, bot_ids: list[str]) -> dict:
    response = await client.post(
        "/api/rooms",
        json={"name": f"Room {uuid.uuid4().hex[:6]}", "bot_ids": bot_ids},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def wait_for_task(client: httpx.AsyncClient, task_id: str, timeout: float = 5.0) -> dict:
    for _ in range(int(timeout / 0.05)):
        response = await client.get(f"/api/tasks/{task_id}")
        assert response.status_code == 200, response.text
        task = response.json()
        if task["status"] in TERMINAL_STATUSES:
            return task
        await asyncio.sleep(0.05)
    raise AssertionError(f"Task {task_id} did not finish in {timeout}s")


async def list_tasks(client: httpx.AsyncClient, room_id: str) -> list[dict]:
    response = await client.get(f"/api/rooms/{room_id}/tasks")
    assert response.status_code == 200, response.text
    return response.json()


async def list_messages(client: httpx.AsyncClient, room_id: str) -> list[dict]:
    response = await client.get(f"/api/rooms/{room_id}/messages")
    assert response.status_code == 200, response.text
    return response.json()
