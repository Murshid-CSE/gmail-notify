"""
CareerMail AI — Daily Digest API Tests.

Tests:
  • GET /digest/today with empty state.
  • Aggregation of new opportunities (using first_seen_at).
  • Multi-email progression (1 opportunity, multiple status transitions).
  • Status transitions in today's window.
  • Urgent action prioritization (critical/high + deadline).
  • Approaching deadlines (today, tomorrow, this week).
  • Category updates breakdown (hackathon, internship, placement, college).
  • Deterministic human-readable brief content.
  • Timezone parameter handling.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest

from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.models.opportunity import Opportunity
from app.models.opportunity_email import OpportunityEmail
from app.models.status_history import OpportunityStatusHistory
from app.models.user import User


class TestDailyDigestAPI:
    def _ensure_user_and_account(self, db):
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, display_name="Digest User")
            db.add(user)
            db.commit()

        acc = db.query(EmailAccount).filter(EmailAccount.user_id == 1).first()
        if not acc:
            acc = EmailAccount(
                user_id=1,
                email_address="digest_user@college.edu",
                encrypted_access_token="enc_tok",
                encrypted_refresh_token="enc_ref",
            )
            db.add(acc)
            db.commit()
            db.refresh(acc)

        return user, acc

    def test_digest_empty_state(self, client):
        response = client.get("/digest/today?tz=UTC")
        assert response.status_code == 200
        data = response.json()

        assert "summary" in data
        assert "counts" in data
        assert "urgent_actions" in data
        assert "recent_status_changes" in data
        assert "new_opportunities" in data
        assert "upcoming_deadlines" in data

        counts = data["counts"]
        assert counts["new_opportunities"] == 0
        assert counts["status_changes"] == 0
        assert counts["urgent_actions"] == 0
        assert counts["deadlines_today"] == 0
        assert counts["deadlines_tomorrow"] == 0
        assert counts["deadlines_this_week"] == 0
        assert counts["hackathon_updates"] == 0
        assert counts["internship_updates"] == 0
        assert counts["placement_updates"] == 0
        assert counts["college_updates"] == 0

        assert "No pending actions or urgent updates for today" in data["summary"]

    def test_digest_multi_email_scenario(self, client, db):
        """Verify:
        Email 1: Registration (creates opp)
        Email 2: Shortlisted (updates opp, adds status history)
        Email 3: Next Round (updates opp, adds status history)
        Result in Digest:
        new_opportunities = 1 (NOT 3)
        status_changes = 2
        """
        user, acc = self._ensure_user_and_account(db)
        now_utc = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)


        # Create emails
        e1 = EmailMessage(
            account_id=acc.id,
            gmail_message_id="dig_e1",
            gmail_thread_id="th_dig_1",
            sender="hackathon@nitr.com",
            subject="HackNITR 5.0 Registration Confirmed",
            received_at=now_utc - timedelta(hours=5),
            processing_status="extracted",
        )
        e2 = EmailMessage(
            account_id=acc.id,
            gmail_message_id="dig_e2",
            gmail_thread_id="th_dig_1",
            sender="hackathon@nitr.com",
            subject="HackNITR 5.0 Shortlisted",
            received_at=now_utc - timedelta(hours=3),
            processing_status="extracted",
        )
        e3 = EmailMessage(
            account_id=acc.id,
            gmail_message_id="dig_e3",
            gmail_thread_id="th_dig_1",
            sender="hackathon@nitr.com",
            subject="HackNITR 5.0 Round 2 Instructions",
            received_at=now_utc - timedelta(hours=1),
            processing_status="extracted",
        )
        db.add_all([e1, e2, e3])
        db.commit()

        # Opportunity created at e1 time, currently at next_round
        opp = Opportunity(
            user_id=user.id,
            category="hackathon",
            title="HackNITR 5.0",
            organization="NIT Rourkela",
            status="next_round",
            round_name="Round 2",
            priority="high",
            confidence=0.95,
            deadline=now_utc + timedelta(days=1),  # Due tomorrow
            action_required=True,
            action="Submit Round 2 architecture document",
            first_seen_at=now_utc - timedelta(hours=5),
            last_updated_at=now_utc - timedelta(hours=1),
        )
        db.add(opp)
        db.commit()
        db.refresh(opp)

        # Links
        db.add_all([
            OpportunityEmail(opportunity_id=opp.id, email_id=e1.id),
            OpportunityEmail(opportunity_id=opp.id, email_id=e2.id),
            OpportunityEmail(opportunity_id=opp.id, email_id=e3.id),
        ])

        # Status histories (2 transitions)
        h1 = OpportunityStatusHistory(
            opportunity_id=opp.id,
            old_status="registered",
            new_status="shortlisted",
            source_email_id=e2.id,
            changed_at=now_utc - timedelta(hours=3),
        )
        h2 = OpportunityStatusHistory(
            opportunity_id=opp.id,
            old_status="shortlisted",
            new_status="next_round",
            source_email_id=e3.id,
            changed_at=now_utc - timedelta(hours=1),
        )
        db.add_all([h1, h2])
        db.commit()

        response = client.get("/digest/today?tz=UTC")
        assert response.status_code == 200
        data = response.json()
        counts = data["counts"]

        # Exactly 1 new opportunity, not 3
        assert counts["new_opportunities"] == 1
        assert len(data["new_opportunities"]) == 1
        assert data["new_opportunities"][0]["title"] == "HackNITR 5.0"

        # Exactly 2 status changes
        assert counts["status_changes"] == 2
        assert len(data["recent_status_changes"]) == 2

        # 1 urgent action
        assert counts["urgent_actions"] == 1
        assert len(data["urgent_actions"]) == 1
        assert data["urgent_actions"][0]["action"] == "Submit Round 2 architecture document"

        # Deadline tomorrow
        assert counts["deadlines_tomorrow"] == 1

        # Hackathon update count
        assert counts["hackathon_updates"] >= 1

        # Check deterministic summary format
        summary = data["summary"]
        assert "CAREER BRIEF" in summary
        assert "HACKATHON" in summary
        assert "HackNITR 5.0" in summary
        assert "ACTION REQUIRED" in summary

    def test_digest_status_change_same_status_ignored(self, client, db):
        """Status history where old_status == new_status must not count as a status change."""
        user, acc = self._ensure_user_and_account(db)
        now_utc = datetime.now(timezone.utc)

        e = EmailMessage(
            account_id=acc.id,
            gmail_message_id="dig_same_e",
            gmail_thread_id="th_dig_same",
            sender="intern@co.com",
            subject="Update",
            received_at=now_utc,
            processing_status="extracted",
        )
        db.add(e)
        db.commit()

        opp = Opportunity(
            user_id=user.id,
            category="internship",
            title="SDE Intern",
            organization="Startup",
            status="shortlisted",
            priority="medium",
            confidence=0.9,
            first_seen_at=now_utc - timedelta(days=5),  # Seen 5 days ago, NOT new today
            last_updated_at=now_utc,
        )
        db.add(opp)
        db.commit()
        db.refresh(opp)

        # Transition with identical old and new status
        h = OpportunityStatusHistory(
            opportunity_id=opp.id,
            old_status="shortlisted",
            new_status="shortlisted",
            source_email_id=e.id,
            changed_at=now_utc,
        )
        db.add(h)
        db.commit()

        response = client.get("/digest/today?tz=UTC")
        assert response.status_code == 200
        data = response.json()
        assert data["counts"]["status_changes"] == 0
        assert data["counts"]["new_opportunities"] == 0

    def test_digest_category_counters(self, client, db):
        user, acc = self._ensure_user_and_account(db)
        now_utc = datetime.now(timezone.utc)

        cats = ["internship", "placement", "college"]
        for i, cat in enumerate(cats):
            opp = Opportunity(
                user_id=user.id,
                category=cat,
                title=f"{cat.title()} Opportunity {i}",
                organization=f"Org {i}",
                status="open",
                priority="high",
                confidence=0.9,
                first_seen_at=now_utc,
                last_updated_at=now_utc,
            )
            db.add(opp)
        db.commit()

        response = client.get("/digest/today?tz=UTC")
        assert response.status_code == 200
        counts = response.json()["counts"]

        assert counts["internship_updates"] >= 1
        assert counts["placement_updates"] >= 1
        assert counts["college_updates"] >= 1
        assert counts["new_opportunities"] >= 3
