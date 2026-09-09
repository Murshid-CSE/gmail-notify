"""
CareerMail AI — OpportunityEmail association model.

Links opportunities to their source email messages (many-to-many).
Retains explicit link between every opportunity and all related Gmail emails.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OpportunityEmail(Base):
    __tablename__ = "opportunity_emails"

    __table_args__ = (
        UniqueConstraint("opportunity_id", "email_id", name="uq_opportunity_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<OpportunityEmail opp_id={self.opportunity_id} email_id={self.email_id}>"
