"""
CareerMail AI — Centralized Execution Pipeline.

Orchestrates the complete automation loop:
  1. Multi-account Gmail synchronization with per-account error isolation
  2. Relevance filtering and Gemini AI extraction for pending emails
  3. Opportunity tracking and status progression
  4. Approaching deadline evaluation and proactive push notifications
  5. Morning Daily Career Brief dispatch
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.models.email_account import EmailAccount
from app.models.notification import NotificationLog
from app.models.opportunity import Opportunity
from app.services.ai.gemini import GeminiClient
from app.services.extraction.extractor import process_pending_emails
from app.services.gmail.sync import sync_account
from app.services.notifications.dispatcher import (
    NotificationDispatcher,
    get_notification_dispatcher,
)
from app.utils.logging import get_logger, log_event

logger = get_logger("services.pipeline")


@dataclass
class PipelineRunResult:
    """Structured metrics returned from an execution of the automation pipeline."""

    accounts_total: int = 0
    accounts_succeeded: int = 0
    accounts_failed: int = 0
    emails_ingested: int = 0
    emails_extracted: int = 0
    deadline_alerts_sent: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    success: bool = True

    def to_dict(self) -> dict:
        return {
            "accounts_total": self.accounts_total,
            "accounts_succeeded": self.accounts_succeeded,
            "accounts_failed": self.accounts_failed,
            "emails_ingested": self.emails_ingested,
            "emails_extracted": self.emails_extracted,
            "deadline_alerts_sent": self.deadline_alerts_sent,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
            "success": self.success,
        }


def run_full_sync_and_extraction_pipeline(
    db: Session,
    *,
    gemini_client: Optional[GeminiClient] = None,
    dispatcher: Optional[NotificationDispatcher] = None,
    batch_limit: int = 50,
) -> PipelineRunResult:
    """Execute the end-to-end sync, extraction, and alert evaluation pipeline.

    Guarantees:
      • Multi-account isolation: Failure in Account 1 does not abort Account 2.
      • Idempotent: Can safely run every 15 minutes without duplicating entities.
      • Deduplication-protected: Deadline and status notifications respect 6h cooldown.

    Returns:
        PipelineRunResult containing execution metrics.
    """
    start_time = time.time()
    result = PipelineRunResult()

    log_event(logger, "SYNC_JOB_STARTED")

    # ── Step 1: Discover all active accounts ──────────────────
    active_accounts = (
        db.query(EmailAccount)
        .filter(EmailAccount.is_active == True)
        .order_by(EmailAccount.id.asc())
        .all()
    )
    result.accounts_total = len(active_accounts)

    # ── Step 2: Synchronize each account with error isolation ─
    for account in active_accounts:
        try:
            log_event(
                logger,
                "ACCOUNT_SYNC_STARTED",
                account_id=account.id,
                email=account.email_address,
            )
            sync_res = sync_account(db, account)
            result.accounts_succeeded += 1
            result.emails_ingested += sync_res.new_messages
            log_event(
                logger,
                "ACCOUNT_SYNC_COMPLETED",
                account_id=account.id,
                new_messages=sync_res.new_messages,
                skipped=sync_res.skipped_duplicates,
            )
        except Exception as exc:
            result.accounts_failed += 1
            safe_error_msg = f"Account {account.id} ({account.email_address}): {type(exc).__name__}"
            result.errors.append(safe_error_msg)
            logger.error(
                "ACCOUNT_SYNC_FAILED | account_id=%d | email=%s | error=%s",
                account.id,
                account.email_address,
                exc,
            )

    # ── Step 3: Process pending emails with AI extraction ────
    try:
        extraction_summary = process_pending_emails(
            db,
            limit=batch_limit,
            gemini_client=gemini_client,
        )
        result.emails_extracted = extraction_summary.get("extracted", 0)
        log_event(
            logger,
            "EXTRACTION_BATCH_COMPLETED",
            extracted=result.emails_extracted,
            filtered_out=extraction_summary.get("filtered_out", 0),
            failed=extraction_summary.get("extraction_failed", 0),
        )
    except Exception as exc:
        result.errors.append(f"Extraction failed: {type(exc).__name__}")
        logger.error("EXTRACTION_BATCH_ERROR | error=%s", exc)

    # ── Step 4: Scan approaching deadlines ───────────────────
    notif_dispatcher = dispatcher or get_notification_dispatcher()
    now_utc = datetime.now(timezone.utc)

    try:
        active_opps_with_deadlines = (
            db.query(Opportunity)
            .filter(
                Opportunity.deadline.isnot(None),
                Opportunity.status.notin_(["completed", "rejected"]),
            )
            .all()
        )

        for opp in active_opps_with_deadlines:
            try:
                alert_log = notif_dispatcher.notify_approaching_deadline(db, opportunity=opp)
                if alert_log is not None:
                    result.deadline_alerts_sent += 1
            except Exception as opp_exc:
                logger.warning(
                    "DEADLINE_ALERT_FAILED | opp_id=%d | error=%s",
                    opp.id,
                    opp_exc,
                )

        log_event(
            logger,
            "DEADLINE_SCAN_COMPLETED",
            evaluated=len(active_opps_with_deadlines),
            alerts_sent=result.deadline_alerts_sent,
        )
    except Exception as exc:
        result.errors.append(f"Deadline scan failed: {type(exc).__name__}")
        logger.error("DEADLINE_SCAN_ERROR | error=%s", exc)

    result.duration_seconds = round(time.time() - start_time, 2)
    result.success = result.accounts_failed == 0 and len(result.errors) == 0

    log_event(
        logger,
        "PIPELINE_COMPLETE",
        accounts_total=result.accounts_total,
        accounts_succeeded=result.accounts_succeeded,
        accounts_failed=result.accounts_failed,
        emails_ingested=result.emails_ingested,
        emails_extracted=result.emails_extracted,
        alerts_sent=result.deadline_alerts_sent,
        duration=result.duration_seconds,
        success=result.success,
    )

    return result


def run_daily_digest_automation(
    db: Session,
    *,
    user_id: int = 1,
    target_date: Optional[date] = None,
    dispatcher: Optional[NotificationDispatcher] = None,
) -> Optional[NotificationLog]:
    """Automate morning career brief generation and push notification dispatch.

    Reuses Milestone 4's deterministic digest calculation and Milestone 6's
    NotificationDispatcher. Does not invoke Gemini.
    """
    notif_dispatcher = dispatcher or get_notification_dispatcher()
    d = target_date or datetime.now(timezone.utc).date()

    log_event(logger, "DIGEST_JOB_STARTED", user_id=user_id, date=d.isoformat())

    try:
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            if user_id == 1:
                user = User(id=1, display_name="Default User")
                db.add(user)
                db.commit()
            else:
                logger.warning("DIGEST_USER_NOT_FOUND | user_id=%d", user_id)
                return None

        log_entry = notif_dispatcher.notify_daily_digest(
            db,
            user_id=user_id,
            target_date=d,
        )
        if log_entry:
            log_event(
                logger,
                "DIGEST_JOB_COMPLETED",
                user_id=user_id,
                log_id=log_entry.id,
                status=log_entry.status,
            )
        else:
            logger.info("DIGEST_JOB_SKIPPED | user_id=%d | date=%s (suppressed/no updates)", user_id, d.isoformat())
        return log_entry
    except Exception as exc:
        logger.error("DIGEST_JOB_FAILED | user_id=%d | error=%s", user_id, exc)
        return None
