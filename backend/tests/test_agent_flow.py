from __future__ import annotations

import json

from app.core.config import Settings

from .conftest import (
    app_client,
    create_bot,
    create_room,
    list_messages,
    list_tasks,
    wait_for_task,
)
from .fakes import FakeLLM, reply, tool_call


async def test_health_and_preset_user(settings: Settings) -> None:
    async with app_client(settings, FakeLLM([])) as client:
        health = await client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["llm_configured"] is False

        me = await client.get("/api/me")
        assert me.status_code == 200
        assert me.json()["username"] == "demo"


async def test_mention_creates_durable_task_and_bot_reply(settings: Settings) -> None:
    fake = FakeLLM([reply("Start with the message pipeline.")])
    async with app_client(settings, fake) as client:
        bot = await create_bot(client, "Researcher")
        room = await create_room(client, [bot["id"]])

        response = await client.post(
            f"/api/rooms/{room['id']}/messages",
            json={"content": "@Researcher what should we build first?"},
        )
        assert response.status_code == 201, response.text
        sent = response.json()
        assert sent["seq"] == 1
        assert sent["mentions"] == [{"type": "bot", "id": bot["id"], "name": "Researcher"}]

        tasks = await list_tasks(client, room["id"])
        assert len(tasks) == 1
        task = await wait_for_task(client, tasks[0]["id"])
        assert task["status"] == "succeeded", task["error"]
        assert task["depth"] == 0

        messages = await list_messages(client, room["id"])
        assert [message["sender_type"] for message in messages] == ["user", "bot"]
        assert messages[1]["sender_name"] == "Researcher"
        assert messages[1]["content"] == "Start with the message pipeline."
        assert messages[1]["seq"] == 2
        assert task["result_message_id"] == messages[1]["id"]
        assert task["runs"][0]["status"] == "succeeded"
        assert fake.calls[0]["model"] == "deepseek-v4.1-flash"


async def test_delegate_tool_creates_child_task_and_visible_handoff(
    settings: Settings,
) -> None:
    fake = FakeLLM(
        [
            tool_call(
                "call_1",
                "delegate_to_bot",
                json.dumps({"bot_name": "Writer", "instruction": "Draft the intro"}),
            ),
            reply("Handed off to @Writer."),
            reply("Intro drafted."),
        ]
    )
    async with app_client(settings, fake) as client:
        researcher = await create_bot(client, "Researcher")
        writer = await create_bot(client, "Writer")
        room = await create_room(client, [researcher["id"], writer["id"]])

        response = await client.post(
            f"/api/rooms/{room['id']}/messages",
            json={"content": "@Researcher prepare the launch copy"},
        )
        assert response.status_code == 201, response.text

        tasks = await list_tasks(client, room["id"])
        assert len(tasks) == 1
        parent = await wait_for_task(client, tasks[0]["id"])
        assert parent["status"] == "succeeded", parent["error"]

        tasks = await list_tasks(client, room["id"])
        assert len(tasks) == 2
        child = next(task for task in tasks if task["parent_id"] == parent["id"])
        child = await wait_for_task(client, child["id"])
        assert child["status"] == "succeeded", child["error"]
        assert child["depth"] == 1
        assert child["root_id"] == parent["root_id"]

        tasks = await list_tasks(client, room["id"])
        assert len(tasks) == 2, "a bot's plain @mention must not create a second task"

        detail = (await client.get(f"/api/tasks/{parent['id']}")).json()
        tool_calls = detail["runs"][0]["tool_calls"]
        assert [call["name"] for call in tool_calls] == ["delegate_to_bot"]
        assert tool_calls[0]["status"] == "ok"

        messages = await list_messages(client, room["id"])
        assert [message["seq"] for message in messages] == [1, 2, 3, 4]
        assert messages[1]["content"] == "@Writer Draft the intro"
        assert messages[1]["mentions"][0]["name"] == "Writer"
        assert messages[3]["content"] == "Intro drafted."


async def test_depth_limit_prevents_runaway_bot_chain(settings: Settings) -> None:
    limited = settings.model_copy(update={"agent_max_depth": 0})
    fake = FakeLLM(
        [
            tool_call(
                "call_1",
                "delegate_to_bot",
                json.dumps({"bot_name": "Writer", "instruction": "pick this up"}),
            ),
            reply("I could not delegate because the depth limit was reached."),
        ]
    )
    async with app_client(limited, fake) as client:
        researcher = await create_bot(client, "Researcher")
        writer = await create_bot(client, "Writer")
        room = await create_room(client, [researcher["id"], writer["id"]])

        response = await client.post(
            f"/api/rooms/{room['id']}/messages",
            json={"content": "@Researcher handle this"},
        )
        assert response.status_code == 201, response.text

        tasks = await list_tasks(client, room["id"])
        assert len(tasks) == 1
        task = await wait_for_task(client, tasks[0]["id"])
        assert task["status"] == "succeeded", task["error"]

        tasks = await list_tasks(client, room["id"])
        assert len(tasks) == 1
        messages = await list_messages(client, room["id"])
        assert [message["sender_type"] for message in messages] == ["user", "bot"]
        assert messages[1]["content"] == (
            "I could not delegate because the depth limit was reached."
        )
        assert len(fake.calls) == 2
        detail = (await client.get(f"/api/tasks/{task['id']}")).json()
        assert detail["runs"][0]["tool_calls"][0]["status"] == "error"
