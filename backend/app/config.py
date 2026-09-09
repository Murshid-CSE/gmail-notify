"""
CareerMail AI — Application Configuration.

Reads all settings from environment variables / .env file.
Never stores secrets in code.
"""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict



_backend_dir = Path(__file__).resolve().parent.parent
_root_dir = _backend_dir.parent


class Settings(BaseSettings):
    """Central configuration loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=(
            str(_root_dir / ".env"),
            str(_backend_dir / ".env"),
            ".env",
        ),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Google OAuth 2.0 ──────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # ── Database ──────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./careermail.db"

    # ── Encryption ────────────────────────────────────────
    # Fernet key for encrypting OAuth tokens at rest.
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = ""

    # ── Application ───────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ── Gmail Sync ────────────────────────────────────────
    MAX_SYNC_MESSAGES: int = 500

    # ── AI Providers (Milestone 2 & Multi-Provider Architecture) ──
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"

    HUGGINGFACE_API_KEY: str = ""
    HUGGINGFACE_MODEL: str = "meta-llama/Llama-3.3-70B-Instruct"

    AI_PRIMARY_PROVIDER: str = "gemini"
    AI_FALLBACK_PROVIDERS: str = "groq,openrouter,huggingface"

    # ── Firebase (Milestone 6) ────────────────────────────
    FIREBASE_CREDENTIALS_PATH: str = ""
    FCM_ENABLED: bool = True
    NOTIFICATION_COOLDOWN_MINUTES: int = 360  # 6-hour default cooldown window

    # ── Timezone ──────────────────────────────────────────
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"

    # ── Scheduler (Milestone 7) ───────────────────────────
    SCHEDULER_ENABLED: bool = True
    SYNC_INTERVAL_MINUTES: int = 15
    DAILY_DIGEST_HOUR: int = 8
    DAILY_DIGEST_MINUTE: int = 0

    # ── Configuration Validators ──────────────────────────

    @field_validator("SYNC_INTERVAL_MINUTES")
    @classmethod
    def validate_sync_interval(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("SYNC_INTERVAL_MINUTES must be greater than 0")
        return v

    @field_validator("DAILY_DIGEST_HOUR")
    @classmethod
    def validate_digest_hour(cls, v: int) -> int:
        if not (0 <= v <= 23):
            raise ValueError("DAILY_DIGEST_HOUR must be between 0 and 23")
        return v

    @field_validator("DAILY_DIGEST_MINUTE")
    @classmethod
    def validate_digest_minute(cls, v: int) -> int:
        if not (0 <= v <= 59):
            raise ValueError("DAILY_DIGEST_MINUTE must be between 0 and 59")
        return v

    @field_validator("DEFAULT_TIMEZONE")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
            return v
        except Exception:
            raise ValueError(f"Invalid DEFAULT_TIMEZONE: {v!r}")

    # ── Derived helpers ───────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    @property
    def encryption_configured(self) -> bool:
        return bool(self.ENCRYPTION_KEY)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.GEMINI_API_KEY)

    @property
    def groq_configured(self) -> bool:
        return bool(self.GROQ_API_KEY)

    @property
    def openrouter_configured(self) -> bool:
        return bool(self.OPENROUTER_API_KEY)

    @property
    def huggingface_configured(self) -> bool:
        return bool(self.HUGGINGFACE_API_KEY)

    @property
    def ai_configured(self) -> bool:
        """Check if at least one AI provider is configured."""
        return (
            self.gemini_configured
            or self.groq_configured
            or self.openrouter_configured
            or self.huggingface_configured
        )

    def is_provider_configured(self, provider_name: str) -> bool:
        """Check whether a named provider is configured with credentials."""
        p = provider_name.strip().lower()
        if p == "gemini":
            return self.gemini_configured
        if p == "groq":
            return self.groq_configured
        if p == "openrouter":
            return self.openrouter_configured
        if p in ("huggingface", "hf"):
            return self.huggingface_configured
        return False

    def get_configured_ai_providers(self) -> list[str]:
        """Return the list of providers in configured priority order that have valid API keys."""
        chain: list[str] = []
        if self.AI_PRIMARY_PROVIDER:
            p = self.AI_PRIMARY_PROVIDER.strip().lower()
            if p and p not in chain:
                chain.append(p)
        if self.AI_FALLBACK_PROVIDERS:
            for item in self.AI_FALLBACK_PROVIDERS.split(","):
                p = item.strip().lower()
                if p and p not in chain:
                    chain.append(p)
        return [p for p in chain if self.is_provider_configured(p)]

    @property
    def firebase_configured(self) -> bool:
        """Check if real Firebase credentials exist on disk and FCM is enabled."""
        if not self.FCM_ENABLED or not self.FIREBASE_CREDENTIALS_PATH:
            return False
        return Path(self.FIREBASE_CREDENTIALS_PATH).is_file()

    @property
    def scheduler_active(self) -> bool:
        """Check if scheduler should actively run.
        Disabled if SCHEDULER_ENABLED is False or ENVIRONMENT is 'test'.
        """
        if not self.SCHEDULER_ENABLED:
            return False
        if self.ENVIRONMENT.lower() == "test":
            return False
        return True


    def require_google_oauth(self) -> None:
        """Raise if Google OAuth is not configured."""
        if not self.google_oauth_configured:
            raise RuntimeError(
                "Google OAuth is not configured. "
                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
            )

    def require_encryption(self) -> None:
        """Raise if encryption key is not configured."""
        if not self.encryption_configured:
            raise RuntimeError(
                "ENCRYPTION_KEY is not configured. "
                'Generate one: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )


def get_settings() -> Settings:
    """Return application settings (cached per-process via module-level)."""
    return _settings


# Module-level singleton so Settings is only parsed once.
_settings = Settings()
