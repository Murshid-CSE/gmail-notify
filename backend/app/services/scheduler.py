"""
CareerMail AI — Background Scheduler Service.

Manages background periodic synchronization and morning daily career briefs
using APScheduler 3.x with timezone awareness and concurrency safety.
"""

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any, Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.services.pipeline import (
    PipelineRunResult,
    run_daily_digest_automation,
    run_full_sync_and_extraction_pipeline,
)
from app.utils.logging import get_logger, log_event

logger = get_logger("services.scheduler")

JOB_ID_PERIODIC_SYNC = "periodic_sync"
JOB_ID_DAILY_DIGEST = "daily_digest"


class CareerMailScheduler:
    """Manages APScheduler background jobs for Gmail synchronization and Daily Briefs."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._tz = ZoneInfo(self._settings.DEFAULT_TIMEZONE)
        self._scheduler: Optional[BackgroundScheduler] = None
        self._is_paused: bool = False
        self._sync_lock = threading.Lock()
        self._digest_lock = threading.Lock()

        # Operational metrics (in-memory)
        self.last_sync_started_at: Optional[datetime] = None
        self.last_sync_finished_at: Optional[datetime] = None
        self.last_sync_success: Optional[bool] = None
        self.last_sync_result: Optional[dict[str, Any]] = None

        self.last_digest_started_at: Optional[datetime] = None
        self.last_digest_finished_at: Optional[datetime] = None
        self.last_digest_success: Optional[bool] = None
        self.last_digest_result: Optional[dict[str, Any]] = None

    @property
    def is_running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def start(self) -> None:
        """Initialize and start the background scheduler if enabled."""
        if not self._settings.scheduler_active:
            logger.info("SCHEDULER_DISABLED | scheduler_enabled=%s, environment=%s",
                        self._settings.SCHEDULER_ENABLED, self._settings.ENVIRONMENT)
            return

        if self.is_running:
            logger.warning("SCHEDULER_ALREADY_RUNNING")
            return

        self._scheduler = BackgroundScheduler(timezone=self._tz)

        # ── Job 1: Periodic Gmail Sync ────────────────────────
        self._scheduler.add_job(
            func=self._scheduled_sync_wrapper,
            trigger=IntervalTrigger(
                minutes=self._settings.SYNC_INTERVAL_MINUTES,
                timezone=self._tz,
            ),
            id=JOB_ID_PERIODIC_SYNC,
            name="Periodic Gmail Sync",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

        # ── Job 2: Daily Digest Brief ─────────────────────────
        self._scheduler.add_job(
            func=self._scheduled_digest_wrapper,
            trigger=CronTrigger(
                hour=self._settings.DAILY_DIGEST_HOUR,
                minute=self._settings.DAILY_DIGEST_MINUTE,
                timezone=self._tz,
            ),
            id=JOB_ID_DAILY_DIGEST,
            name="Daily Career Brief",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

        self._scheduler.start()
        self._is_paused = False

        log_event(
            logger,
            "SCHEDULER_STARTED",
            sync_interval_minutes=self._settings.SYNC_INTERVAL_MINUTES,
            daily_digest_hour=self._settings.DAILY_DIGEST_HOUR,
            daily_digest_minute=self._settings.DAILY_DIGEST_MINUTE,
            timezone=self._settings.DEFAULT_TIMEZONE,
        )

    def shutdown(self, wait: bool = False) -> None:
        """Gracefully stop the scheduler and background worker threads."""
        if self._scheduler is not None and self._scheduler.running:
            self._scheduler.shutdown(wait=wait)
            self._scheduler = None
            self._is_paused = False
            log_event(logger, "SCHEDULER_SHUTDOWN")

    def pause(self) -> None:
        """Pause execution of scheduled background jobs."""
        if self._scheduler is not None and self._scheduler.running:
            self._scheduler.pause()
            self._is_paused = True
            log_event(logger, "SCHEDULER_PAUSED")

    def resume(self) -> None:
        """Resume execution of scheduled background jobs."""
        if self._scheduler is not None and self._scheduler.running:
            self._scheduler.resume()
            self._is_paused = False
            log_event(logger, "SCHEDULER_RESUMED")

    def trigger_sync_job_now(self) -> dict[str, Any]:
        """Execute the full sync & extraction pipeline immediately with concurrency protection."""
        acquired = self._sync_lock.acquire(blocking=False)
        if not acquired:
            logger.warning("SYNC_JOB_SKIPPED | reason=already_running")
            return {
                "success": False,
                "skipped": True,
                "message": "Pipeline execution is already in progress",
            }

        self.last_sync_started_at = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            pipeline_result: PipelineRunResult = run_full_sync_and_extraction_pipeline(db)
            self.last_sync_finished_at = datetime.now(timezone.utc)
            self.last_sync_success = pipeline_result.success
            self.last_sync_result = pipeline_result.to_dict()

            return {
                "success": pipeline_result.success,
                "message": (
                    f"Pipeline completed: {pipeline_result.accounts_succeeded}/{pipeline_result.accounts_total} "
                    f"accounts synced, {pipeline_result.emails_ingested} emails ingested, "
                    f"{pipeline_result.emails_extracted} extracted, {pipeline_result.deadline_alerts_sent} alerts"
                ),
                "details": pipeline_result.to_dict(),
            }
        except Exception as exc:
            self.last_sync_finished_at = datetime.now(timezone.utc)
            self.last_sync_success = False
            error_details = {"error": type(exc).__name__, "message": str(exc)}
            self.last_sync_result = error_details
            logger.error("SYNC_JOB_MANUAL_FAILED | error=%s", exc)
            return {
                "success": False,
                "message": f"Pipeline execution failed: {type(exc).__name__}",
                "details": error_details,
            }
        finally:
            db.close()
            self._sync_lock.release()

    def trigger_digest_job_now(self, user_id: int = 1) -> dict[str, Any]:
        """Execute the morning daily digest brief immediately."""
        acquired = self._digest_lock.acquire(blocking=False)
        if not acquired:
            logger.warning("DIGEST_JOB_SKIPPED | reason=already_running")
            return {
                "success": False,
                "skipped": True,
                "message": "Daily digest automation is already in progress",
            }

        self.last_digest_started_at = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            log_entry = run_daily_digest_automation(db, user_id=user_id)
            self.last_digest_finished_at = datetime.now(timezone.utc)
            success = log_entry is not None and log_entry.status in ("sent", "mock_sent")
            self.last_digest_success = success
            details = {
                "user_id": user_id,
                "status": log_entry.status if log_entry else "skipped",
                "notification_id": log_entry.id if log_entry else None,
            }
            self.last_digest_result = details
            return {
                "success": success,
                "message": (
                    f"Daily digest triggered: status={details['status']}, notification_id={details['notification_id']}"
                ),
                "details": details,
            }
        except Exception as exc:
            self.last_digest_finished_at = datetime.now(timezone.utc)
            self.last_digest_success = False
            error_details = {"error": type(exc).__name__, "message": str(exc)}
            self.last_digest_result = error_details
            logger.error("DIGEST_JOB_MANUAL_FAILED | error=%s", exc)
            return {
                "success": False,
                "message": f"Daily digest automation failed: {type(exc).__name__}",
                "details": error_details,
            }
        finally:
            db.close()
            self._digest_lock.release()

    def get_status(self) -> dict[str, Any]:
        """Return safe operational state and registered job details."""
        jobs_info = []
        if self._scheduler is not None and self._scheduler.running:
            for job in self._scheduler.get_jobs():
                jobs_info.append(
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run_time": job.next_run_time,
                        "is_paused": job.next_run_time is None or self._is_paused,
                        "trigger": str(job.trigger),
                    }
                )

        daily_digest_time = (
            f"{self._settings.DAILY_DIGEST_HOUR:02d}:{self._settings.DAILY_DIGEST_MINUTE:02d}"
        )

        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "scheduler_enabled": self._settings.scheduler_active,
            "sync_interval_minutes": self._settings.SYNC_INTERVAL_MINUTES,
            "daily_digest_time": daily_digest_time,
            "timezone": self._settings.DEFAULT_TIMEZONE,
            "jobs": jobs_info,
            "last_sync_started_at": self.last_sync_started_at,
            "last_sync_finished_at": self.last_sync_finished_at,
            "last_sync_success": self.last_sync_success,
            "last_sync_result": self.last_sync_result,
            "last_digest_started_at": self.last_digest_started_at,
            "last_digest_finished_at": self.last_digest_finished_at,
            "last_digest_success": self.last_digest_success,
        }

    # ── Background wrappers called by APScheduler ─────────────

    def _scheduled_sync_wrapper(self) -> None:
        try:
            logger.info("SCHEDULED_SYNC_JOB_TRIGGERED")
            self.trigger_sync_job_now()
        except Exception as exc:
            logger.error("SCHEDULED_SYNC_JOB_UNHANDLED_ERROR | error=%s", exc)

    def _scheduled_digest_wrapper(self) -> None:
        try:
            logger.info("SCHEDULED_DIGEST_JOB_TRIGGERED")
            self.trigger_digest_job_now()
        except Exception as exc:
            logger.error("SCHEDULED_DIGEST_JOB_UNHANDLED_ERROR | error=%s", exc)


# ── Global Singleton Accessor ─────────────────────────────────

_scheduler_instance: Optional[CareerMailScheduler] = None
_scheduler_singleton_lock = threading.Lock()


def get_scheduler() -> CareerMailScheduler:
    """Retrieve or initialize the process-wide CareerMailScheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        with _scheduler_singleton_lock:
            if _scheduler_instance is None:
                _scheduler_instance = CareerMailScheduler()
    return _scheduler_instance


def reset_scheduler() -> None:
    """Helper used during testing to reset the scheduler singleton."""
    global _scheduler_instance
    with _scheduler_singleton_lock:
        if _scheduler_instance is not None:
            if _scheduler_instance.is_running:
                _scheduler_instance.shutdown(wait=False)
            _scheduler_instance = None
