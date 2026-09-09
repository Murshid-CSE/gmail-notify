"""
CareerMail AI — Notification Service & Dispatcher Tests.

Validates:
  • Mock FCM execution when credentials are not configured
  • Failed delivery simulation without crashing
  • Invalid token detection and automatic deactivation
  • Status change decision rules and 6-hour cooldown deduplication
  • Different status events on the same opportunity are not blocked
  • Urgent action and deadline alerts
  • Daily digest push brief generation
  • API endpoints: POST /notifications/test and GET /notifications/history
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.models.device import DeviceToken
from app.models.notification import NotificationLog
from app.models.opportunity import Opportunity
from app.models.user import User
from app.services.notifications.dispatcher import NotificationDispatcher
from app.services.notifications.fcm import FCMClient, FCMResult


@pytest.fixture(autouse=True)
def ensure_default_user(db):
    """Ensure default user exists for foreign key constraints."""
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, display_name="Test User")
        db.add(user)
        db.commit()


@pytest.fixture
def sample_device(db):
    """Register an active test device."""
    dev = DeviceToken(
        user_id=1,
        fcm_token="test-active-fcm-token-12345",
        device_type="android",
        device_name="Test Pixel",
        is_active=True,
    )
    db.add(dev)
    db.commit()
    return dev


@pytest.fixture
def sample_opportunity(db):
    """Create a sample opportunity in the database."""
    opp = Opportunity(
        user_id=1,
        category="hackathon",
        title="Smart India Hackathon 2026",
        organization="Ministry of Education",
        status="registered",
        priority="high",
        action_required=False,
    )
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp


class TestFCMClient:
    """Test FCMClient abstraction behavior in mock and error scenarios."""

    def test_mock_mode_when_no_credentials(self):
        client = FCMClient(credentials_path="")
        assert client.is_live is False

        result = client.send_to_tokens(
            tokens=["token-1", "token-2"],
            title="Test Title",
            body="Test Body",
            data_payload={"type": "opportunity", "opportunity_id": "1"},
        )
        assert result.success is True
        assert result.status == "mock_sent"
        assert result.recipient_count == 2
        assert result.message_id.startswith("mock-msg-")
        assert "mock" in result.detail.lower()

    def test_send_to_empty_tokens_returns_gracefully(self):
        client = FCMClient(credentials_path="")
        result = client.send_to_tokens(
            tokens=[],
            title="Empty",
            body="Empty body",
        )
        assert result.success is True
        assert result.recipient_count == 0

    def test_failed_fcm_dispatch_does_not_crash(self):
        client = FCMClient(credentials_path="")
        # Force live mode with mocked failing firebase messaging
        client.is_live = True
        client._app = MagicMock()

        with patch("firebase_admin.messaging.send_each_for_multicast", side_effect=Exception("FCM service unavailable")):
            result = client.send_to_tokens(
                tokens=["token-1"],
                title="Fail Test",
                body="Body",
            )
            assert result.success is False
            assert result.status == "failed"
            assert result.recipient_count == 0
            assert "FCM service unavailable" in result.detail


class TestNotificationDispatcher:
    """Test decision rules, deduplication, and cooldowns."""

    def test_status_change_meaningful_transition(self, db, sample_device, sample_opportunity):
        dispatcher = NotificationDispatcher()

        # registered -> shortlisted (high value transition)
        log = dispatcher.notify_status_change(
            db,
            opportunity=sample_opportunity,
            old_status="registered",
            new_status="shortlisted",
        )
        assert log is not None
        assert log.status == "mock_sent"
        assert log.notification_type == "status_change"
        assert "Shortlisted" in log.body
        assert log.data_payload.get("opportunity_id") == str(sample_opportunity.id)

    def test_status_change_no_op_ignored(self, db, sample_opportunity):
        dispatcher = NotificationDispatcher()

        # old_status == new_status should produce no notification
        log = dispatcher.notify_status_change(
            db,
            opportunity=sample_opportunity,
            old_status="interview",
            new_status="interview",
        )
        assert log is None

    def test_status_change_low_value_ignored(self, db, sample_opportunity):
        dispatcher = NotificationDispatcher()

        # unknown -> informational is not high value
        log = dispatcher.notify_status_change(
            db,
            opportunity=sample_opportunity,
            old_status="unknown",
            new_status="informational",
        )
        assert log is None

    def test_six_hour_cooldown_deduplication(self, db, sample_device, sample_opportunity):
        dispatcher = NotificationDispatcher()

        # First send
        log1 = dispatcher.notify_status_change(
            db,
            opportunity=sample_opportunity,
            old_status="shortlisted",
            new_status="next_round",
        )
        assert log1 is not None

        # Same event within cooldown window should be suppressed
        log2 = dispatcher.notify_status_change(
            db,
            opportunity=sample_opportunity,
            old_status="shortlisted",
            new_status="next_round",
        )
        assert log2 is None

    def test_different_status_events_not_blocked(self, db, sample_device, sample_opportunity):
        dispatcher = NotificationDispatcher()

        # Event 1: shortlisted -> next_round
        log1 = dispatcher.notify_status_change(
            db,
            opportunity=sample_opportunity,
            old_status="shortlisted",
            new_status="next_round",
        )
        assert log1 is not None

        # Event 2: next_round -> interview (different status event on SAME opportunity)
        log2 = dispatcher.notify_status_change(
            db,
            opportunity=sample_opportunity,
            old_status="next_round",
            new_status="interview",
        )
        assert log2 is not None
        assert "Interview" in log2.title or "Interview" in log2.body

    def test_event_after_cooldown_expires_allowed(self, db, sample_device, sample_opportunity):
        dispatcher = NotificationDispatcher()

        # Create an old notification from 7 hours ago
        seven_hours_ago = datetime.now(timezone.utc) - timedelta(hours=7)
        old_log = NotificationLog(
            user_id=1,
            opportunity_id=sample_opportunity.id,
            notification_type="status_change",
            title="Old Notification",
            body="Old Body",
            status="mock_sent",
            dedup_key=f"status_change:{sample_opportunity.id}:interview->selected",
            created_at=seven_hours_ago,
        )
        db.add(old_log)
        db.commit()

        # Dispatch same event now — should be allowed because 7h > 6h
        new_log = dispatcher.notify_status_change(
            db,
            opportunity=sample_opportunity,
            old_status="interview",
            new_status="selected",
        )
        assert new_log is not None
        assert new_log.id != old_log.id

    def test_urgent_action_notification(self, db, sample_device, sample_opportunity):
        dispatcher = NotificationDispatcher()
        sample_opportunity.action_required = True
        sample_opportunity.action = "Submit assignment before 11 PM"
        sample_opportunity.deadline = datetime.now(timezone.utc) + timedelta(hours=5)
        db.commit()

        log = dispatcher.notify_urgent_action(db, opportunity=sample_opportunity)
        assert log is not None
        assert log.notification_type == "urgent_action"
        assert "Submit assignment" in log.body

        # Second identical call within cooldown is suppressed
        assert dispatcher.notify_urgent_action(db, opportunity=sample_opportunity) is None

    def test_approaching_deadline_notification(self, db, sample_device, sample_opportunity):
        dispatcher = NotificationDispatcher()
        sample_opportunity.deadline = datetime.now(timezone.utc) + timedelta(hours=12)
        db.commit()

        log = dispatcher.notify_approaching_deadline(db, opportunity=sample_opportunity)
        assert log is not None
        assert log.notification_type == "deadline"
        assert "today" in log.body.lower() or "tomorrow" in log.body.lower()

        # Non-urgent future deadline (e.g. 10 days out) is ignored
        sample_opportunity.deadline = datetime.now(timezone.utc) + timedelta(days=10)
        db.commit()
        assert dispatcher.notify_approaching_deadline(db, opportunity=sample_opportunity) is None

    def test_daily_digest_notification(self, db, sample_device):
        dispatcher = NotificationDispatcher()
        today = date.today()

        log = dispatcher.notify_daily_digest(db, user_id=1, target_date=today)
        assert log is not None
        assert log.notification_type == "digest"
        assert "Today's Career Brief" in log.title

        # Duplicate call on same date is suppressed
        assert dispatcher.notify_daily_digest(db, user_id=1, target_date=today) is None

    def test_invalid_tokens_deactivated(self, db, sample_device):
        fcm_mock = MagicMock()
        fcm_mock.send_to_tokens.return_value = FCMResult(
            success=False,
            status="failed",
            recipient_count=0,
            invalid_tokens=[sample_device.fcm_token],
            detail="Token unregistered",
        )

        dispatcher = NotificationDispatcher(fcm_client=fcm_mock)
        dispatcher.notify_test(db, user_id=1)

        db.refresh(sample_device)
        assert sample_device.is_active is False


class TestNotificationAPI:
    """Test notification endpoints."""

    def test_send_test_notification_endpoint(self, client, sample_device):
        payload = {
            "title": "API Test",
            "body": "API notification test message",
        }
        resp = client.post("/notifications/test", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] in ("sent", "mock_sent")
        assert data["recipient_count"] >= 1

    def test_notification_history_pagination(self, client, db, sample_opportunity):
        # Create test log entries
        for i in range(5):
            entry = NotificationLog(
                user_id=1,
                opportunity_id=sample_opportunity.id,
                notification_type="status_change",
                title=f"Notification #{i}",
                body=f"Body #{i}",
                status="mock_sent",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=i),
            )
            db.add(entry)
        db.commit()

        resp = client.get("/notifications/history?page=1&page_size=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 5
        assert len(data["items"]) == 3
        assert data["page"] == 1
        assert data["page_size"] == 3
        assert data["items"][0]["title"] is not None
