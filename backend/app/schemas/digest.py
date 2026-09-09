"""
CareerMail AI — Daily Digest Schemas.

Defines response models for the daily digest endpoint and push notification brief.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DigestCounts(BaseModel):
    """Counts summary for daily digest dashboard."""

    new_opportunities: int = 0
    status_changes: int = 0
    urgent_actions: int = 0
    deadlines_today: int = 0
    deadlines_tomorrow: int = 0
    deadlines_this_week: int = 0
    hackathon_updates: int = 0
    internship_updates: int = 0
    placement_updates: int = 0
    college_updates: int = 0


class DigestActionItem(BaseModel):
    """Urgent action item requiring student attention."""

    opportunity_id: int
    title: str
    organization: Optional[str] = None
    category: str
    action: str
    priority: str
    deadline: Optional[datetime] = None
    days_remaining: Optional[int] = None
    is_overdue: bool = False


class DigestStatusChangeItem(BaseModel):
    """Record of an opportunity progressing status today."""

    opportunity_id: int
    title: str
    organization: Optional[str] = None
    category: str
    old_status: str
    new_status: str
    round_name: Optional[str] = None
    changed_at: datetime


class DigestOpportunityItem(BaseModel):
    """Newly discovered opportunity in today's digest."""

    opportunity_id: int
    title: str
    organization: Optional[str] = None
    category: str
    status: str
    priority: str
    deadline: Optional[datetime] = None
    first_seen_at: datetime


class DigestDeadlineItem(BaseModel):
    """Upcoming deadline highlight for digest."""

    opportunity_id: int
    title: str
    organization: Optional[str] = None
    category: str
    deadline: datetime
    urgency_label: str  # e.g., "today", "tomorrow", "in 3 days"
    days_remaining: int


class DailyDigestResponse(BaseModel):
    """Comprehensive daily digest response."""

    generated_at: datetime
    target_date: str
    timezone: str
    summary: str
    summary_text: Optional[str] = None
    counts: DigestCounts
    urgent_actions: list[DigestActionItem] = Field(default_factory=list)
    recent_status_changes: list[DigestStatusChangeItem] = Field(default_factory=list)
    new_opportunities: list[DigestOpportunityItem] = Field(default_factory=list)
    upcoming_deadlines: list[DigestDeadlineItem] = Field(default_factory=list)
