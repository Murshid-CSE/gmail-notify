"""
Tests for application configuration.
"""

import os
import pytest


def test_settings_loads_from_env():
    """Settings reads environment variables correctly."""
    from app.config import Settings

    settings = Settings(
        GOOGLE_CLIENT_ID="test-id",
        GOOGLE_CLIENT_SECRET="test-secret",
        DATABASE_URL="sqlite:///:memory:",
        ENCRYPTION_KEY="test-key",
    )
    assert settings.GOOGLE_CLIENT_ID == "test-id"
    assert settings.google_oauth_configured is True


def test_settings_detects_missing_oauth():
    """Settings correctly reports unconfigured OAuth."""
    settings = _make_settings(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
    assert settings.google_oauth_configured is False


def test_settings_detects_missing_encryption():
    """Settings correctly reports unconfigured encryption."""
    settings = _make_settings(ENCRYPTION_KEY="")
    assert settings.encryption_configured is False


def test_require_google_oauth_raises():
    """require_google_oauth raises RuntimeError when not configured."""
    settings = _make_settings(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
    with pytest.raises(RuntimeError, match="Google OAuth is not configured"):
        settings.require_google_oauth()


def test_require_encryption_raises():
    """require_encryption raises RuntimeError when not configured."""
    settings = _make_settings(ENCRYPTION_KEY="")
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY is not configured"):
        settings.require_encryption()


def test_is_production():
    """is_production flag based on ENVIRONMENT."""
    settings = _make_settings(ENVIRONMENT="production")
    assert settings.is_production is True

    settings = _make_settings(ENVIRONMENT="development")
    assert settings.is_production is False


def _make_settings(**overrides):
    """Helper to create Settings with overrides."""
    from app.config import Settings

    defaults = {
        "GOOGLE_CLIENT_ID": "test-id",
        "GOOGLE_CLIENT_SECRET": "test-secret",
        "DATABASE_URL": "sqlite:///:memory:",
        "ENCRYPTION_KEY": "test-key",
    }
    defaults.update(overrides)
    return Settings(**defaults)
