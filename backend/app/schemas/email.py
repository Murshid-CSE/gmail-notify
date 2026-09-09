"""
CareerMail AI — Email API schemas.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EmailResponse(BaseModel):
    """Compact email for list views."""

    id: int
    gmail_message_id: str
    gmail_thread_id: str
    account_id: int
    sender: str
    subject: str
    received_at: datetime
    processing_status: str
    is_relevant: Optional[bool] = None
    labels: Optional[list[str]] = None

    model_config = {"from_attributes": True}

    @field_validator("labels", mode="before")
    @classmethod
    def parse_labels(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v


class EmailDetailResponse(BaseModel):
    """Full email detail — includes body for single-email view."""

    id: int
    gmail_message_id: str
    gmail_thread_id: str
    account_id: int
    sender: str
    recipients: Optional[list[str]] = None
    subject: str
    received_at: datetime
    body_text: Optional[str] = None
    labels: Optional[list[str]] = None
    processing_status: str
    is_relevant: Optional[bool] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("labels", mode="before")
    @classmethod
    def parse_labels(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v

    @field_validator("recipients", mode="before")
    @classmethod
    def parse_recipients(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v


class EmailListResponse(BaseModel):
    """Paginated email list."""

    items: list[EmailResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool
