"""
CareerMail AI — Deadlines API Routes.

GET /deadlines — Returns opportunities grouped by deadline urgency:
  • overdue
  • today
  • tomorrow
  • this_week
  • later
  • no_deadline
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.opportunity import Opportunity
from app.schemas.deadline import DeadlineCardItem, DeadlinesGroupedResponse
from app.utils.logging import get_logger

logger = get_logger("api.deadlines")

router = APIRouter(prefix="/deadlines", tags=["deadlines"])


def get_user_timezone(tz_name: Optional[str] = None) -> ZoneInfo:
    """Resolve user timezone from query param, app config, or fallback to UTC."""
    settings = get_settings()
    candidate = tz_name or settings.DEFAULT_TIMEZONE or "Asia/Kolkata"
    try:
        return ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("INVALID_TIMEZONE | tz=%s | falling back to UTC", candidate)
        return ZoneInfo("UTC")


def _build_deadline_card_item(opp: Opportunity, now_user: datetime) -> DeadlineCardItem:
    """Construct DeadlineCardItem with timezone-aware derived metrics."""
    if opp.deadline is None:
        return DeadlineCardItem(
            id=opp.id,
            title=opp.title,
            organization=opp.organization,
            category=opp.category,
            status=opp.status,
            deadline=None,
            priority=opp.priority,
            action_required=getattr(opp, "action_required", False),
            action=getattr(opp, "action", None),
            days_remaining=None,
            hours_remaining=None,
            is_overdue=False,
            is_due_today=False,
            is_due_tomorrow=False,
        )

    # Ensure deadline is timezone-aware and converted to user timezone
    dl_user = opp.deadline
    if dl_user.tzinfo is None:
        dl_user = dl_user.replace(tzinfo=timezone.utc)
    dl_user = dl_user.astimezone(now_user.tzinfo)

    diff = dl_user - now_user
    total_seconds = diff.total_seconds()
    is_overdue = total_seconds < 0

    hours_remaining = round(total_seconds / 3600.0, 1)
    days_remaining = int(total_seconds // 86400)

    deadline_date = dl_user.date()
    now_date = now_user.date()
    tomorrow_date = now_date + timedelta(days=1)

    is_due_today = (deadline_date == now_date) and not is_overdue
    is_due_tomorrow = deadline_date == tomorrow_date

    return DeadlineCardItem(
        id=opp.id,
        title=opp.title,
        organization=opp.organization,
        category=opp.category,
        status=opp.status,
        deadline=dl_user,
        priority=opp.priority,
        action_required=getattr(opp, "action_required", False),
        action=getattr(opp, "action", None),
        days_remaining=days_remaining,
        hours_remaining=hours_remaining,
        is_overdue=is_overdue,
        is_due_today=is_due_today,
        is_due_tomorrow=is_due_tomorrow,
    )


@router.get("", response_model=DeadlinesGroupedResponse)
def get_deadlines(
    category: Optional[str] = Query(None, description="Filter by category (hackathon, internship, etc.)"),
    tz: Optional[str] = Query(None, description="User timezone (e.g. Asia/Kolkata, America/New_York)"),
    db: Session = Depends(get_db),
):
    """Retrieve opportunities grouped into overdue, today, tomorrow, this_week, later, no_deadline."""
    user_tz = get_user_timezone(tz)
    now_user = datetime.now(user_tz)
    today_date = now_user.date()
    tomorrow_date = today_date + timedelta(days=1)
    # End of current week (Sunday) or at least 7 days out
    days_until_sunday = 6 - today_date.weekday()
    if days_until_sunday < 2:  # Friday/Saturday/Sunday: look through end of next week
        days_until_sunday += 7
    week_end_date = today_date + timedelta(days=days_until_sunday)

    query = db.query(Opportunity)
    if category:
        query = query.filter(Opportunity.category == category)

    opportunities = query.all()

    overdue_items = []
    today_items = []
    tomorrow_items = []
    this_week_items = []
    later_items = []
    no_deadline_items = []

    for opp in opportunities:
        card = _build_deadline_card_item(opp, now_user)

        if opp.deadline is None:
            no_deadline_items.append(card)
            continue

        dl_user = opp.deadline
        if dl_user.tzinfo is None:
            dl_user = dl_user.replace(tzinfo=timezone.utc)
        dl_user = dl_user.astimezone(user_tz)

        # 1. Overdue: deadline has passed
        if (dl_user - now_user).total_seconds() < 0:
            overdue_items.append(card)
        # 2. Today: deadline date is today and not overdue
        elif dl_user.date() == today_date:
            today_items.append(card)
        # 3. Tomorrow: deadline date is tomorrow
        elif dl_user.date() == tomorrow_date:
            tomorrow_items.append(card)
        # 4. This week: between day after tomorrow and week_end_date
        elif tomorrow_date < dl_user.date() <= week_end_date:
            this_week_items.append(card)
        # 5. Later: beyond this week
        else:
            later_items.append(card)

    # Sort groups by deadline proximity
    overdue_items.sort(key=lambda x: x.deadline or datetime.max.replace(tzinfo=timezone.utc))
    today_items.sort(key=lambda x: x.deadline or datetime.max.replace(tzinfo=timezone.utc))
    tomorrow_items.sort(key=lambda x: x.deadline or datetime.max.replace(tzinfo=timezone.utc))
    this_week_items.sort(key=lambda x: x.deadline or datetime.max.replace(tzinfo=timezone.utc))
    later_items.sort(key=lambda x: x.deadline or datetime.max.replace(tzinfo=timezone.utc))

    total_active = len(overdue_items) + len(today_items) + len(tomorrow_items) + len(this_week_items) + len(later_items)

    return DeadlinesGroupedResponse(
        overdue=overdue_items,
        today=today_items,
        tomorrow=tomorrow_items,
        this_week=this_week_items,
        later=later_items,
        no_deadline=no_deadline_items,
        total_active=total_active,
    )
