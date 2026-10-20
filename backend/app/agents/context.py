from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.models import Bot, Message, Room, Task


def build_conversation(
    settings: Settings,
    room: Room,
    bot: Bot,
    task: Task,
    messages: list[Message],
    room_bots: list[Bot],
) -> list[dict[str, Any]]:
    teammates = ", ".join(
        f"@{other.name}" + (f" ({other.description})" if other.description else "")
        for other in room_bots
        if other.id != bot.id
    )
    system = (
        f'You are {bot.name}, an AI collaborator in the chat room "{room.name}".\n'
        f"{bot.description}\n"
        f"Your persona and instructions:\n{bot.persona or 'Be a capable, concise teammate.'}\n\n"
        "How this room works:\n"
        "- Humans and bots share one transcript. Your final assistant text is posted to the room "
        "as your message.\n"
        "- Use tools when they help. Do not pretend to call a tool.\n"
        "- To ask another bot to act, call the delegate_to_bot tool. A plain @mention is "
        "informational and does not create work for that bot.\n"
        "- Delegated work is visible in the room. Do not mention yourself. Prefer a direct, "
        "useful answer over narration.\n"
        "- If the request is impossible with the available tools, say what is missing.\n"
    )
    if teammates:
        system += f"\nTeammates in this room: {teammates}\n"

    lines: list[str] = []
    for message in messages:
        content = message.content.strip()
        if len(content) > 2000:
            content = content[:2000] + " …"
        lines.append(
            f"#{message.seq} {message.sender_name} ({message.sender_type.value}): {content}"
        )

    transcript: list[str] = []
    used = 0
    for line in reversed(lines):
        if used + len(line) + 1 > settings.agent_max_context_chars:
            break
        transcript.append(line)
        used += len(line) + 1
    transcript.reverse()

    user = (
        "Recent room transcript (oldest to newest):\n"
        + ("\n".join(transcript) if transcript else "(empty)")
        + f"\n\nYour task: {task.goal}\n"
        "Produce the message to post back to the room."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
