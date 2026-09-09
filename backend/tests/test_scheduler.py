"""
Tests for CareerMail AI Scheduler Service & Endpoints (Milestone 7).

Verifies:
  1. Scheduler settings validation (invalid intervals, hours, minutes, timezones)
  2. Safety: disabled by default in tests (no background jobs started accidentally)
  3. Lifecycle: start, shutdown, pause, resume
  4. Stable job IDs: periodic_sync and daily_digest
  5. Concurrency protection: sync job cannot overlap with another sync execution
  6. Operational status metrics formatting
  7. Scheduler API endpoints:
     • GET /scheduler/status
     • POST /scheduler/trigger/sync
     • POST /scheduler/trigger/digest
     • POST /scheduler/pause
     • POST /scheduler/resume
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import threading
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.user import User
from app.services.pipeline import PipelineRunResult
from app.services.scheduler import (
    JOB_ID_DAILY_DIGEST,
    JOB_ID_PERIODIC_SYNC,
    CareerMailScheduler,
    get_scheduler,
    reset_scheduler,
)


@pytest.fixture(autouse=True)
def clean_scheduler_state():
    """Ensure singleton scheduler is clean before and after each test."""
    reset_scheduler()
    yield
    reset_scheduler()


@pytest.fixture(autouse=True)
def ensure_default_user(db: Session):
    """Ensure test user exists for foreign key constraints."""
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, display_name="Test Student")
        db.add(user)
        db.commit()
    return user


# ── 1. Configuration Validation Tests ──────────────────────────


def test_scheduler_config_valid():
    """Valid scheduler settings parse cleanly."""
    settings = Settings(
        SCHEDULER_ENABLED=True,
        SYNC_INTERVAL_MINUTES=30,
        DAILY_DIGEST_HOUR=9,
        DAILY_DIGEST_MINUTE=30,
        DEFAULT_TIMEZONE="Asia/Kolkata",
    )
    assert settings.SYNC_INTERVAL_MINUTES == 30
    assert settings.DAILY_DIGEST_HOUR == 9
    assert settings.DAILY_DIGEST_MINUTE == 30
    assert settings.DEFAULT_TIMEZONE == "Asia/Kolkata"


def test_scheduler_config_invalid_interval():
    """Interval <= 0 must fail validation."""
    with pytest.raises(ValidationError):
        Settings(SYNC_INTERVAL_MINUTES=0)

    with pytest.raises(ValidationError):
        Settings(SYNC_INTERVAL_MINUTES=-5)


def test_scheduler_config_invalid_hour():
    """Hour must be between 0 and 23."""
    with pytest.raises(ValidationError):
        Settings(DAILY_DIGEST_HOUR=24)

    with pytest.raises(ValidationError):
        Settings(DAILY_DIGEST_HOUR=-1)


def test_scheduler_config_invalid_minute():
    """Minute must be between 0 and 59."""
    with pytest.raises(ValidationError):
        Settings(DAILY_DIGEST_MINUTE=60)

    with pytest.raises(ValidationError):
        Settings(DAILY_DIGEST_MINUTE=-1)


def test_scheduler_config_invalid_timezone():
    """Invalid timezone identifier must fail validation with a clear message."""
    with pytest.raises(ValidationError, match="Invalid DEFAULT_TIMEZONE"):
        Settings(DEFAULT_TIMEZONE="Atlantis/Unknown")


# ── 2. Scheduler Safety Rule: Disabled in Tests ───────────────


def test_scheduler_disabled_in_test_environment():
    """In test environment, scheduler_active is False even if SCHEDULER_ENABLED=true."""
    settings = Settings(ENVIRONMENT="test", SCHEDULER_ENABLED=True)
    assert settings.scheduler_active is False

    scheduler = CareerMailScheduler(settings=settings)
    scheduler.start()
    # APScheduler should NOT start
    assert scheduler.is_running is False


# ── 3. Lifecycle & Stable Job IDs ─────────────────────────────


def test_scheduler_lifecycle_and_stable_job_ids():
    """When active, scheduler starts with stable job IDs and shuts down cleanly."""
    settings = Settings(ENVIRONMENT="production", SCHEDULER_ENABLED=True)
    assert settings.scheduler_active is True

    scheduler = CareerMailScheduler(settings=settings)
    try:
        scheduler.start()
        assert scheduler.is_running is True
        assert scheduler.is_paused is False

        status = scheduler.get_status()
        assert status["is_running"] is True
        assert status["is_paused"] is False
        assert status["scheduler_enabled"] is True
        assert status["sync_interval_minutes"] == 15
        assert status["daily_digest_time"] == "08:00"
        assert status["timezone"] == "Asia/Kolkata"

        job_ids = [j["id"] for j in status["jobs"]]
        assert JOB_ID_PERIODIC_SYNC in job_ids
        assert JOB_ID_DAILY_DIGEST in job_ids

        # Test Pause
        scheduler.pause()
        assert scheduler.is_paused is True
        pause_status = scheduler.get_status()
        assert pause_status["is_paused"] is True

        # Test Resume
        scheduler.resume()
        assert scheduler.is_paused is False
    finally:
        scheduler.shutdown(wait=False)
        assert scheduler.is_running is False


# ── 4. Concurrency Protection ──────────────────────────────────


def test_scheduler_concurrency_lock():
    """A running sync pipeline blocks a second overlapping sync execution."""
    scheduler = CareerMailScheduler()

    # Simulate an active sync holding the lock
    lock_acquired = scheduler._sync_lock.acquire(blocking=False)
    assert lock_acquired is True

    try:
        # Second call must be safely rejected / skipped
        res = scheduler.trigger_sync_job_now()
        assert res["success"] is False
        assert res.get("skipped") is True
        assert "already in progress" in res["message"]
    finally:
        scheduler._sync_lock.release()


# ── 5. Manual Triggers & Operational Metrics ───────────────────


def test_scheduler_manual_sync_trigger(db: Session):
    """trigger_sync_job_now runs the pipeline and updates in-memory metrics."""
    scheduler = CareerMailScheduler()

    mock_result = PipelineRunResult(
        accounts_total=1,
        accounts_succeeded=1,
        accounts_failed=0,
        emails_ingested=2,
        emails_extracted=1,
        deadline_alerts_sent=0,
        duration_seconds=0.5,
        success=True,
    )

    with patch("app.services.scheduler.run_full_sync_and_extraction_pipeline", return_value=mock_result):
        resp = scheduler.trigger_sync_job_now()

    assert resp["success"] is True
    assert "Pipeline completed" in resp["message"]
    assert scheduler.last_sync_success is True
    assert scheduler.last_sync_finished_at is not None
    assert scheduler.last_sync_result["emails_ingested"] == 2


def test_scheduler_manual_digest_trigger(db: Session):
    """trigger_digest_job_now runs digest automation and updates metrics."""
    scheduler = CareerMailScheduler()

    mock_log = MagicMock()
    mock_log.id = 99
    mock_log.status = "mock_sent"

    with patch("app.services.scheduler.run_daily_digest_automation", return_value=mock_log):
        resp = scheduler.trigger_digest_job_now(user_id=1)

    assert resp["success"] is True
    assert "Daily digest triggered" in resp["message"]
    assert scheduler.last_digest_success is True
    assert scheduler.last_digest_result["notification_id"] == 99


# ── 6. REST API Endpoints ─────────────────────────────────────


def test_api_get_scheduler_status(client):
    """GET /scheduler/status returns current operational details."""
    response = client.get("/scheduler/status")
    assert response.status_code == 200
    data = response.json()

    assert "is_running" in data
    assert "is_paused" in data
    assert "sync_interval_minutes" in data
    assert "daily_digest_time" in data
    assert "timezone" in data
    assert "jobs" in data
    # No credentials exposed
    assert "password" not in data
    assert "token" not in data


def test_api_trigger_sync(client):
    """POST /scheduler/trigger/sync manually invokes the pipeline."""
    mock_result = PipelineRunResult(
        accounts_total=0,
        accounts_succeeded=0,
        accounts_failed=0,
        emails_ingested=0,
        emails_extracted=0,
        duration_seconds=0.1,
        success=True,
    )

    with patch("app.services.scheduler.run_full_sync_and_extraction_pipeline", return_value=mock_result):
        response = client.post("/scheduler/trigger/sync")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Pipeline completed" in data["message"]


def test_api_trigger_digest(client):
    """POST /scheduler/trigger/digest triggers daily career brief."""
    mock_log = MagicMock()
    mock_log.id = 42
    mock_log.status = "mock_sent"

    with patch("app.services.scheduler.run_daily_digest_automation", return_value=mock_log):
        response = client.post("/scheduler/trigger/digest?user_id=1")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["details"]["notification_id"] == 42


def test_api_pause_and_resume_when_not_running(client):
    """Pause and resume return appropriate status when scheduler is not running."""
    resp_pause = client.post("/scheduler/pause")
    assert resp_pause.status_code == 200
    assert resp_pause.json()["success"] is False
    assert "not running" in resp_pause.json()["message"]

    resp_resume = client.post("/scheduler/resume")
    assert resp_resume.status_code == 200
    assert resp_resume.json()["success"] is False
    assert "not running" in resp_resume.json()["message"]


def test_api_pause_and_resume_when_running(client):
    """Pause and resume succeed when scheduler is running."""
    scheduler = get_scheduler()
    scheduler._settings = Settings(ENVIRONMENT="production", SCHEDULER_ENABLED=True)
    scheduler.start()

    try:
        resp_pause = client.post("/scheduler/pause")
        assert resp_pause.status_code == 200
        assert resp_pause.json()["success"] is True
        assert resp_pause.json()["is_paused"] is True

        resp_resume = client.post("/scheduler/resume")
        assert resp_resume.status_code == 200
        assert resp_resume.json()["success"] is True
        assert resp_resume.json()["is_paused"] is False
    finally:
        scheduler.shutdown(wait=False)
