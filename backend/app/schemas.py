from __future__ import annotations

import uuid
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants import DEFAULT_TOOL_NAMES
from app.models import MemberType, RunStatus, SenderType, TaskStatus

BOT_NAME_PATTERN = r"^[\w\-\u4e00-\u9fff]{1,32}$"


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(ORMModel):
    id: uuid.UUID
    username: str
    display_name: str


class BotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=32, pattern=BOT_NAME_PATTERN)
    description: str = Field(default="", max_length=200)
    persona: str = Field(default="", max_length=4000)
    model: str | None = Field(default=None, max_length=100)
    temperature: float = Field(default=0.7, ge=0, le=2)
    allowed_tools: list[str] = Field(
        default_factory=lambda: list(DEFAULT_TOOL_NAMES), max_length=20
    )
    max_steps: int = Field(default=8, ge=1, le=20)


class BotOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str
    persona: str
    model: str | None
    temperature: float
    allowed_tools: list[str]
    max_steps: int
    created_at: int


class LLMSettingsOut(BaseModel):
    provider: str
    model: str
    base_url: str | None
    api_key_set: bool
    api_key_hint: str | None
    updated_at: int


class LLMSettingsUpdate(BaseModel):
    provider: Literal["openai"] = "openai"
    model: str = Field(min_length=1, max_length=100)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    clear_api_key: bool = False

    @field_validator("model")
    @classmethod
    def model_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("model must not be blank")
        return value

    @field_validator("base_url")
    @classmethod
    def valid_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an http(s) URL")
        return value

    @field_validator("api_key")
    @classmethod
    def normalize_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    bot_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)


class RoomOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str
    next_seq: int
    created_at: int


class RoomDetail(RoomOut):
    bots: list[BotOut]
    tasks_pending: int = 0


class MentionOut(BaseModel):
    type: MemberType = MemberType.BOT
    id: uuid.UUID
    name: str


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be blank")
        return value


class MessageOut(ORMModel):
    id: uuid.UUID
    room_id: uuid.UUID
    seq: int
    sender_type: SenderType
    sender_id: uuid.UUID | None
    sender_name: str
    content: str
    mentions: list[MentionOut]
    task_id: uuid.UUID | None
    origin_run_id: uuid.UUID | None
    created_at: int


class ToolCallOut(ORMModel):
    id: uuid.UUID
    name: str
    arguments: dict
    result_preview: str
    status: str
    error: str | None
    created_at: int
    finished_at: int | None


class RunOut(ORMModel):
    id: uuid.UUID
    task_id: uuid.UUID
    bot_id: uuid.UUID
    attempt: int
    status: RunStatus
    model: str
    input_tokens: int
    output_tokens: int
    error: str | None
    created_at: int
    finished_at: int | None
    tool_calls: list[ToolCallOut]


class TaskOut(ORMModel):
    id: uuid.UUID
    room_id: uuid.UUID
    root_id: uuid.UUID
    parent_id: uuid.UUID | None
    assignee_bot_id: uuid.UUID
    trigger_message_id: uuid.UUID
    goal: str
    depth: int
    status: TaskStatus
    result_message_id: uuid.UUID | None
    error: str | None
    created_at: int
    started_at: int | None
    finished_at: int | None


class TaskDetail(TaskOut):
    assignee_name: str
    runs: list[RunOut]
