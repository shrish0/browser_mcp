from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "My FastAPI App"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    PRIMARY_MODEL: str = "qwen/qwen3.6-plus:free"
    FALLBACK_MODEL: str = "openai/gpt-4o"

    # API Keys
    OPENROUTER_API_KEY: str = "enter_your_openrouter_api_key_here"
    OPENROUTER_API_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_HTTP_REFERER: str = ""
    OPENROUTER_TITLE: str = "Browser MCP"
    OPENROUTER_REQUEST_TIMEOUT: int = 30

    # Custom
    ENV: str = "dev"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


# Cached instance (default usage)
@lru_cache
def get_settings() -> Settings:
    return Settings()


# 🔥 Reload function (bypass cache)
def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
