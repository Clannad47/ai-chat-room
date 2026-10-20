from __future__ import annotations

from typing import Any

from app.agents.llm import LLMResponse, LLMRuntimeConfig, LLMToolCall


class FakeLLM:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        temperature: float,
        config: LLMRuntimeConfig,
    ) -> LLMResponse:
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "model": model,
                "temperature": temperature,
                "config": config,
            }
        )
        if not self.responses:
            raise AssertionError("FakeLLM ran out of scripted responses")
        return self.responses.pop(0)

    async def aclose(self) -> None:
        return None


def reply(content: str) -> LLMResponse:
    return LLMResponse(content=content)


def tool_call(call_id: str, name: str, arguments: str) -> LLMResponse:
    return LLMResponse(
        content=None,
        tool_calls=[LLMToolCall(id=call_id, name=name, arguments=arguments)],
    )
