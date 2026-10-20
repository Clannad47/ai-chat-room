from __future__ import annotations

from app.core.config import Settings

from .conftest import app_client, create_bot, create_room, wait_for_task
from .fakes import FakeLLM, reply


async def test_llm_settings_are_hot_and_never_expose_the_key(settings: Settings) -> None:
    fake = FakeLLM([reply("Configured on the fly.")])
    async with app_client(settings, fake) as client:
        initial = await client.get("/api/settings/llm")
        assert initial.status_code == 200
        assert initial.json()["api_key_set"] is False
        assert initial.json()["model"] == settings.llm_model
        assert "api_key" not in initial.json()

        updated = await client.put(
            "/api/settings/llm",
            json={
                "provider": "openai",
                "model": "hot-model",
                "base_url": "https://example.test/v1",
                "api_key": "secret-token-1234",
            },
        )
        assert updated.status_code == 200, updated.text
        body = updated.json()
        assert body["model"] == "hot-model"
        assert body["base_url"] == "https://example.test/v1"
        assert body["api_key_set"] is True
        assert body["api_key_hint"] == "••••1234"
        assert "secret-token-1234" not in updated.text

        health = await client.get("/api/health")
        assert health.json()["llm_configured"] is True

        bot = await create_bot(client, "Researcher")
        room = await create_room(client, [bot["id"]])
        sent = await client.post(
            f"/api/rooms/{room['id']}/messages",
            json={"content": "@Researcher use the new settings"},
        )
        assert sent.status_code == 201, sent.text
        task = await wait_for_task(
            client, (await client.get(f"/api/rooms/{room['id']}/tasks")).json()[0]["id"]
        )
        assert task["status"] == "succeeded", task["error"]
        assert fake.calls[0]["model"] == "hot-model"
        assert fake.calls[0]["config"].api_key == "secret-token-1234"
        assert fake.calls[0]["config"].base_url == "https://example.test/v1"


async def test_llm_settings_persist_and_can_clear_the_key(settings: Settings) -> None:
    async with app_client(settings, FakeLLM([])) as client:
        saved = await client.put(
            "/api/settings/llm",
            json={
                "provider": "openai",
                "model": "persisted-model",
                "api_key": "persisted-key",
            },
        )
        assert saved.status_code == 200, saved.text

    async with app_client(settings, FakeLLM([])) as client:
        reloaded = (await client.get("/api/settings/llm")).json()
        assert reloaded["model"] == "persisted-model"
        assert reloaded["api_key_set"] is True

        cleared = await client.put(
            "/api/settings/llm",
            json={
                "provider": "openai",
                "model": "persisted-model",
                "clear_api_key": True,
            },
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["api_key_set"] is False
        assert cleared.json()["api_key_hint"] is None


async def test_llm_settings_reject_invalid_urls(settings: Settings) -> None:
    async with app_client(settings, FakeLLM([])) as client:
        response = await client.put(
            "/api/settings/llm",
            json={
                "provider": "openai",
                "model": "valid-model",
                "base_url": "ftp://example.test",
            },
        )
        assert response.status_code == 422
