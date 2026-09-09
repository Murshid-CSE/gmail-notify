"""
CareerMail AI — Opportunity model.

Represents a single deduplicated career opportunity (hackathon, internship, placement, college).
Maintains history of status transitions and references to all source emails.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.email_account import EmailAccount
    from app.models.email_message import EmailMessage
    from app.models.status_history import OpportunityStatusHistory
    from app.models.user import User


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Core classification & identity ───────────────────
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    organization: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Status tracking ──────────────────────────────────
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    round_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # ── Dates & deadlines ────────────────────────────────
    deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    event_date: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # ── Opportunity details ──────────────────────────────
    location: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    eligibility: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    apply_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Priority & confidence ────────────────────────────
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    # ── Source tracking ──────────────────────────────────
    source_account_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("email_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Timestamps ───────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────
    user: Mapped["User"] = relationship("User")
    source_account: Mapped[Optional["EmailAccount"]] = relationship("EmailAccount")

    status_history: Mapped[list["OpportunityStatusHistory"]] = relationship(
        "OpportunityStatusHistory",
        back_populates="opportunity",
        cascade="all, delete-orphan",
        order_by="OpportunityStatusHistory.changed_at.asc()",
    )

    emails: Mapped[list["EmailMessage"]] = relationship(
        "EmailMessage",
        secondary="opportunity_emails",
        back_populates="opportunities",
        order_by="EmailMessage.received_at.asc()",
    )

    def __repr__(self) -> str:
        return (
            f"<Opportunity id={self.id} category={self.category!r} "
            f"title={self.title!r} status={self.status!r}>"
        )
