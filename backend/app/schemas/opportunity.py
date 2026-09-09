"""
CareerMail AI — Opportunity API Schemas.

Defines Pydantic response models for opportunities, status history,
source email references, and deadline intelligence metrics.
Never exposes OAuth tokens or internal secrets.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceEmailReference(BaseModel):
    """Reference to an original Gmail message linked to an opportunity."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    gmail_message_id: str
    subject: str
    received_at: datetime
    sender: str


class StatusHistoryResponse(BaseModel):
    """Historical record of an opportunity's status transition."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    old_status: Optional[str] = None
    new_status: str
    source_email_id: Optional[int] = None
    changed_at: datetime


class OpportunityResponse(BaseModel):
    """Opportunity summary with computed deadline intelligence."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    title: str
    organization: Optional[str] = None
    description: Optional[str] = None
    status: str
    round_name: Optional[str] = None
    deadline: Optional[datetime] = None
    event_date: Optional[str] = None
    location: Optional[str] = None
    eligibility: Optional[str] = None
    apply_url: Optional[str] = None
    event_url: Optional[str] = None
    action_required: bool = False
    action: Optional[str] = None
    priority: str
    confidence: float
    first_seen_at: datetime
    last_updated_at: datetime

    # Computed deadline metrics
    days_remaining: Optional[int] = None
    hours_remaining: Optional[float] = None
    is_overdue: bool = False
    is_due_today: bool = False
    is_due_tomorrow: bool = False


class OpportunityDetailResponse(OpportunityResponse):
    """Detailed opportunity view including source emails and full status history."""

    source_emails: list[SourceEmailReference] = Field(default_factory=list)
    status_history: list[StatusHistoryResponse] = Field(default_factory=list)
