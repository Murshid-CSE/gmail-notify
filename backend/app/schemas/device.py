"""
CareerMail AI — Device Schemas.

Pydantic models for FCM device registration, listing, and deactivation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


DevicePlatform = Literal["android", "ios", "web"]


class DeviceRegisterRequest(BaseModel):
    """Payload to register or reactivate an FCM device token."""

    fcm_token: str = Field(..., min_length=1, max_length=512, description="Firebase Cloud Messaging token")
    device_type: DevicePlatform = Field(default="android", description="Platform type: android, ios, or web")
    device_name: Optional[str] = Field(None, max_length=100, description="Human-readable device name")


class DeviceResponse(BaseModel):
    """Device registration representation."""

    id: int
    user_id: int
    device_type: str
    device_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_seen_at: datetime
    fcm_token_snippet: str = Field(..., description="Truncated token for identification without full secret exposure")

    @classmethod
    def from_orm_model(cls, obj) -> "DeviceResponse":
        snippet = obj.fcm_token[:12] + "..." if len(obj.fcm_token) > 12 else obj.fcm_token
        return cls(
            id=obj.id,
            user_id=obj.user_id,
            device_type=obj.device_type,
            device_name=obj.device_name,
            is_active=obj.is_active,
            created_at=obj.created_at,
            last_seen_at=obj.last_seen_at,
            fcm_token_snippet=snippet,
        )


class DeviceListResponse(BaseModel):
    """List of registered devices for the user."""

    devices: list[DeviceResponse]
    total: int
