"""
CareerMail AI — Opportunity Manager Tests.

Tests:
  • The core end-to-end scenario:
      Email 1 (Registration) + Email 2 (Shortlisted) + Email 3 (Round 2)
      ==> ONE opportunity, status=next_round, 3 history entries, 3 source emails.
  • Duplicate email processing (idempotency).
  • Same opportunity arriving from 2 different connected Gmail accounts.
  • Deadline intelligence calculations (today, tomorrow, future, overdue, missing).
  • Robust deadline date parsing across multiple formats.
  • Graceful handling of empty/missing optional fields.
"""

from datetime import datetime, timezone, timedelta
import pytest

from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.models.opportunity import Opportunity
from app.models.opportunity_email import OpportunityEmail
from app.models.status_history import OpportunityStatusHistory
from app.models.user import User
from app.schemas.extraction import Category, EmailAnalysis, Priority, Status
from app.services.opportunities.manager import (
    attach_source_email,
    compute_deadline_state,
    create_or_update_opportunity,
    parse_deadline_datetime,
)


class TestOpportunityManagerPipeline:
    def _setup_environment(self, db):
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, display_name="Test Student")
            db.add(user)
            db.commit()

        acc1 = EmailAccount(
            user_id=1,
            email_address="student.college@gmail.com",
            encrypted_access_token="tok1",
            encrypted_refresh_token="ref1",
        )
        acc2 = EmailAccount(
            user_id=1,
            email_address="student.personal@gmail.com",
            encrypted_access_token="tok2",
            encrypted_refresh_token="ref2",
        )
        db.add_all([acc1, acc2])
        db.commit()
        db.refresh(acc1)
        db.refresh(acc2)
        return user, acc1, acc2

    def test_three_email_progression_single_opportunity(self, db):
        """The critical CareerMail AI test:

        Email 1: 'XYZ Hackathon registration successful' (status=registered)
        Email 2: 'Congratulations! XYZ Hackathon shortlisted' (status=shortlisted)
        Email 3: 'You have advanced to Round 2' (status=next_round)

        Must result in:
          - EXACTLY 1 Opportunity
          - Status = 'next_round'
          - 3 source email references
          - 3 status history entries: (None->registered, registered->shortlisted, shortlisted->next_round)
        """
        user, acc1, _ = self._setup_environment(db)

        # ── Email 1: Registration ─────────────────────────────
        email1 = EmailMessage(
            account_id=acc1.id,
            gmail_message_id="msg_xyz_1",
            gmail_thread_id="th_xyz_1",
            sender="team@xyzhackathon.com",
            subject="XYZ Hackathon registration successful",
            received_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            processing_status="pending",
        )
        db.add(email1)
        db.commit()

        analysis1 = EmailAnalysis(
            category=Category.hackathon,
            title="XYZ Hackathon",
            organization="XYZ Foundation",
            status=Status.registered,
            priority=Priority.medium,
            confidence=0.9,
        )

        opp1, created1, changed1 = create_or_update_opportunity(db, email1, analysis1)
        db.commit()

        assert created1 is True
        assert changed1 is True
        assert opp1.status == "registered"

        # ── Email 2: Shortlisted ──────────────────────────────
        email2 = EmailMessage(
            account_id=acc1.id,
            gmail_message_id="msg_xyz_2",
            gmail_thread_id="th_xyz_1",
            sender="team@xyzhackathon.com",
            subject="Congratulations! XYZ Hackathon shortlisted",
            received_at=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
            processing_status="pending",
        )
        db.add(email2)
        db.commit()

        analysis2 = EmailAnalysis(
            category=Category.hackathon,
            title="XYZ Hackathon",
            organization="XYZ Foundation",
            status=Status.shortlisted,
            priority=Priority.high,
            confidence=0.95,
        )

        opp2, created2, changed2 = create_or_update_opportunity(db, email2, analysis2)
        db.commit()

        assert created2 is False
        assert changed2 is True
        assert opp2.id == opp1.id  # Same opportunity!
        assert opp2.status == "shortlisted"

        # ── Email 3: Round 2 Details ──────────────────────────
        email3 = EmailMessage(
            account_id=acc1.id,
            gmail_message_id="msg_xyz_3",
            gmail_thread_id="th_xyz_1",
            sender="team@xyzhackathon.com",
            subject="You have advanced to Round 2",
            received_at=datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc),
            processing_status="pending",
        )
        db.add(email3)
        db.commit()

        analysis3 = EmailAnalysis(
            category=Category.hackathon,
            title="XYZ Hackathon",
            organization="XYZ Foundation",
            status=Status.next_round,
            round_name="Round 2",
            priority=Priority.high,
            confidence=0.98,
        )

        opp3, created3, changed3 = create_or_update_opportunity(db, email3, analysis3)
        db.commit()

        assert created3 is False
        assert changed3 is True
        assert opp3.id == opp1.id  # Same opportunity!
        assert opp3.status == "next_round"
        assert opp3.round_name == "Round 2"

        # ── Final Database Verification ───────────────────────
        all_opps = db.query(Opportunity).all()
        assert len(all_opps) == 1
        final_opp = all_opps[0]
        assert final_opp.title == "XYZ Hackathon"
        assert final_opp.status == "next_round"

        # Check source emails attached
        attached_links = (
            db.query(OpportunityEmail)
            .filter(OpportunityEmail.opportunity_id == final_opp.id)
            .all()
        )
        assert len(attached_links) == 3

        # Check status history
        history = (
            db.query(OpportunityStatusHistory)
            .filter(OpportunityStatusHistory.opportunity_id == final_opp.id)
            .order_by(OpportunityStatusHistory.changed_at.asc())
            .all()
        )
        assert len(history) == 3
        assert history[0].old_status is None
        assert history[0].new_status == "registered"

        assert history[1].old_status == "registered"
        assert history[1].new_status == "shortlisted"

        assert history[2].old_status == "shortlisted"
        assert history[2].new_status == "next_round"

    def test_duplicate_email_processing_idempotency(self, db):
        user, acc1, _ = self._setup_environment(db)

        email = EmailMessage(
            account_id=acc1.id,
            gmail_message_id="msg_dup_1",
            gmail_thread_id="th_dup_1",
            sender="internships@stripe.com",
            subject="Stripe Internship Offer",
            received_at=datetime.now(timezone.utc),
            processing_status="pending",
        )
        db.add(email)
        db.commit()

        analysis = EmailAnalysis(
            category=Category.internship,
            title="Software Engineering Intern",
            organization="Stripe",
            status=Status.selected,
            priority=Priority.critical,
        )

        # First run
        opp1, created1, _ = create_or_update_opportunity(db, email, analysis)
        db.commit()
        assert created1 is True

        # Second run with exact same email
        opp2, created2, changed2 = create_or_update_opportunity(db, email, analysis)
        db.commit()
        assert created2 is False
        assert changed2 is False
        assert opp2.id == opp1.id

        # Verification: Only 1 opportunity, 1 email link, 1 history entry
        assert db.query(Opportunity).count() == 1
        assert db.query(OpportunityEmail).count() == 1
        assert db.query(OpportunityStatusHistory).count() == 1

    def test_same_opportunity_across_two_gmail_accounts(self, db):
        user, acc1, acc2 = self._setup_environment(db)

        # Email arrives in College account (acc1)
        email_acc1 = EmailMessage(
            account_id=acc1.id,
            gmail_message_id="msg_acc1_sih",
            gmail_thread_id="th_sih_1",
            sender="notifications@sih.gov.in",
            subject="Smart India Hackathon 2026 Confirmation",
            received_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            processing_status="pending",
        )
        # Follow-up arrives in Personal account (acc2)
        email_acc2 = EmailMessage(
            account_id=acc2.id,
            gmail_message_id="msg_acc2_sih",
            gmail_thread_id="th_sih_2",
            sender="coordinator@sih.gov.in",
            subject="Smart India Hackathon 2026 - Shortlisted for Grand Finale",
            received_at=datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc),
            processing_status="pending",
        )
        db.add_all([email_acc1, email_acc2])
        db.commit()

        analysis1 = EmailAnalysis(
            category=Category.hackathon,
            title="Smart India Hackathon 2026",
            organization="AICTE",
            status=Status.registered,
        )
        analysis2 = EmailAnalysis(
            category=Category.hackathon,
            title="Smart India Hackathon 2026",
            organization="AICTE",
            status=Status.shortlisted,
        )

        opp1, created1, _ = create_or_update_opportunity(db, email_acc1, analysis1)
        db.commit()

        opp2, created2, _ = create_or_update_opportunity(db, email_acc2, analysis2)
        db.commit()

        assert created1 is True
        assert created2 is False
        assert opp1.id == opp2.id
        assert opp2.status == "shortlisted"

        # Linked to both emails across both accounts
        links = db.query(OpportunityEmail).filter(OpportunityEmail.opportunity_id == opp1.id).all()
        assert len(links) == 2
        email_ids = {link.email_id for link in links}
        assert email_ids == {email_acc1.id, email_acc2.id}

    def test_missing_optional_fields_gracefully_handled(self, db):
        user, acc1, _ = self._setup_environment(db)

        email = EmailMessage(
            account_id=acc1.id,
            gmail_message_id="msg_minimal",
            gmail_thread_id="th_min",
            sender="dean@college.edu",
            subject="College Notice",
            received_at=datetime.now(timezone.utc),
            processing_status="pending",
        )
        db.add(email)
        db.commit()

        analysis = EmailAnalysis(
            category=Category.college,
            title=None,
            organization=None,
            deadline=None,
            apply_url=None,
            event_url=None,
            location=None,
            eligibility=None,
            description=None,
        )

        opp, created, _ = create_or_update_opportunity(db, email, analysis)
        db.commit()

        assert created is True
        assert opp.organization is None
        assert opp.deadline is None
        assert opp.title == "College Notice"  # Fallback to subject


