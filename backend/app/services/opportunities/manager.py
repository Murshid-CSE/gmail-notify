"""
CareerMail AI — Opportunity Manager.

Coordinates opportunity creation, updates, deduplication, status progression,
status history recording, source email attachment, and deadline calculations.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.models.opportunity import Opportunity
from app.models.opportunity_email import OpportunityEmail
from app.models.status_history import OpportunityStatusHistory
from app.schemas.extraction import EmailAnalysis
from app.services.deduplication.matcher import find_matching_opportunity
from app.utils.logging import get_logger, log_event

logger = get_logger("opportunities.manager")

# ── Status Precedence / Progression Rank ──────────────────
# Higher rank indicates further progression. Status cannot be downgraded
# to a lower rank by subsequent or older emails.
STATUS_RANK: dict[str, int] = {
    "rejected": 100,
    "completed": 95,
    "selected": 80,
    "interview": 60,
    "next_round": 55,
    "assessment": 50,
    "shortlisted": 40,
    "registered": 30,
    "opportunity": 10,
    "informational": 5,
    "unknown": 0,
}

PRIORITY_RANK: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def parse_deadline_datetime(raw: Optional[str]) -> Optional[datetime]:
    """Parse raw deadline string into timezone-aware UTC datetime.

    Handles ISO formats, standard YYYY-MM-DD, and common textual dates.
    Returns None if parsing fails.
    """
    if not raw or not raw.strip():
        return None

    cleaned = raw.strip()

    # 1. Try standard ISO format
    try:
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        pass

    # 2. Try common date patterns
    date_patterns = [
        ("%Y-%m-%d", True),
        ("%Y/%m/%d", True),
        ("%d-%m-%Y", True),
        ("%d/%m/%Y", True),
        ("%d %b %Y", True),
        ("%d %B %Y", True),
        ("%b %d, %Y", True),
        ("%B %d, %Y", True),
        ("%b %d %Y", True),
        ("%B %d %Y", True),
        ("%Y-%m-%d %H:%M:%S", False),
        ("%d-%m-%Y %H:%M:%S", False),
    ]

    for pattern, is_date_only in date_patterns:
        try:
            parsed = datetime.strptime(cleaned, pattern)
            if is_date_only:
                # Set deadline to end of day UTC
                parsed = parsed.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            else:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (ValueError, TypeError):
            continue

    # 3. Try extracting YYYY-MM-DD via regex
    match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", cleaned)
    if match:
        try:
            year, month, day = map(int, match.groups())
            return datetime(year, month, day, 23, 59, 59, tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


def compute_deadline_state(
    deadline: Optional[datetime],
    now: Optional[datetime] = None,
) -> dict:
    """Calculate derived deadline metrics.

    Returns:
        dict with:
          • days_remaining: Optional[int]
          • hours_remaining: Optional[float]
          • is_overdue: bool
          • is_due_today: bool
          • is_due_tomorrow: bool
    """
    if deadline is None:
        return {
            "days_remaining": None,
            "hours_remaining": None,
            "is_overdue": False,
            "is_due_today": False,
            "is_due_tomorrow": False,
        }

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    diff = deadline - now
    total_seconds = diff.total_seconds()
    is_overdue = total_seconds < 0

    hours_remaining = round(total_seconds / 3600.0, 1)
    days_remaining = int(total_seconds // 86400)

    # Date-level comparisons in UTC
    deadline_date = deadline.date()
    now_date = now.date()
    tomorrow_date = now_date + timedelta(days=1)

    is_due_today = (deadline_date == now_date) and not is_overdue
    is_due_tomorrow = deadline_date == tomorrow_date

    return {
        "days_remaining": days_remaining,
        "hours_remaining": hours_remaining,
        "is_overdue": is_overdue,
        "is_due_today": is_due_today,
        "is_due_tomorrow": is_due_tomorrow,
    }


def should_update_status(current_status: str, new_status: str) -> bool:
    """Determine if new_status is a valid status upgrade.

    Prevents status downgrades (e.g. next_round -> shortlisted).
    """
    if not new_status or new_status in ("unknown", "informational"):
        return False

    current_rank = STATUS_RANK.get(current_status, 0)
    new_rank = STATUS_RANK.get(new_status, 0)

    # Allow transition only if rank increases
    return new_rank > current_rank


def update_status(
    db: Session,
    opportunity: Opportunity,
    new_status: str,
    source_email_id: Optional[int],
    changed_at: Optional[datetime] = None,
) -> bool:
    """Safely update opportunity status and record status history.

    Returns:
        True if status changed, False otherwise.
    """
    old_status = opportunity.status

    if old_status == new_status:
        return False

    if not should_update_status(old_status, new_status):
        logger.info(
            "STATUS_DOWNGRADE_PREVENTED | opp_id=%d | current=%s | attempted=%s",
            opportunity.id,
            old_status,
            new_status,
        )
        return False

    opportunity.status = new_status
    if changed_at:
        opportunity.last_updated_at = changed_at
    else:
        opportunity.last_updated_at = datetime.now(timezone.utc)

    record_status_history(
        db,
        opportunity_id=opportunity.id,
        old_status=old_status,
        new_status=new_status,
        source_email_id=source_email_id,
        changed_at=changed_at,
    )

    logger.info(
        "STATUS_UPDATED | opp_id=%d | %s -> %s | email_id=%s",
        opportunity.id,
        old_status,
        new_status,
        source_email_id,
    )
    return True


def record_status_history(
    db: Session,
    opportunity_id: int,
    old_status: Optional[str],
    new_status: str,
    source_email_id: Optional[int],
    changed_at: Optional[datetime] = None,
) -> Optional[OpportunityStatusHistory]:
    """Record a status transition.

    Idempotent: will not create duplicate entries for the same transition from the same email.
    """
    if old_status == new_status:
        return None

    # Check for duplicate entry from the same source email
    if source_email_id:
        existing = (
            db.query(OpportunityStatusHistory)
            .filter(
                OpportunityStatusHistory.opportunity_id == opportunity_id,
                OpportunityStatusHistory.source_email_id == source_email_id,
                OpportunityStatusHistory.new_status == new_status,
            )
            .first()
        )
        if existing:
            return existing

    history = OpportunityStatusHistory(
        opportunity_id=opportunity_id,
        old_status=old_status,
        new_status=new_status,
        source_email_id=source_email_id,
        changed_at=changed_at or datetime.now(timezone.utc),
    )
    db.add(history)
    return history


def attach_source_email(
    db: Session,
    opportunity_id: int,
    email_id: int,
    attached_at: Optional[datetime] = None,
) -> bool:
    """Attach an email message to an opportunity.

    Idempotent: does nothing if relationship already exists.
    """
    existing = (
        db.query(OpportunityEmail)
        .filter(
            OpportunityEmail.opportunity_id == opportunity_id,
            OpportunityEmail.email_id == email_id,
        )
        .first()
    )
    if existing:
        return False

    link = OpportunityEmail(
        opportunity_id=opportunity_id,
        email_id=email_id,
        attached_at=attached_at or datetime.now(timezone.utc),
    )
    db.add(link)
    return True


def create_or_update_opportunity(
    db: Session,
    email: EmailMessage,
    analysis: EmailAnalysis,
    notify: bool = True,
) -> tuple[Opportunity, bool, bool]:
    """Process an EmailAnalysis into an Opportunity.

    Finds existing opportunity via deduplication matcher:
      • If matched: updates fields, applies status progression, attaches email.
      • If no match: creates new opportunity, records initial history, attaches email.
      • Dispatches push notifications for concrete events (high-value status changes, urgent actions).

    Args:
        db: Active database session.
        email: The source EmailMessage.
        analysis: Validated EmailAnalysis from Gemini.
        notify: Whether to dispatch push notifications for qualifying events.

    Returns:
        tuple of (Opportunity, was_created: bool, status_changed: bool)
    """

    # 1. Determine user_id
    user_id = 1
    if email.account_id:
        account = db.query(EmailAccount).filter(EmailAccount.id == email.account_id).first()
        if account:
            user_id = account.user_id

    category_str = analysis.category.value
    title_str = (analysis.title or email.subject or "Untitled Opportunity").strip()
    status_str = analysis.status.value

    # 2. Check for existing opportunity
    opp = find_matching_opportunity(
        db=db,
        user_id=user_id,
        category=category_str,
        title=title_str,
        organization=analysis.organization,
    )

    received_time = email.received_at
    if received_time and received_time.tzinfo is None:
        received_time = received_time.replace(tzinfo=timezone.utc)

    if opp is None:
        # ── CREATE NEW OPPORTUNITY ───────────────────────────
        parsed_deadline = parse_deadline_datetime(analysis.deadline)

        opp = Opportunity(
            user_id=user_id,
            category=category_str,
            title=title_str,
            organization=analysis.organization,
            description=analysis.description,
            status=status_str,
            round_name=analysis.round_name,
            deadline=parsed_deadline,
            event_date=analysis.event_date,
            location=analysis.location,
            eligibility=analysis.eligibility,
            apply_url=analysis.apply_url,
            event_url=analysis.event_url,
            action_required=analysis.action_required,
            action=analysis.action,
            priority=analysis.priority.value,
            confidence=analysis.confidence,
            source_account_id=email.account_id,
            first_seen_at=received_time or datetime.now(timezone.utc),
            last_updated_at=received_time or datetime.now(timezone.utc),
        )
        db.add(opp)
        db.flush()  # Obtain opp.id

        # Attach source email
        attach_source_email(db, opp.id, email.id, attached_at=received_time)

        # Record initial status
        record_status_history(
            db,
            opportunity_id=opp.id,
            old_status=None,
            new_status=status_str,
            source_email_id=email.id,
            changed_at=received_time,
        )

        log_event(
            logger,
            "OPPORTUNITY_CREATED",
            opp_id=opp.id,
            category=opp.category,
            title=opp.title,
            status=opp.status,
            email_id=email.id,
        )

        if notify:
            try:
                from app.services.notifications.dispatcher import get_notification_dispatcher
                dispatcher = get_notification_dispatcher()
                if opp.status in {"shortlisted", "next_round", "assessment", "interview", "selected", "rejected"}:
                    dispatcher.notify_status_change(
                        db,
                        opportunity=opp,
                        old_status=None,
                        new_status=opp.status,
                        source_email_id=email.id,
                    )
                elif opp.action_required:
                    dispatcher.notify_urgent_action(
                        db,
                        opportunity=opp,
                        source_email_id=email.id,
                    )
            except Exception as exc:
                logger.warning(
                    "NOTIFICATION_DISPATCH_FAILED | opp_id=%d | error=%s",
                    opp.id,
                    exc,
                )

        return opp, True, True

    else:
        # ── UPDATE EXISTING OPPORTUNITY ───────────────────────
        old_status = opp.status
        old_action_required = opp.action_required

        status_changed = update_status(
            db,
            opportunity=opp,
            new_status=status_str,
            source_email_id=email.id,
            changed_at=received_time,
        )

        # Update round_name if provided and newer
        if analysis.round_name:
            opp.round_name = analysis.round_name

        # Update deadline if provided
        if analysis.deadline:
            parsed_dl = parse_deadline_datetime(analysis.deadline)
            if parsed_dl:
                opp.deadline = parsed_dl

        # Fill in missing metadata fields from incoming email
        if analysis.event_date and not opp.event_date:
            opp.event_date = analysis.event_date
        if analysis.location and not opp.location:
            opp.location = analysis.location
        if analysis.eligibility and not opp.eligibility:
            opp.eligibility = analysis.eligibility
        if analysis.apply_url and not opp.apply_url:
            opp.apply_url = analysis.apply_url
        if analysis.event_url and not opp.event_url:
            opp.event_url = analysis.event_url
        if analysis.organization and not opp.organization:
            opp.organization = analysis.organization
        if analysis.description and not opp.description:
            opp.description = analysis.description
        if analysis.action_required:
            opp.action_required = True
        if analysis.action and not opp.action:
            opp.action = analysis.action

        # Escalate priority if incoming email is higher priority
        incoming_prio_rank = PRIORITY_RANK.get(analysis.priority.value, 0)
        current_prio_rank = PRIORITY_RANK.get(opp.priority, 0)
        if incoming_prio_rank > current_prio_rank:
            opp.priority = analysis.priority.value

        # Update last_updated_at
        if received_time and opp.last_updated_at:
            t1 = opp.last_updated_at if opp.last_updated_at.tzinfo else opp.last_updated_at.replace(tzinfo=timezone.utc)
            t2 = received_time if received_time.tzinfo else received_time.replace(tzinfo=timezone.utc)
            opp.last_updated_at = max(t1, t2)

        # Attach email to existing opportunity
        attach_source_email(db, opp.id, email.id, attached_at=received_time)

        log_event(
            logger,
            "OPPORTUNITY_UPDATED",
            opp_id=opp.id,
            status=opp.status,
            status_changed=status_changed,
            email_id=email.id,
        )

        if notify:
            try:
                from app.services.notifications.dispatcher import get_notification_dispatcher
                dispatcher = get_notification_dispatcher()
                if status_changed:
                    dispatcher.notify_status_change(
                        db,
                        opportunity=opp,
                        old_status=old_status,
                        new_status=opp.status,
                        source_email_id=email.id,
                    )
                if opp.action_required and not old_action_required:
                    dispatcher.notify_urgent_action(
                        db,
                        opportunity=opp,
                        source_email_id=email.id,
                    )
            except Exception as exc:
                logger.warning(
                    "NOTIFICATION_DISPATCH_FAILED | opp_id=%d | error=%s",
                    opp.id,
                    exc,
                )

        return opp, False, status_changed

