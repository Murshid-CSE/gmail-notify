"""
CareerMail AI — Deadline API Schemas.

Defines response models for deadline groups (overdue, today, tomorrow,
this_week, later, no_deadline) and mobile card representations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DeadlineCardItem(BaseModel):
    """Opportunity summary tailored for mobile deadline cards."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    organization: Optional[str] = None
    category: str
    status: str
    deadline: Optional[datetime] = None
    priority: str
    action_required: bool = False
    action: Optional[str] = None
    days_remaining: Optional[int] = None
    hours_remaining: Optional[float] = None
    is_overdue: bool = False
    is_due_today: bool = False
    is_due_tomorrow: bool = False


class DeadlinesGroupedResponse(BaseModel):
    """Grouped deadlines for dashboard and deadline tracking views."""

    overdue: list[DeadlineCardItem] = Field(default_factory=list)
    today: list[DeadlineCardItem] = Field(default_factory=list)
    tomorrow: list[DeadlineCardItem] = Field(default_factory=list)
    this_week: list[DeadlineCardItem] = Field(default_factory=list)
    later: list[DeadlineCardItem] = Field(default_factory=list)
    no_deadline: list[DeadlineCardItem] = Field(default_factory=list)
    total_active: int = 0
