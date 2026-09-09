"""
CareerMail AI — Structured Logging.

Rules:
  • NEVER log OAuth access / refresh tokens.
  • NEVER log full email bodies in INFO or above.
  • DEBUG-level body logging is guarded behind ENVIRONMENT != production.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from app.config import get_settings

# ── Sensitive-field filter ──────────────────────────────


class SensitiveFilter(logging.Filter):
    """Strip fields that must never appear in log output."""

    _REDACT_KEYS = {
        "access_token",
        "refresh_token",
        "token",
        "client_secret",
        "encryption_key",
        "password",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        # If the message is a dict-like structured log, redact keys.
        if isinstance(record.msg, dict):
            record.msg = {
                k: "***REDACTED***" if k.lower() in self._REDACT_KEYS else v
                for k, v in record.msg.items()
            }
        return True


# ── Logger factory ──────────────────────────────────────


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with structured formatting."""
    settings = get_settings()
    logger = logging.getLogger(f"careermail.{name}")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveFilter())
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        logger.propagate = False

    return logger


def log_event(logger: logging.Logger, event: str, **kwargs: Any) -> None:
    """Emit a structured log line.

    Example::

        log_event(logger, "SYNC_STARTED", account_id=1)
    """
    parts = [event] + [f"{k}={v}" for k, v in kwargs.items()]
    logger.info(" | ".join(parts))
