"""
CareerMail AI — Notification Schemas.

Pydantic models for sending test notifications, querying history, and tracking statuses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


NotificationType = Literal["status_change", "urgent_action", "deadline", "digest", "test"]
NotificationStatus = Literal["sent", "mock_sent", "failed"]


class TestNotificationRequest(BaseModel):
    """Payload to trigger an on-demand test notification."""

    title: Optional[str] = Field(default="CareerMail AI Test", max_length=255)
    body: Optional[str] = Field(
        default="This is a test notification from CareerMail AI. Push notifications are working!",
    )
    opportunity_id: Optional[int] = Field(
        default=None,
        description="Optional opportunity ID to link in notification data payload",
    )


class NotificationSendResult(BaseModel):
    """Result of dispatching a push notification."""

    success: bool
    status: NotificationStatus
    recipient_count: int
    message_id: Optional[str] = None
    detail: str


class NotificationLogResponse(BaseModel):
    """Record of a sent or simulated push notification."""

    id: int
    user_id: int
    opportunity_id: Optional[int] = None
    notification_type: str
    title: str
    body: str
    data_payload: dict[str, Any]
    status: str
    fcm_message_id: Optional[str] = None
    created_at: datetime


class NotificationHistoryResponse(BaseModel):
    """Paginated list of historical notifications."""

    items: list[NotificationLogResponse]
    total: int
    page: int
    page_size: int
