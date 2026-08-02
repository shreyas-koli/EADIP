"""
Application configuration module.

Loads environment variables from a .env file and exposes them
as typed, validated attributes through a Pydantic Settings model.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the EADIP backend.

    All values are read from environment variables and / or the
    project-level ``.env`` file.  Pydantic validates types at
    startup so mis-configurations surface immediately.
    """

    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "EADIP"

    PROJECT_DESCRIPTION: str = (
    "Enterprise Autonomous Data Intelligence Platform"
)
    APP_VERSION: str = "1.0.0"

    # ── Authentication / JWT ─────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Database ─────────────────────────────────────────────────
    DEBUG: bool = True
    DATABASE_URL: str


    # ── Pydantic Settings v2 config ──────────────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()


# Module-level singleton for convenient imports:
#   from app.core.config import settings
settings: Settings = get_settings()
