from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.agents.llm import LLMConfigurationError, LLMRuntimeConfig, OpenAIClient


class _Completions:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="call_1",
                                function=SimpleNamespace(
                                    name="get_room_history",
                                    arguments='{"limit": 5}',
                                ),
                            )
                        ],
                    )
                )
            ],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=4),
        )


def _config(**overrides: Any) -> LLMRuntimeConfig:
    values: dict[str, Any] = {
        "provider": "openai",
        "api_key": "test-key",
        "base_url": None,
        "model": "test-model",
    }
    values.update(overrides)
    return LLMRuntimeConfig(**values)


async def test_openai_adapter_parses_tool_calls() -> None:
    client = OpenAIClient()
    completions = _Completions()
    client._clients[("test-key", None)] = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(completions=completions)
    )

    response = await client.complete(
        [{"role": "user", "content": "hi"}],
        [
            {
                "type": "function",
                "function": {"name": "get_room_history", "parameters": {}},
            }
        ],
        model="test-model",
        temperature=0.4,
        config=_config(),
    )

    assert response.content is None
    assert response.tool_calls[0].name == "get_room_history"
    assert response.tool_calls[0].arguments == '{"limit": 5}'
    assert response.input_tokens == 12
    assert response.output_tokens == 4
    assert completions.kwargs is not None
    assert completions.kwargs["tool_choice"] == "auto"
    assert completions.kwargs["model"] == "test-model"


async def test_openai_adapter_requires_key() -> None:
    client = OpenAIClient()
    with pytest.raises(LLMConfigurationError):
        await client.complete(
            [],
            [],
            model="test-model",
            temperature=0.4,
            config=_config(api_key=None),
        )
