from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Chat Room"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_prefix: str = "/api"
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    data_dir: Path = Path("data")
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    default_user_name: str = "demo"
    default_user_display_name: str = "Demo User"

    llm_provider: Literal["openai"] = "openai"
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_model: str = "deepseek-v4.1-flash"

    agent_max_steps: int = 8
    agent_max_context_chars: int = 16_000
    agent_max_depth: int = 3
    agent_max_tasks_per_root: int = 24
    agent_reply_max_chars: int = 16_000
    tool_timeout_seconds: float = 20.0
    tool_result_max_chars: int = 8_000
    fetch_max_bytes: int = 100_000
    room_history_limit: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
