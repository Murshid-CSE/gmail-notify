"""
CareerMail AI — EmailAccount API schemas.

Never expose tokens or encrypted data through API responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AccountResponse(BaseModel):
    """Public account info — NO tokens, NO secrets."""

    id: int
    email_address: str
    provider: str
    is_active: bool
    last_sync_at: Optional[datetime] = None
    message_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountListResponse(BaseModel):
    """Response for GET /accounts."""

    accounts: list[AccountResponse]
    total: int


class OAuthStartResponse(BaseModel):
    """Response for GET /auth/google/start."""

    authorization_url: str
    message: str = "Open this URL in your browser to connect your Gmail account."


class SyncResponse(BaseModel):
    """Response for POST /accounts/{id}/sync."""

    account_id: int
    email_address: str
    new_messages: int = 0
    skipped_duplicates: int = 0
    total_messages_in_db: int = 0
    sync_duration_seconds: float = 0.0
    message: str = ""
