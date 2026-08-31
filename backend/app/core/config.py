"""
Application configuration module.

Loads environment variables from a .env file and exposes them
as typed, validated attributes through a Pydantic Settings model.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


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

    # ── CORS ─────────────────────────────────────────────────────
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://eadip.onrender.com",
    ]

    # ── Authentication / JWT ─────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Security / Encryption ────────────────────────────────────
    ENCRYPTION_KEY: str

    # ── Database ─────────────────────────────────────────────────
    DEBUG: bool = True
    DATABASE_URL: str
    
    # Optional dedicated PostgreSQL connection string for integration tests.
    # E.g., postgresql://user:password@localhost:5432/aadw_test
    TEST_DATABASE_URL: str | None = None

    # ── Recommendation Thresholds ────────────────────────────────
    REC_LARGE_TABLE_ROWS: int = 100000
    REC_WIDE_TABLE_COLS: int = 50
    REC_EMPTY_TABLE_ROWS: int = 0
    REC_NULLABLE_COLUMN_PCT: float = 0.5

    # ── Monitoring Thresholds ────────────────────────────────────
    """
    Monitoring Agent runtime thresholds.
    These define what constitutes a warning or critical finding when analyzing
    PostgreSQL runtime state (pg_stat_activity, pg_locks, etc.)
    """
    MONITORING_LONG_RUNNING_QUERY_SECONDS: int = Field(default=5, ge=0)
    MONITORING_LONG_RUNNING_TRANSACTION_SECONDS: int = Field(default=30, ge=0)
    MONITORING_CONNECTION_WARNING_PERCENT: float = Field(default=75.0, ge=0.0, le=100.0)
    MONITORING_CONNECTION_CRITICAL_PERCENT: float = Field(default=90.0, ge=0.0, le=100.0)
    MONITORING_BLOCKING_QUERY_THRESHOLD: int = Field(default=1, ge=0)
    MONITORING_IDLE_IN_TRANSACTION_THRESHOLD: int = Field(default=1, ge=0)
    MONITORING_CACHE_HIT_WARNING_PERCENT: float = Field(default=90.0, ge=0.0, le=100.0)
    
    # ── Host / System Monitoring Thresholds ──────────────────────
    MONITORING_CPU_WARNING_PERCENT: float = Field(default=80.0, ge=0.0, le=100.0)
    MONITORING_CPU_CRITICAL_PERCENT: float = Field(default=95.0, ge=0.0, le=100.0)
    
    MONITORING_MEMORY_WARNING_PERCENT: float = Field(default=85.0, ge=0.0, le=100.0)
    MONITORING_MEMORY_CRITICAL_PERCENT: float = Field(default=95.0, ge=0.0, le=100.0)
    MONITORING_SWAP_WARNING_PERCENT: float = Field(default=50.0, ge=0.0, le=100.0)
    MONITORING_SWAP_CRITICAL_PERCENT: float = Field(default=80.0, ge=0.0, le=100.0)
    
    MONITORING_DISK_CAPACITY_WARNING_PERCENT: float = Field(default=85.0, ge=0.0, le=100.0)
    MONITORING_DISK_CAPACITY_CRITICAL_PERCENT: float = Field(default=95.0, ge=0.0, le=100.0)
    # Generic I/O activity thresholds (Bytes per second)
    MONITORING_DISK_IO_READ_MB_S_WARNING: float = Field(default=100.0, ge=0.0)
    MONITORING_DISK_IO_WRITE_MB_S_WARNING: float = Field(default=100.0, ge=0.0)
    
    MONITORING_NETWORK_ERRORS_WARNING: int = Field(default=1, ge=0)
    MONITORING_NETWORK_DROPS_WARNING: int = Field(default=1, ge=0)
    
    MONITORING_PROCESS_CPU_WARNING_PERCENT: float = Field(default=80.0, ge=0.0)
    MONITORING_PROCESS_MEMORY_WARNING_MB: float = Field(default=1024.0, ge=0.0)


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
