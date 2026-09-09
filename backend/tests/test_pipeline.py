"""
Tests for CareerMail AI Centralized Pipeline Service (Milestone 7).

Verifies:
  1. Multiple active Gmail accounts processed sequentially
  2. Account isolation: One account failure does not abort remaining accounts
  3. Safe empty execution when 0 accounts exist
  4. Integration with AI extraction batching
  5. Deadline evaluation: only qualifying deadlines trigger alerts
  6. Idempotency and notification deduplication (respecting 6h cooldown)
  7. Daily digest automation execution
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.device import DeviceToken
from app.models.email_account import EmailAccount
from app.models.notification import NotificationLog
from app.models.opportunity import Opportunity
from app.models.user import User
from app.services.notifications.dispatcher import NotificationDispatcher
from app.services.pipeline import (
    PipelineRunResult,
    run_daily_digest_automation,
    run_full_sync_and_extraction_pipeline,
)


@pytest.fixture(autouse=True)
def ensure_default_user(db: Session):
    """Ensure test user exists for foreign key constraints."""
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, display_name="Test Student")
        db.add(user)
        db.commit()
    return user


def _create_account(db: Session, email: str, is_active: bool = True) -> EmailAccount:
    account = EmailAccount(
        user_id=1,
        provider="gmail",
        email_address=email,
        encrypted_access_token="test-access-token",
        encrypted_refresh_token="test-refresh-token",
        token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        is_active=is_active,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def test_pipeline_no_accounts(db: Session):
    """Pipeline runs cleanly when no active accounts are present."""
    result = run_full_sync_and_extraction_pipeline(db)

    assert result.success is True
    assert result.accounts_total == 0
    assert result.accounts_succeeded == 0
    assert result.accounts_failed == 0
    assert result.emails_ingested == 0
    assert result.emails_extracted == 0
    assert result.deadline_alerts_sent == 0
    assert len(result.errors) == 0


def test_pipeline_multiple_accounts_success(db: Session):
    """Pipeline synchronizes all active accounts successfully."""
    _create_account(db, "student1@college.edu")
    _create_account(db, "student2@college.edu")

    mock_sync_result = MagicMock()
    mock_sync_result.new_messages = 5
    mock_sync_result.skipped_duplicates = 2

    with patch("app.services.pipeline.sync_account", return_value=mock_sync_result) as mock_sync:
        with patch("app.services.pipeline.process_pending_emails", return_value={"extracted": 4, "filtered_out": 1}):
            result = run_full_sync_and_extraction_pipeline(db)

    assert result.success is True
    assert result.accounts_total == 2
    assert result.accounts_succeeded == 2
    assert result.accounts_failed == 0
    assert result.emails_ingested == 10
    assert result.emails_extracted == 4
    assert mock_sync.call_count == 2


def test_pipeline_account_isolation(db: Session):
    """Account 1 failure does not abort Account 2; returns structured isolation metrics."""
    acc1 = _create_account(db, "broken@college.edu")
    acc2 = _create_account(db, "working@college.edu")

    def side_effect(db_sess, account):
        if account.id == acc1.id:
            raise RuntimeError("OAuth token revoked by Google")
        res = MagicMock()
        res.new_messages = 3
        res.skipped_duplicates = 0
        return res

    with patch("app.services.pipeline.sync_account", side_effect=side_effect):
        with patch("app.services.pipeline.process_pending_emails", return_value={"extracted": 2}):
            result = run_full_sync_and_extraction_pipeline(db)

    assert result.accounts_total == 2
    assert result.accounts_succeeded == 1
    assert result.accounts_failed == 1
    assert result.emails_ingested == 3
    assert result.emails_extracted == 2
    assert result.success is False
    assert len(result.errors) == 1
    assert f"Account {acc1.id} (broken@college.edu): RuntimeError" in result.errors[0]


def test_pipeline_approaching_deadline_scan(db: Session):
    """Only opportunities with approaching deadlines (today/tomorrow) receive alerts."""
    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()

    # Qualifying 1: Deadline today
    opp_today = Opportunity(
        user_id=1,
        title="Hackathon Alpha",
        category="hackathon",
        status="detected",
        deadline=datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc),
    )
    # Qualifying 2: Deadline tomorrow
    opp_tomorrow = Opportunity(
        user_id=1,
        title="Internship Beta",
        category="internship",
        status="detected",
        deadline=datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc),
    )
    # Non-qualifying: Deadline in 10 days
    opp_future = Opportunity(
        user_id=1,
        title="Fellowship Gamma",
        category="job",
        status="detected",
        deadline=datetime.combine(today + timedelta(days=10), datetime.min.time(), tzinfo=timezone.utc),
    )
    # Non-qualifying: Opportunity already rejected
    opp_rejected = Opportunity(
        user_id=1,
        title="Past Event",
        category="hackathon",
        status="rejected",
        deadline=datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc),
    )

    db.add_all([opp_today, opp_tomorrow, opp_future, opp_rejected])
    db.commit()

    # Register an active device for user 1
    device = DeviceToken(
        user_id=1,
        fcm_token="device-token-123",
        device_type="android",
        device_name="Test Pixel",
        is_active=True,
    )
    db.add(device)
    db.commit()

    dispatcher = NotificationDispatcher()

    with patch("app.services.pipeline.sync_account"):
        with patch("app.services.pipeline.process_pending_emails", return_value={"extracted": 0}):
            result = run_full_sync_and_extraction_pipeline(db, dispatcher=dispatcher)

    # Only opp_today and opp_tomorrow qualify for approaching deadline alerts
    assert result.deadline_alerts_sent == 2


def test_pipeline_notification_deduplication(db: Session):
    """Running pipeline consecutively respects the 6-hour notification cooldown."""
    today = datetime.now(timezone.utc).date()
    opp = Opportunity(
        user_id=1,
        title="Hackathon Delta",
        category="hackathon",
        status="detected",
        deadline=datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc),
    )
    db.add(opp)
    db.commit()

    device = DeviceToken(
        user_id=1,
        fcm_token="device-token-abc",
        device_type="android",
        device_name="Test Device",
        is_active=True,
    )
    db.add(device)
    db.commit()

    dispatcher = NotificationDispatcher()

    with patch("app.services.pipeline.sync_account"):
        with patch("app.services.pipeline.process_pending_emails", return_value={"extracted": 0}):
            # First run: alert sent
            res1 = run_full_sync_and_extraction_pipeline(db, dispatcher=dispatcher)
            assert res1.deadline_alerts_sent == 1

            # Second run (immediate): cooldown prevents duplicate alert
            res2 = run_full_sync_and_extraction_pipeline(db, dispatcher=dispatcher)
            assert res2.deadline_alerts_sent == 0


def test_daily_digest_automation(db: Session):
    """run_daily_digest_automation invokes deterministic digest and dispatches brief."""
    device = DeviceToken(
        user_id=1,
        fcm_token="device-token-xyz",
        device_type="android",
        device_name="Test Device",
        is_active=True,
    )
    db.add(device)

    opp = Opportunity(
        user_id=1,
        title="Internship Omega",
        category="internship",
        status="detected",
        deadline=datetime.now(timezone.utc) + timedelta(days=2),
    )
    db.add(opp)
    db.commit()

    dispatcher = NotificationDispatcher()
    log_entry = run_daily_digest_automation(db, user_id=1, dispatcher=dispatcher)

    assert log_entry is not None
    assert log_entry.notification_type == "digest"
    assert log_entry.status in ("sent", "mock_sent")
    assert "Omega" in log_entry.body or "Career Brief" in log_entry.title
