"""
CareerMail AI — EmailMessage model.

Stores fetched Gmail messages with unique constraint on gmail_message_id.
Retains source account, original headers, and parsed body.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.opportunity import Opportunity

from sqlalchemy import (
    String,
    DateTime,
    Integer,
    Boolean,
    ForeignKey,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EmailMessage(Base):
    __tablename__ = "email_messages"

    # Ensure we never store the same Gmail message twice.
    __table_args__ = (
        UniqueConstraint("gmail_message_id", "account_id", name="uq_gmail_msg_account"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("email_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Gmail identifiers ────────────────────────────────
    gmail_message_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    gmail_thread_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # ── Headers ──────────────────────────────────────────
    sender: Mapped[str] = mapped_column(String(512), nullable=False)
    recipients: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list
    subject: Mapped[str] = mapped_column(String(1024), default="(no subject)")

    # ── Timestamps ───────────────────────────────────────
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # ── Body ─────────────────────────────────────────────
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Labels ───────────────────────────────────────────
    labels: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list

    # ── Processing pipeline state ────────────────────────
    # pending → filtered_out | pending_extraction | extracted | extraction_failed
    processing_status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )
    is_relevant: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # ── Metadata ─────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    account: Mapped["EmailAccount"] = relationship(
        "EmailAccount", back_populates="messages"
    )
    opportunities: Mapped[list["Opportunity"]] = relationship(
        "Opportunity",
        secondary="opportunity_emails",
        back_populates="emails",
    )

    def __repr__(self) -> str:
        return (
            f"<EmailMessage id={self.id} gmail_id={self.gmail_message_id!r} "
            f"subject={self.subject!r}>"
        )
