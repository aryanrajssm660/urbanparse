"""
Application configuration — loaded from environment variables.
No secrets are hardcoded; all sensitive values come from .env.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Central configuration sourced from environment variables."""

    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # Database
    database_url: str = "sqlite:///./urbandash.db"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Limits
    max_address_length: int = 1000

    # Logging
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_claude_key(self) -> bool:
        return bool(self.anthropic_api_key and not self.anthropic_api_key.startswith("sk-ant-xxx"))

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
