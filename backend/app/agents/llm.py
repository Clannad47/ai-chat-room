from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class LLMConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMRuntimeConfig:
    provider: str
    api_key: str | None = field(repr=False)
    base_url: str | None
    model: str
    updated_at: int = 0


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    def assistant_message(self) -> dict[str, Any]:
        message: dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in self.tool_calls
            ]
        return message


class LLMClient(Protocol):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        temperature: float,
        config: LLMRuntimeConfig,
    ) -> LLMResponse: ...

    async def aclose(self) -> None: ...


class OpenAIClient:
    def __init__(self) -> None:
        self._clients: dict[tuple[str, str | None], AsyncOpenAI] = {}

    def _get_client(self, config: LLMRuntimeConfig) -> AsyncOpenAI:
        if config.provider != "openai":
            raise LLMConfigurationError(f"Unsupported LLM provider: {config.provider}")
        if not config.api_key:
            raise LLMConfigurationError(
                "LLM API key is not configured; set it in the model settings panel"
            )
        cache_key = (config.api_key, config.base_url or None)
        client = self._clients.get(cache_key)
        if client is None:
            client = AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url or None,
                max_retries=2,
            )
            self._clients[cache_key] = client
        return client

    async def aclose(self) -> None:
        clients = list(self._clients.values())
        self._clients.clear()
        for client in clients:
            await client.close()

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        temperature: float,
        config: LLMRuntimeConfig,
    ) -> LLMResponse:
        client = self._get_client(config)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0].message
        tool_calls = [
            LLMToolCall(
                id=call.id,
                name=call.function.name,
                arguments=call.function.arguments or "",
            )
            for call in (choice.tool_calls or [])
        ]
        usage = response.usage
        return LLMResponse(
            content=choice.content,
            tool_calls=tool_calls,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )


def build_llm_client() -> LLMClient:
    return OpenAIClient()
