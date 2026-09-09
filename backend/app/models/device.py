"""
CareerMail AI — Device Token model.

Stores registered FCM device tokens for push notifications.
Supports idempotent registration, reactivation, and deactivation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeviceToken(Base):
    """Registered client device token for Firebase Cloud Messaging (FCM)."""

    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fcm_token: Mapped[str] = mapped_column(
        String(512),
        unique=True,
        nullable=False,
        index=True,
    )
    device_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="android",
    )  # "android", "ios", "web"
    device_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="device_tokens")

    __table_args__ = (
        Index("ix_device_tokens_user_active", "user_id", "is_active"),
    )

    def __repr__(self) -> str:
        snippet = self.fcm_token[:10] + "..." if len(self.fcm_token) > 10 else self.fcm_token
        return (
            f"<DeviceToken id={self.id} user_id={self.user_id} "
            f"type={self.device_type} active={self.is_active} token={snippet}>"
        )
