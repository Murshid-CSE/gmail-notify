"""
CareerMail AI — EmailAccount model.

Represents a connected Gmail account.
Tokens are stored encrypted (Fernet).
Supports two independent accounts per user.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    String,
    DateTime,
    Integer,
    BigInteger,
    Boolean,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Provider info — extensible for Outlook/Yahoo later.
    provider: Mapped[str] = mapped_column(String(50), default="gmail")
    email_address: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)

    # OAuth tokens — encrypted at rest.
    encrypted_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encrypted_refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Sync state.
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Gmail history ID for incremental sync.
    history_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="email_accounts")
    messages: Mapped[list["EmailMessage"]] = relationship(
        "EmailMessage", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EmailAccount id={self.id} email={self.email_address!r} provider={self.provider!r}>"
