from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "My FastAPI App"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # API Keys
    OPENROUTER_API_KEY: str | None = None

    # Custom
    ENV: str = "dev"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Cached instance (default usage)
@lru_cache
def get_settings() -> Settings:
    return Settings()


# 🔥 Reload function (bypass cache)
def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()