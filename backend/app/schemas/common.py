"""
CareerMail AI — Common / shared Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class HealthResponse(BaseModel):
    """GET /health response."""

    status: str = "ok"
    environment: str
    google_oauth_configured: bool
    encryption_configured: bool
    gemini_configured: bool = False
    firebase_configured: bool = False
    scheduler_active: bool = False
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    detail: str
    error_code: Optional[str] = None


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_next: bool
    has_previous: bool


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    pagination: PaginationMeta
