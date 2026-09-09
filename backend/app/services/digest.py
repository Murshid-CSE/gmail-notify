"""
CareerMail AI — Daily Digest Service.

Aggregates daily career briefing metrics:
  • New opportunities discovered today
  • Status transitions that occurred today
  • Urgent actions requiring attention
  • Deadlines today, tomorrow, and this week
  • Category updates breakdown
  • Deterministic human-readable brief for mobile push notifications
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.opportunity import Opportunity
from app.models.status_history import OpportunityStatusHistory
from app.schemas.digest import (
    DailyDigestResponse,
    DigestActionItem,
    DigestCounts,
    DigestDeadlineItem,
    DigestOpportunityItem,
    DigestStatusChangeItem,
)
from app.utils.logging import get_logger

logger = get_logger("services.digest")

PRIORITY_WEIGHT = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def get_user_timezone(tz_name: Optional[str] = None) -> ZoneInfo:
    """Resolve user timezone from argument, config, or fallback to UTC."""
    settings = get_settings()
    candidate = tz_name or settings.DEFAULT_TIMEZONE or "Asia/Kolkata"
    try:
        return ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("INVALID_TIMEZONE | tz=%s | falling back to UTC", candidate)
        return ZoneInfo("UTC")


def _format_human_readable_brief(
    target_date: date,
    counts: DigestCounts,
    urgent_actions: list[DigestActionItem],
    status_changes: list[DigestStatusChangeItem],
    new_opps: list[DigestOpportunityItem],
    deadlines: list[DigestDeadlineItem],
) -> str:
    """Generate a clean, deterministic summary text without calling LLMs."""
    total_updates = (
        counts.new_opportunities
        + counts.status_changes
        + counts.deadlines_today
        + counts.deadlines_tomorrow
    )

    if total_updates == 0 and len(urgent_actions) == 0:
        return (
            "YOUR DAILY CAREER BRIEF\n\n"
            f"Date: {target_date.strftime('%A, %b %d, %Y')}\n"
            "No pending actions or urgent updates for today. You are all caught up!"
        )

    lines: list[str] = ["YOUR DAILY CAREER BRIEF"]
    lines.append(f"Date: {target_date.strftime('%A, %b %d, %Y')}")
    lines.append("")

    if counts.urgent_actions > 0:
        lines.append(f"⚠️  {counts.urgent_actions} urgent action{'s' if counts.urgent_actions > 1 else ''} needing attention")
        lines.append("")

    # 1. Urgent Actions
    if urgent_actions:
        lines.append("ACTION REQUIRED")
        for item in urgent_actions[:4]:
            dl_info = f" (Deadline: {item.days_remaining}d)" if item.days_remaining is not None else ""
            lines.append(f"• {item.title}: {item.action}{dl_info}")
        lines.append("")

    # 2. Status changes (Hackathons / Internships / Placements)
    hackathon_changes = [c for c in status_changes if c.category == "hackathon"]
    internship_changes = [c for c in status_changes if c.category in ("internship", "placement")]
    other_changes = [c for c in status_changes if c.category not in ("hackathon", "internship", "placement")]

    if hackathon_changes:
        lines.append("HACKATHON UPDATES")
        for c in hackathon_changes[:4]:
            round_info = f" ({c.round_name})" if c.round_name else ""
            lines.append(f"• {c.title} — status: {c.new_status.replace('_', ' ').title()}{round_info}")
        lines.append("")

    if internship_changes:
        lines.append("INTERNSHIP & PLACEMENT UPDATES")
        for c in internship_changes[:4]:
            org_str = f" ({c.organization})" if c.organization else ""
            lines.append(f"• {c.title}{org_str} — {c.new_status.replace('_', ' ').title()}")
        lines.append("")

    if other_changes:
        lines.append("COLLEGE NOTICES & OTHER UPDATES")
        for c in other_changes[:3]:
            lines.append(f"• {c.title} — {c.new_status.replace('_', ' ').title()}")
        lines.append("")

    # 3. Deadlines
    if deadlines:
        lines.append("APPROACHING DEADLINES")
        for d in deadlines[:4]:
            org_str = f" — {d.organization}" if d.organization else ""
            lines.append(f"• {d.title}{org_str} ({d.urgency_label})")
        lines.append("")

    # 4. New Opportunities count
    if counts.new_opportunities > 0:
        lines.append(f"✨ {counts.new_opportunities} new opportunit{'ies' if counts.new_opportunities > 1 else 'y'} added today")

    return "\n".join(lines).strip()


def build_daily_digest(
    db: Session,
    user_id: int = 1,
    tz_name: Optional[str] = None,
    target_date: Optional[date] = None,
) -> DailyDigestResponse:
    """Build personalized daily career brief for a user.

    Aggregates new opportunities, status transitions, deadlines, and urgent actions.
    """
    user_tz = get_user_timezone(tz_name)
    now_user = datetime.now(user_tz)

    if target_date is None:
        target_date = now_user.date()

    # Time boundaries in user timezone, converted to UTC for DB queries
    start_user = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=user_tz)
    end_user = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, 999999, tzinfo=user_tz)

    start_utc = start_user.astimezone(timezone.utc)
    end_utc = end_user.astimezone(timezone.utc)

    # ── 1. New Opportunities discovered on target_date ─────
    new_opp_records = (
        db.query(Opportunity)
        .filter(
            Opportunity.user_id == user_id,
            Opportunity.first_seen_at >= start_utc,
            Opportunity.first_seen_at <= end_utc,
        )
        .order_by(Opportunity.created_at.desc())
        .all()
    )

    new_opp_items = [
        DigestOpportunityItem(
            opportunity_id=opp.id,
            title=opp.title,
            organization=opp.organization,
            category=opp.category,
            status=opp.status,
            priority=opp.priority,
            deadline=opp.deadline,
            first_seen_at=opp.first_seen_at,
        )
        for opp in new_opp_records
    ]

    # ── 2. Status Transitions that occurred on target_date ─
    status_history_records = (
        db.query(OpportunityStatusHistory, Opportunity)
        .join(Opportunity, OpportunityStatusHistory.opportunity_id == Opportunity.id)
        .filter(
            Opportunity.user_id == user_id,
            OpportunityStatusHistory.changed_at >= start_utc,
            OpportunityStatusHistory.changed_at <= end_utc,
            OpportunityStatusHistory.old_status.isnot(None),
            OpportunityStatusHistory.old_status != OpportunityStatusHistory.new_status,
        )
        .order_by(OpportunityStatusHistory.changed_at.desc())
        .all()
    )

    status_change_items = [
        DigestStatusChangeItem(
            opportunity_id=opp.id,
            title=opp.title,
            organization=opp.organization,
            category=opp.category,
            old_status=h.old_status or "unknown",
            new_status=h.new_status,
            round_name=opp.round_name,
            changed_at=h.changed_at,
        )
        for h, opp in status_history_records
    ]

    # ── 3. Deadlines Analysis ──────────────────────────────
    today_date = target_date
    tomorrow_date = today_date + timedelta(days=1)
    week_end_date = today_date + timedelta(days=7)

    all_active_opps = (
        db.query(Opportunity)
        .filter(
            Opportunity.user_id == user_id,
            Opportunity.status.notin_(["completed", "rejected"]),
        )
        .all()
    )

    deadlines_today_count = 0
    deadlines_tomorrow_count = 0
    deadlines_this_week_count = 0
    deadline_items: list[DigestDeadlineItem] = []

    for opp in all_active_opps:
        if opp.deadline is None:
            continue

        dl_user = opp.deadline
        if dl_user.tzinfo is None:
            dl_user = dl_user.replace(tzinfo=timezone.utc)
        dl_user = dl_user.astimezone(user_tz)

        dl_date = dl_user.date()
        diff_days = (dl_date - today_date).days

        urgency = ""
        if dl_date < today_date:
            urgency = "overdue"
        elif dl_date == today_date:
            deadlines_today_count += 1
            urgency = "today"
        elif dl_date == tomorrow_date:
            deadlines_tomorrow_count += 1
            urgency = "tomorrow"
        elif tomorrow_date < dl_date <= week_end_date:
            deadlines_this_week_count += 1
            urgency = f"in {diff_days} days"

        if urgency:
            deadline_items.append(
                DigestDeadlineItem(
                    opportunity_id=opp.id,
                    title=opp.title,
                    organization=opp.organization,
                    category=opp.category,
                    deadline=dl_user,
                    urgency_label=urgency,
                    days_remaining=diff_days,
                )
            )

    # Sort deadlines by urgency
    deadline_items.sort(key=lambda d: d.days_remaining)

    # ── 4. Urgent Actions ──────────────────────────────────
    urgent_action_candidates = (
        db.query(Opportunity)
        .filter(
            Opportunity.user_id == user_id,
            Opportunity.status.notin_(["completed", "rejected"]),
            or_(
                Opportunity.action_required == True,
                Opportunity.priority.in_(["critical", "high"]),
                Opportunity.deadline.isnot(None),
            ),
        )
        .all()
    )

    urgent_action_items: list[DigestActionItem] = []
    for opp in urgent_action_candidates:
        days_rem = None
        is_overdue = False

        if opp.deadline:
            dl = opp.deadline if opp.deadline.tzinfo else opp.deadline.replace(tzinfo=timezone.utc)
            dl_local = dl.astimezone(user_tz)
            days_rem = (dl_local.date() - today_date).days
            is_overdue = (dl_local - now_user).total_seconds() < 0

        # Determine default action description if not explicitly set
        action_text = opp.action
        if not action_text:
            if opp.status == "shortlisted":
                action_text = "Confirm participation / check next round instructions"
            elif opp.status == "assessment":
                action_text = "Complete online assessment before deadline"
            elif opp.status == "interview":
                action_text = "Prepare for interview slot"
            elif opp.status == "registered":
                action_text = "Review event details & upcoming milestones"
            elif is_overdue:
                action_text = "Action overdue — check submission portal immediately"
            elif days_rem is not None and days_rem <= 1:
                action_text = "Submission deadline approaching soon"
            elif getattr(opp, "action_required", False):
                action_text = "Action required — check email details"
            else:
                continue

        urgent_action_items.append(
            DigestActionItem(
                opportunity_id=opp.id,
                title=opp.title,
                organization=opp.organization,
                category=opp.category,
                action=action_text,
                priority=opp.priority,
                deadline=opp.deadline,
                days_remaining=days_rem,
                is_overdue=is_overdue,
            )
        )

    # Sort urgent actions: overdue first, then by priority weight, then by deadline
    def action_sort_key(item: DigestActionItem):
        prio = PRIORITY_WEIGHT.get(item.priority, 1)
        overdue_rank = 0 if item.is_overdue else 1
        days = item.days_remaining if item.days_remaining is not None else 999
        return (overdue_rank, -prio, days)

    urgent_action_items.sort(key=action_sort_key)

    # ── 5. Category updates count ──────────────────────────
    all_updated_ids = {opp.id for opp in new_opp_records} | {h.opportunity_id for h, _ in status_history_records}
    updated_opps = db.query(Opportunity).filter(Opportunity.id.in_(all_updated_ids)).all() if all_updated_ids else []

    hackathon_count = sum(1 for o in updated_opps if o.category == "hackathon")
    internship_count = sum(1 for o in updated_opps if o.category == "internship")
    placement_count = sum(1 for o in updated_opps if o.category == "placement")
    college_count = sum(1 for o in updated_opps if o.category == "college")

    counts = DigestCounts(
        new_opportunities=len(new_opp_items),
        status_changes=len(status_change_items),
        urgent_actions=len(urgent_action_items),
        deadlines_today=deadlines_today_count,
        deadlines_tomorrow=deadlines_tomorrow_count,
        deadlines_this_week=deadlines_this_week_count,
        hackathon_updates=hackathon_count,
        internship_updates=internship_count,
        placement_updates=placement_count,
        college_updates=college_count,
    )

    summary_text = _format_human_readable_brief(
        target_date=target_date,
        counts=counts,
        urgent_actions=urgent_action_items,
        status_changes=status_change_items,
        new_opps=new_opp_items,
        deadlines=deadline_items,
    )

    return DailyDigestResponse(
        generated_at=now_user,
        target_date=str(target_date),
        timezone=str(user_tz),
        summary=summary_text,
        summary_text=summary_text,
        counts=counts,
        urgent_actions=urgent_action_items,
        recent_status_changes=status_change_items,
        new_opportunities=new_opp_items,
        upcoming_deadlines=deadline_items,
    )
