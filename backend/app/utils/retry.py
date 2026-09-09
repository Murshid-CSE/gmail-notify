"""
CareerMail AI — Retry with Exponential Backoff.

For transient failures in external APIs (Gmail, Gemini, FCM).
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable, Sequence, Type

from app.utils.logging import get_logger

logger = get_logger("retry")


def retry_with_backoff(
    max_retries: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Sequence[Type[Exception]] = (Exception,),
) -> Callable:
    """Decorator that retries a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay between retries.
        backoff_factor: Multiplier applied to delay after each retry.
        retryable_exceptions: Tuple of exception types to retry on.

    Example::

        @retry_with_backoff(max_retries=3, retryable_exceptions=(ConnectionError,))
        def call_gmail_api():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            last_exception: Exception | None = None

            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except tuple(retryable_exceptions) as exc:
                    last_exception = exc
                    if attempt == max_retries:
                        logger.error(
                            "RETRY_EXHAUSTED | func=%s | attempts=%d | error=%s",
                            func.__name__,
                            attempt,
                            str(exc),
                        )
                        raise

                    logger.warning(
                        "RETRY_ATTEMPT | func=%s | attempt=%d/%d | delay=%.1fs | error=%s",
                        func.__name__,
                        attempt,
                        max_retries,
                        delay,
                        str(exc),
                    )
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)

            # Should not reach here, but satisfy type checker.
            if last_exception:
                raise last_exception

        return wrapper

    return decorator
