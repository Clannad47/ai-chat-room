from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import DEFAULT_TOOL_NAMES
from app.core.config import Settings
from app.models import Bot, MemberType, Message, Room, RoomMember, SenderType, Task
from app.services.chat import ChatService

MAX_REDIRECTS = 3


class ToolError(RuntimeError):
    pass


@dataclass
class ToolContext:
    session: AsyncSession
    room: Room
    bot: Bot
    task: Task
    settings: Settings
    chat: ChatService


class GetRoomHistoryArgs(BaseModel):
    limit: int = Field(default=20, ge=1, le=50)


class DelegateToBotArgs(BaseModel):
    bot_name: str = Field(min_length=1, max_length=32)
    instruction: str = Field(min_length=1, max_length=4000)


class FetchUrlArgs(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[ToolContext, Any], Awaitable[Any]]

    def openai_spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }


async def get_room_history(ctx: ToolContext, args: GetRoomHistoryArgs) -> str:
    rows = (
        await ctx.session.scalars(
            select(Message)
            .where(Message.room_id == ctx.room.id)
            .order_by(Message.seq.desc())
            .limit(args.limit)
        )
    ).all()
    lines = [f"#{m.seq} {m.sender_name}: {m.content}" for m in reversed(rows)]
    return "\n".join(lines) or "(no messages)"


async def delegate_to_bot(ctx: ToolContext, args: DelegateToBotArgs) -> str:
    if ctx.task.depth >= ctx.settings.agent_max_depth:
        raise ToolError("Delegation depth limit reached")

    target = await ctx.session.scalar(
        select(Bot)
        .join(
            RoomMember,
            (RoomMember.member_id == Bot.id) & (RoomMember.member_type == MemberType.BOT),
        )
        .where(RoomMember.room_id == ctx.room.id, Bot.name.ilike(args.bot_name))
    )
    if target is None:
        raise ToolError(f"Bot @{args.bot_name} is not in this room")
    if target.id == ctx.bot.id:
        raise ToolError("A bot cannot delegate to itself")

    result = await ctx.chat.post_message(
        ctx.room.id,
        sender_type=SenderType.BOT,
        sender_id=ctx.bot.id,
        sender_name=ctx.bot.name,
        content=f"@{target.name} {args.instruction.strip()}",
        message_task_id=ctx.task.id,
        parent_task_id=ctx.task.id,
        create_tasks_from_mentions=True,
    )
    task_ids = [str(task.id) for task in result.tasks]
    if not task_ids:
        raise ToolError("Delegation was skipped (task depth or room task limit reached)")
    return json.dumps({"delegated_to": target.name, "task_ids": task_ids}, ensure_ascii=False)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [" ".join(line.split()) for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def _extract_text(body: str, content_type: str) -> str:
    if "html" not in content_type:
        return body.strip()
    parser = _TextExtractor()
    try:
        parser.feed(body)
        return parser.text()
    except Exception:
        return body.strip()


async def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ToolError("Only http and https URLs are allowed")
    if not parsed.hostname:
        raise ToolError("URL has no hostname")

    host = parsed.hostname
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        loop = asyncio.get_running_loop()
        infos = await loop.getaddrinfo(host, parsed.port or 0, type=socket.SOCK_STREAM)
        addresses = list({ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos})

    if not addresses:
        raise ToolError("Hostname did not resolve")
    if any(not address.is_global for address in addresses):
        raise ToolError("Private, loopback, and reserved network targets are blocked")


async def fetch_url(ctx: ToolContext, args: FetchUrlArgs) -> str:
    url = args.url.strip()
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10.0),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": "AI-Chat-Room/0.1"},
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await _assert_public_url(url)
            async with client.stream("GET", url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ToolError("Redirect without Location header")
                    url = urljoin(url, location)
                    continue

                content_type = response.headers.get("content-type", "").lower()
                if not any(
                    kind in content_type for kind in ("text/", "json", "xml", "html", "javascript")
                ):
                    raise ToolError(f"Unsupported content type: {content_type or 'unknown'}")

                chunks: list[bytes] = []
                total = 0
                truncated = False
                async for chunk in response.aiter_bytes():
                    remaining = ctx.settings.fetch_max_bytes - total
                    if remaining <= 0:
                        truncated = True
                        break
                    chunks.append(chunk[:remaining])
                    total += len(chunk)
                    if len(chunk) > remaining:
                        truncated = True
                        break

                body = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
                text = _extract_text(body, content_type)
                text = text[: ctx.settings.tool_result_max_chars]
                return json.dumps(
                    {
                        "url": url,
                        "status": response.status_code,
                        "truncated": truncated,
                        "text": text,
                    },
                    ensure_ascii=False,
                )

    raise ToolError("Too many redirects")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self.register(
            ToolSpec(
                name="get_room_history",
                description="Read the most recent messages in this room.",
                args_model=GetRoomHistoryArgs,
                handler=get_room_history,
            )
        )
        self.register(
            ToolSpec(
                name="delegate_to_bot",
                description=(
                    "Post a visible message asking another bot in the room to work on something. "
                    "The target bot receives a new task."
                ),
                args_model=DelegateToBotArgs,
                handler=delegate_to_bot,
            )
        )
        self.register(
            ToolSpec(
                name="fetch_url",
                description="Fetch a public http(s) page and return its readable text.",
                args_model=FetchUrlArgs,
                handler=fetch_url,
            )
        )

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def names(self) -> list[str]:
        return list(self._tools)

    def specs(self, allowed: list[str]) -> list[dict[str, Any]]:
        return [
            self._tools[name].openai_spec()
            for name in dict.fromkeys(allowed)
            if name in self._tools
        ]

    async def execute(self, name: str, raw_arguments: str, ctx: ToolContext) -> str:
        spec = self._tools.get(name)
        if spec is None:
            raise ToolError(f"Unknown tool: {name}")
        try:
            parsed = json.loads(raw_arguments or "{}")
        except json.JSONDecodeError as exc:
            raise ToolError(f"Tool arguments are not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ToolError("Tool arguments must be a JSON object")
        args = spec.args_model.model_validate(parsed)

        result = await asyncio.wait_for(
            spec.handler(ctx, args), timeout=ctx.settings.tool_timeout_seconds
        )
        text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        return text[: ctx.settings.tool_result_max_chars]


__all__ = [
    "DEFAULT_TOOL_NAMES",
    "ToolContext",
    "ToolError",
    "ToolRegistry",
]
