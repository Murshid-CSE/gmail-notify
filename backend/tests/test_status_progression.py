"""
CareerMail AI — Status Progression & Downgrade Protection Tests.

Tests:
  • Status rank precedence (opportunity < registered < shortlisted < next_round < selected < rejected).
  • Legitimate status progressions (e.g. registered → shortlisted → next_round).
  • Downgrade protection (older email must not revert an advanced status).
  • Duplicate status transition prevention (no shortlisted → shortlisted).
  • Terminal status enforcement (rejected / completed cannot be overwritten by earlier statuses).
  • Unknown / informational status cannot overwrite an active status.
"""

from datetime import datetime, timezone
import pytest

from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.models.opportunity import Opportunity
from app.models.status_history import OpportunityStatusHistory
from app.models.user import User
from app.services.opportunities.manager import (
    STATUS_RANK,
    record_status_history,
    should_update_status,
    update_status,
)


class TestStatusPrecedence:
    def test_rank_ordering(self):
        assert STATUS_RANK["opportunity"] < STATUS_RANK["registered"]
        assert STATUS_RANK["registered"] < STATUS_RANK["shortlisted"]
        assert STATUS_RANK["shortlisted"] < STATUS_RANK["next_round"]
        assert STATUS_RANK["next_round"] < STATUS_RANK["selected"]
        assert STATUS_RANK["selected"] < STATUS_RANK["rejected"]

    def test_legitimate_upgrades(self):
        assert should_update_status("opportunity", "registered") is True
        assert should_update_status("registered", "shortlisted") is True
        assert should_update_status("shortlisted", "next_round") is True
        assert should_update_status("next_round", "selected") is True
        assert should_update_status("shortlisted", "rejected") is True
        assert should_update_status("registered", "assessment") is True
        assert should_update_status("assessment", "interview") is True
        assert should_update_status("interview", "selected") is True

    def test_downgrade_prevention(self):
        # Once shortlisted, older opportunity email cannot downgrade it
        assert should_update_status("shortlisted", "opportunity") is False
        assert should_update_status("shortlisted", "registered") is False

        # Once next_round, older shortlisted email cannot downgrade it
        assert should_update_status("next_round", "shortlisted") is False
        assert should_update_status("next_round", "registered") is False

        # Once selected, cannot downgrade to interview
        assert should_update_status("selected", "interview") is False

        # Once rejected, cannot revert to registered
        assert should_update_status("rejected", "registered") is False

    def test_same_status_returns_false(self):
        assert should_update_status("shortlisted", "shortlisted") is False
        assert should_update_status("registered", "registered") is False

    def test_unknown_or_informational_cannot_overwrite(self):
        assert should_update_status("shortlisted", "unknown") is False
        assert should_update_status("shortlisted", "informational") is False
        assert should_update_status("registered", "") is False


class TestStatusDBTransitions:
    def _setup_user_and_opp(self, db, initial_status="registered"):
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, display_name="Test User")
            db.add(user)
            db.commit()

        acc = EmailAccount(
            user_id=1,
            email_address="test.progression@gmail.com",
            encrypted_access_token="tok",
            encrypted_refresh_token="ref",
        )
        db.add(acc)
        db.commit()
        db.refresh(acc)

        email = EmailMessage(
            account_id=acc.id,
            gmail_message_id="msg_prog_1",
            gmail_thread_id="th_prog_1",
            sender="team@xyz.com",
            subject="XYZ Update",
            received_at=datetime.now(timezone.utc),
            processing_status="pending",
        )
        db.add(email)
        db.commit()
        db.refresh(email)

        opp = Opportunity(
            user_id=1,
            category="hackathon",
            title="XYZ Hackathon",
            status=initial_status,
            first_seen_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        db.add(opp)
        db.commit()
        db.refresh(opp)
        return opp, email

    def test_successful_status_update_and_history_creation(self, db):
        opp, email = self._setup_user_and_opp(db, initial_status="registered")

        changed = update_status(
            db,
            opportunity=opp,
            new_status="shortlisted",
            source_email_id=email.id,
            changed_at=datetime.now(timezone.utc),
        )
        db.commit()

        assert changed is True
        assert opp.status == "shortlisted"

        # Verify status history record
        history = (
            db.query(OpportunityStatusHistory)
            .filter(OpportunityStatusHistory.opportunity_id == opp.id)
            .all()
        )
        assert len(history) == 1
        assert history[0].old_status == "registered"
        assert history[0].new_status == "shortlisted"
        assert history[0].source_email_id == email.id

    def test_downgrade_prevented_in_database(self, db):
        opp, email = self._setup_user_and_opp(db, initial_status="next_round")

        # Older email with "shortlisted" status arrives
        changed = update_status(
            db,
            opportunity=opp,
            new_status="shortlisted",
            source_email_id=email.id,
        )
        db.commit()

        assert changed is False
        assert opp.status == "next_round"  # Must NOT be downgraded

        # No history record created
        history_count = (
            db.query(OpportunityStatusHistory)
            .filter(OpportunityStatusHistory.opportunity_id == opp.id)
            .count()
        )
        assert history_count == 0

    def test_duplicate_status_transition_prevented(self, db):
        opp, email = self._setup_user_and_opp(db, initial_status="registered")

        # First transition
        update_status(db, opp, "shortlisted", source_email_id=email.id)
        db.commit()

        # Same email processed again
        h2 = record_status_history(
            db,
            opportunity_id=opp.id,
            old_status="registered",
            new_status="shortlisted",
            source_email_id=email.id,
        )
        db.commit()

        history = (
            db.query(OpportunityStatusHistory)
            .filter(OpportunityStatusHistory.opportunity_id == opp.id)
            .all()
        )
        assert len(history) == 1  # No duplicate history record