class TestDeadlineIntelligence:
    def test_deadline_parsing_formats(self):
        # ISO format
        dt1 = parse_deadline_datetime("2026-10-15T23:59:59Z")
        assert dt1 is not None
        assert dt1.year == 2026 and dt1.month == 10 and dt1.day == 15

        # YYYY-MM-DD
        dt2 = parse_deadline_datetime("2026-11-20")
        assert dt2 is not None
        assert dt2.year == 2026 and dt2.month == 11 and dt2.day == 20

        # Text format: 15 Oct 2026
        dt3 = parse_deadline_datetime("15 Oct 2026")
        assert dt3 is not None
        assert dt3.year == 2026 and dt3.month == 10 and dt3.day == 15

        # Invalid text
        assert parse_deadline_datetime("ASAP") is None
        assert parse_deadline_datetime("") is None
        assert parse_deadline_datetime(None) is None

    def test_deadline_state_today(self):
        now = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)
        deadline = datetime(2026, 9, 8, 23, 59, 59, tzinfo=timezone.utc)

        state = compute_deadline_state(deadline, now=now)
        assert state["is_due_today"] is True
        assert state["is_overdue"] is False
        assert state["is_due_tomorrow"] is False
        assert state["hours_remaining"] > 0

    def test_deadline_state_tomorrow(self):
        now = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)
        deadline = datetime(2026, 9, 9, 18, 0, 0, tzinfo=timezone.utc)

        state = compute_deadline_state(deadline, now=now)
        assert state["is_due_tomorrow"] is True
        assert state["is_due_today"] is False
        assert state["is_overdue"] is False
        assert state["days_remaining"] == 1

    def test_deadline_state_overdue(self):
        now = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)
        deadline = datetime(2026, 9, 5, 23, 59, 59, tzinfo=timezone.utc)

        state = compute_deadline_state(deadline, now=now)
        assert state["is_overdue"] is True
        assert state["is_due_today"] is False
        assert state["hours_remaining"] < 0

    def test_deadline_state_none(self):
        state = compute_deadline_state(None)
        assert state["days_remaining"] is None
        assert state["hours_remaining"] is None
        assert state["is_overdue"] is False
        assert state["is_due_today"] is False
        assert state["is_due_tomorrow"] is False
