"""
CareerMail AI — OpportunityStatusHistory model.

Tracks all status transitions for an opportunity (e.g., registered → shortlisted → next_round).
Retains link to the source email that triggered the transition.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.email_message import EmailMessage
    from app.models.opportunity import Opportunity


class OpportunityStatusHistory(Base):
    __tablename__ = "opportunity_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    source_email_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("email_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    opportunity: Mapped["Opportunity"] = relationship(
        "Opportunity", back_populates="status_history"
    )
    source_email: Mapped[Optional["EmailMessage"]] = relationship(
        "EmailMessage"
    )

    def __repr__(self) -> str:
        return (
            f"<OpportunityStatusHistory id={self.id} opp_id={self.opportunity_id} "
            f"{self.old_status} -> {self.new_status}>"
        )
