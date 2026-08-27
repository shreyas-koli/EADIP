"""
Configuration tests for EADIP backend settings.
"""

import os
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_monitoring_settings():
    """Verify that default monitoring settings are set correctly."""
    # Ensure environment variables are not interfering with defaults
    env_keys = [
        "MONITORING_LONG_RUNNING_QUERY_SECONDS",
        "MONITORING_LONG_RUNNING_TRANSACTION_SECONDS",
        "MONITORING_CONNECTION_WARNING_PERCENT",
        "MONITORING_CONNECTION_CRITICAL_PERCENT",
        "MONITORING_BLOCKING_QUERY_THRESHOLD",
        "MONITORING_IDLE_IN_TRANSACTION_THRESHOLD",
        "MONITORING_CACHE_HIT_WARNING_PERCENT",
    ]
    for key in env_keys:
        if key in os.environ:
            del os.environ[key]

    # Required fields for Settings model to instantiate
    os.environ["SECRET_KEY"] = "test_secret"
    os.environ["ENCRYPTION_KEY"] = "test_encryption_key_must_be_32_bytes_long_or_more"
    os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

    settings = Settings()

    assert settings.MONITORING_LONG_RUNNING_QUERY_SECONDS == 5
    assert settings.MONITORING_LONG_RUNNING_TRANSACTION_SECONDS == 30
    assert settings.MONITORING_CONNECTION_WARNING_PERCENT == 75.0
    assert settings.MONITORING_CONNECTION_CRITICAL_PERCENT == 90.0
    assert settings.MONITORING_BLOCKING_QUERY_THRESHOLD == 1
    assert settings.MONITORING_IDLE_IN_TRANSACTION_THRESHOLD == 1
    assert settings.MONITORING_CACHE_HIT_WARNING_PERCENT == 90.0

    # Cleanup
    for key in ["SECRET_KEY", "ENCRYPTION_KEY", "DATABASE_URL"]:
        if key in os.environ:
            del os.environ[key]


def test_env_override_monitoring_settings():
    """Verify that environment variables can override the defaults."""
    os.environ["SECRET_KEY"] = "test_secret"
    os.environ["ENCRYPTION_KEY"] = "test_encryption_key"
    os.environ["DATABASE_URL"] = "postgresql://test"

    os.environ["MONITORING_LONG_RUNNING_QUERY_SECONDS"] = "10"
    os.environ["MONITORING_CONNECTION_WARNING_PERCENT"] = "80.5"

    settings = Settings()

    assert settings.MONITORING_LONG_RUNNING_QUERY_SECONDS == 10
    assert settings.MONITORING_CONNECTION_WARNING_PERCENT == 80.5

    # Cleanup
    for key in [
        "SECRET_KEY",
        "ENCRYPTION_KEY",
        "DATABASE_URL",
        "MONITORING_LONG_RUNNING_QUERY_SECONDS",
        "MONITORING_CONNECTION_WARNING_PERCENT",
    ]:
        if key in os.environ:
            del os.environ[key]


def test_invalid_percentage_rejected():
    """Verify that invalid percentages are rejected by Pydantic."""
    os.environ["SECRET_KEY"] = "test_secret"
    os.environ["ENCRYPTION_KEY"] = "test_encryption_key"
    os.environ["DATABASE_URL"] = "postgresql://test"

    os.environ["MONITORING_CONNECTION_WARNING_PERCENT"] = "150.0"  # Invalid, must be <= 100

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "Input should be less than or equal to 100" in str(exc_info.value)

    os.environ["MONITORING_CONNECTION_WARNING_PERCENT"] = "-10.0"  # Invalid, must be >= 0

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "Input should be greater than or equal to 0" in str(exc_info.value)

    # Cleanup
    for key in [
        "SECRET_KEY",
        "ENCRYPTION_KEY",
        "DATABASE_URL",
        "MONITORING_CONNECTION_WARNING_PERCENT",
    ]:
        if key in os.environ:
            del os.environ[key]


def test_negative_durations_rejected():
    """Verify that negative counts/durations are rejected."""
    os.environ["SECRET_KEY"] = "test_secret"
    os.environ["ENCRYPTION_KEY"] = "test_encryption_key"
    os.environ["DATABASE_URL"] = "postgresql://test"

    os.environ["MONITORING_LONG_RUNNING_QUERY_SECONDS"] = "-5"

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "Input should be greater than or equal to 0" in str(exc_info.value)

    # Cleanup
    for key in [
        "SECRET_KEY",
        "ENCRYPTION_KEY",
        "DATABASE_URL",
        "MONITORING_LONG_RUNNING_QUERY_SECONDS",
    ]:
        if key in os.environ:
            del os.environ[key]

