"""
CareerMail AI — Notification Dispatcher.

Orchestrates notification decisions, deduplication, cooldown checking,
payload formatting, FCM dispatch, token cleanup, and audit logging.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.device import DeviceToken
from app.models.notification import NotificationLog
from app.models.opportunity import Opportunity
from app.schemas.notification import NotificationSendResult
from app.services.notifications.fcm import FCMClient, FCMResult, get_fcm_client
from app.utils.logging import get_logger, log_event

logger = get_logger("notifications.dispatcher")

# High-value statuses that qualify for real-time push alerts
HIGH_VALUE_STATUSES = {
    "shortlisted",
    "next_round",
    "assessment",
    "interview",
    "selected",
    "rejected",
}


class NotificationDispatcher:
    """Coordinates push notification dispatching and deduplication."""

    def __init__(self, fcm_client: Optional[FCMClient] = None) -> None:
        self.settings = get_settings()
        self.fcm = fcm_client or get_fcm_client()

    def _is_suppressed_by_cooldown(
        self,
        db: Session,
        *,
        user_id: int,
        dedup_key: str,
        cooldown_minutes: Optional[int] = None,
    ) -> bool:
        """Check if an identical notification was dispatched within the cooldown window."""
        minutes = (
            cooldown_minutes
            if cooldown_minutes is not None
            else self.settings.NOTIFICATION_COOLDOWN_MINUTES
        )
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        existing = (
            db.query(NotificationLog)
            .filter(
                NotificationLog.user_id == user_id,
                NotificationLog.dedup_key == dedup_key,
                NotificationLog.created_at >= cutoff,
                NotificationLog.status.in_(["sent", "mock_sent"]),
            )
            .first()
        )
        if existing:
            logger.info(
                "NOTIFICATION_COOLDOWN_SUPPRESSED | user_id=%d | dedup_key=%r | last_sent=%s",
                user_id,
                dedup_key,
                existing.created_at.isoformat(),
            )
            return True
        return False

    def _get_active_tokens(self, db: Session, user_id: int) -> list[str]:
        """Fetch all currently active device FCM tokens for a user."""
        devices = (
            db.query(DeviceToken)
            .filter(DeviceToken.user_id == user_id, DeviceToken.is_active == True)
            .all()
        )
        return [d.fcm_token for d in devices]

    def _deactivate_invalid_tokens(self, db: Session, invalid_tokens: list[str]) -> None:
        """Deactivate tokens that Firebase identified as unregistered or invalid."""
        if not invalid_tokens:
            return
        logger.warning(
            "DEACTIVATING_INVALID_TOKENS | count=%d",
            len(invalid_tokens),
        )
        db.query(DeviceToken).filter(
            DeviceToken.fcm_token.in_(invalid_tokens)
        ).update({"is_active": False}, synchronize_session=False)
        db.commit()

    def _dispatch_and_log(
        self,
        db: Session,
        *,
        user_id: int,
        opportunity_id: Optional[int],
        notification_type: str,
        title: str,
        body: str,
        data_payload: dict[str, Any],
        dedup_key: Optional[str] = None,
    ) -> tuple[FCMResult, NotificationLog]:
        """Core dispatch routine with active token lookup, FCM send, and DB logging."""
        tokens = self._get_active_tokens(db, user_id)

        # Dispatch via FCM abstraction
        fcm_result = self.fcm.send_to_tokens(
            tokens=tokens,
            title=title,
            body=body,
            data_payload=data_payload,
        )

        # Cleanup any unregistered tokens reported by FCM
        if fcm_result.invalid_tokens:
            self._deactivate_invalid_tokens(db, fcm_result.invalid_tokens)

        # Record in NotificationLog
        log_entry = NotificationLog(
            user_id=user_id,
            opportunity_id=opportunity_id,
            notification_type=notification_type,
            title=title,
            body=body,
            data_payload=data_payload,
            status=fcm_result.status,
            fcm_message_id=fcm_result.message_id,
            dedup_key=dedup_key,
            created_at=datetime.now(timezone.utc),
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)

        log_event(
            logger,
            "NOTIFICATION_DISPATCHED",
            user_id=user_id,
            type=notification_type,
            status=fcm_result.status,
            recipients=fcm_result.recipient_count,
            opp_id=opportunity_id,
        )

        return fcm_result, log_entry

    # ── Concrete Notification Triggers ───────────────────────

    def notify_status_change(
        self,
        db: Session,
        *,
        opportunity: Opportunity,
        old_status: Optional[str],
        new_status: str,
        source_email_id: Optional[int] = None,
    ) -> Optional[NotificationLog]:
        """Send push notification for meaningful opportunity status progression."""
        # 1. Decision Rule: Old and new must differ
        if old_status == new_status:
            return None

        # 2. Decision Rule: Must be a high-value status
        if new_status not in HIGH_VALUE_STATUSES:
            logger.debug(
                "STATUS_CHANGE_IGNORED | opp_id=%d | %s -> %s (not high-value)",
                opportunity.id,
                old_status,
                new_status,
            )
            return None

        # 3. Deduplication & Cooldown: 6 hours for the specific transition
        dedup_key = f"status_change:{opportunity.id}:{old_status}->{new_status}"
        if self._is_suppressed_by_cooldown(db, user_id=opportunity.user_id, dedup_key=dedup_key):
            return None

        # 4. Format Content
        formatted_new = new_status.replace("_", " ").title()
        org_name = opportunity.organization or "Career Opportunity"

        if old_status:
            formatted_old = old_status.replace("_", " ").title()
            title = f"Status Update: {opportunity.title}"
            body = f"Your status moved from {formatted_old} to {formatted_new} at {org_name}."
        else:
            title = f"{formatted_new}: {opportunity.title}"
            body = f"New {formatted_new.lower()} update for {opportunity.title} at {org_name}."

        # 5. Safe Payload (navigation metadata only)
        payload: dict[str, Any] = {
            "type": "opportunity",
            "opportunity_id": str(opportunity.id),
        }
        if source_email_id:
            payload["email_id"] = str(source_email_id)

        _, log_entry = self._dispatch_and_log(
            db,
            user_id=opportunity.user_id,
            opportunity_id=opportunity.id,
            notification_type="status_change",
            title=title,
            body=body,
            data_payload=payload,
            dedup_key=dedup_key,
        )
        return log_entry

    def notify_urgent_action(
        self,
        db: Session,
        *,
        opportunity: Opportunity,
        source_email_id: Optional[int] = None,
    ) -> Optional[NotificationLog]:
        """Send push notification when an opportunity requires urgent action."""
        # 1. Decision Rule: Action must be required
        if not opportunity.action_required:
            return None

        # 2. Urgency check: deadline today/tomorrow/overdue or critical priority
        is_urgent = False
        if opportunity.priority in ("critical", "high"):
            is_urgent = True

        if opportunity.deadline:
            dl = opportunity.deadline
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            diff = dl - now
            if diff <= timedelta(days=2):  # overdue, today, or tomorrow
                is_urgent = True

        if not is_urgent:
            return None

        # 3. Deduplication & Cooldown: Suppress duplicate alert within cooldown
        action_clean = (opportunity.action or "action").strip()[:30]
        dedup_key = f"urgent_action:{opportunity.id}:{action_clean}"
        if self._is_suppressed_by_cooldown(db, user_id=opportunity.user_id, dedup_key=dedup_key):
            return None

        # 4. Format Content
        title = f"Action Required: {opportunity.title}"
        action_desc = opportunity.action or "Please review the required action"
        body = f"{action_desc} ({opportunity.organization or 'Career Opportunity'})."

        payload: dict[str, Any] = {
            "type": "opportunity",
            "opportunity_id": str(opportunity.id),
        }
        if source_email_id:
            payload["email_id"] = str(source_email_id)

        _, log_entry = self._dispatch_and_log(
            db,
            user_id=opportunity.user_id,
            opportunity_id=opportunity.id,
            notification_type="urgent_action",
            title=title,
            body=body,
            data_payload=payload,
            dedup_key=dedup_key,
        )
        return log_entry

    def notify_approaching_deadline(
        self,
        db: Session,
        *,
        opportunity: Opportunity,
    ) -> Optional[NotificationLog]:
        """Send push notification when an opportunity deadline is today or tomorrow."""
        if not opportunity.deadline:
            return None

        dl = opportunity.deadline
        if dl.tzinfo is None:
            dl = dl.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        # Check if deadline is today or tomorrow
        today_date = now.date()
        dl_date = dl.date()
        day_diff = (dl_date - today_date).days

        if day_diff not in (0, 1):
            return None

        # Dedup key includes deadline date
        dedup_key = f"deadline:{opportunity.id}:{dl_date.isoformat()}"
        if self._is_suppressed_by_cooldown(db, user_id=opportunity.user_id, dedup_key=dedup_key):
            return None

        day_label = "today" if day_diff == 0 else "tomorrow"
        title = f"Deadline Approaching: {opportunity.title}"
        body = f"Deadline is {day_label} for {opportunity.title} ({opportunity.organization or 'Company'})."

        payload: dict[str, Any] = {
            "type": "opportunity",
            "opportunity_id": str(opportunity.id),
        }

        _, log_entry = self._dispatch_and_log(
            db,
            user_id=opportunity.user_id,
            opportunity_id=opportunity.id,
            notification_type="deadline",
            title=title,
            body=body,
            data_payload=payload,
            dedup_key=dedup_key,
        )
        return log_entry

    def notify_daily_digest(
        self,
        db: Session,
        *,
        user_id: int = 1,
        target_date: Optional[date] = None,
    ) -> Optional[NotificationLog]:
        """Send daily digest notification reusing the deterministic builder from Milestone 4."""
        from app.services.digest import build_daily_digest

        d = target_date or datetime.now(timezone.utc).date()
        date_str = d.isoformat()

        dedup_key = f"digest:{user_id}:{date_str}"
        if self._is_suppressed_by_cooldown(db, user_id=user_id, dedup_key=dedup_key):
            return None

        digest = build_daily_digest(db, user_id=user_id, target_date=d)

        # Build concise push text
        lines: list[str] = []
        if digest.counts.urgent_actions > 0:
            lines.append(f"{digest.counts.urgent_actions} urgent action{'s' if digest.counts.urgent_actions > 1 else ''}")
        if digest.counts.new_opportunities > 0:
            lines.append(f"{digest.counts.new_opportunities} new opportunit{'ies' if digest.counts.new_opportunities > 1 else 'y'}")
        if digest.counts.status_changes > 0:
            lines.append(f"{digest.counts.status_changes} status update{'s' if digest.counts.status_changes > 1 else ''}")
        total_deadlines = digest.counts.deadlines_today + digest.counts.deadlines_tomorrow + digest.counts.deadlines_this_week
        if total_deadlines > 0:
            lines.append(f"{total_deadlines} deadline{'s' if total_deadlines > 1 else ''} this week")

        if lines:
            body = "\n".join(lines)
        else:
            body = "You are all caught up! No urgent updates today."

        title = "Today's Career Brief"
        payload = {
            "type": "digest",
            "date": date_str,
        }

        _, log_entry = self._dispatch_and_log(
            db,
            user_id=user_id,
            opportunity_id=None,
            notification_type="digest",
            title=title,
            body=body,
            data_payload=payload,
            dedup_key=dedup_key,
        )
        return log_entry

    def notify_test(
        self,
        db: Session,
        *,
        user_id: int = 1,
        title: Optional[str] = None,
        body: Optional[str] = None,
        opportunity_id: Optional[int] = None,
    ) -> tuple[NotificationSendResult, NotificationLog]:
        """Send on-demand test notification (bypasses cooldown)."""
        test_title = title or "CareerMail AI Test"
        test_body = (
            body
            or "This is a test notification from CareerMail AI. Push notifications are working!"
        )

        payload: dict[str, Any] = {"type": "test"}
        if opportunity_id:
            payload = {"type": "opportunity", "opportunity_id": str(opportunity_id)}

        fcm_result, log_entry = self._dispatch_and_log(
            db,
            user_id=user_id,
            opportunity_id=opportunity_id,
            notification_type="test",
            title=test_title,
            body=test_body,
            data_payload=payload,
            dedup_key=None,
        )

        result = NotificationSendResult(
            success=fcm_result.success,
            status=fcm_result.status,
            recipient_count=fcm_result.recipient_count,
            message_id=fcm_result.message_id,
            detail=fcm_result.detail,
        )
        return result, log_entry


_global_dispatcher: Optional[NotificationDispatcher] = None


def get_notification_dispatcher(
    fcm_client: Optional[FCMClient] = None,
) -> NotificationDispatcher:
    """Get or create singleton NotificationDispatcher instance."""
    global _global_dispatcher
    if fcm_client is not None:
        return NotificationDispatcher(fcm_client=fcm_client)
    if _global_dispatcher is None:
        _global_dispatcher = NotificationDispatcher()
    return _global_dispatcher
