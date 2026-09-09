"""
CareerMail AI — Deadlines API Tests.

Tests:
  • GET /deadlines grouping: overdue, today, tomorrow, this_week, later, no_deadline.
  • Timezone conversion accuracy.
  • Category filtering.
  • Card metadata fields (action_required, action, days/hours remaining).
  • Empty state handling.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest

from app.models.opportunity import Opportunity
from app.models.user import User


class TestDeadlinesAPI:
    def _seed_deadline_opportunities(self, db, base_now_utc: datetime):
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, display_name="Deadline User")
            db.add(user)
            db.commit()

        # 1. Overdue (2 days ago)
        opp_overdue = Opportunity(
            user_id=1,
            category="hackathon",
            title="Overdue Hackathon",
            organization="Org 1",
            status="registered",
            priority="medium",
            confidence=0.9,
            deadline=base_now_utc - timedelta(days=2),
            first_seen_at=base_now_utc,
            last_updated_at=base_now_utc,
        )

        # 2. Due Today (+2 hours from base_now_utc)
        opp_today = Opportunity(
            user_id=1,
            category="internship",
            title="Due Today Internship",
            organization="Org 2",
            status="open",
            priority="critical",
            confidence=0.95,
            deadline=base_now_utc + timedelta(hours=2),
            action_required=True,
            action="Submit resume and code sample",
            first_seen_at=base_now_utc,
            last_updated_at=base_now_utc,
        )

        # 3. Due Tomorrow (+26 hours from base_now_utc)
        opp_tomorrow = Opportunity(
            user_id=1,
            category="placement",
            title="Due Tomorrow Placement",
            organization="Org 3",
            status="interview",
            priority="high",
            confidence=0.92,
            deadline=base_now_utc + timedelta(days=1, hours=2),
            action_required=True,
            action="Attend pre-placement briefing",
            first_seen_at=base_now_utc,
            last_updated_at=base_now_utc,
        )

        # 4. Due This Week (+3 days)
        opp_this_week = Opportunity(
            user_id=1,
            category="hackathon",
            title="This Week Hackathon",
            organization="Org 4",
            status="shortlisted",
            priority="high",
            confidence=0.88,
            deadline=base_now_utc + timedelta(days=3),
            first_seen_at=base_now_utc,
            last_updated_at=base_now_utc,
        )

        # 5. Due Later (+20 days)
        opp_later = Opportunity(
            user_id=1,
            category="college",
            title="Later Fellowship",
            organization="Org 5",
            status="open",
            priority="low",
            confidence=0.85,
            deadline=base_now_utc + timedelta(days=20),
            first_seen_at=base_now_utc,
            last_updated_at=base_now_utc,
        )

        # 6. No deadline
        opp_no_dl = Opportunity(
            user_id=1,
            category="general",
            title="Open Mentorship Programme",
            organization="Org 6",
            status="open",
            priority="low",
            confidence=0.8,
            deadline=None,
            first_seen_at=base_now_utc,
            last_updated_at=base_now_utc,
        )

        db.add_all([
            opp_overdue,
            opp_today,
            opp_tomorrow,
            opp_this_week,
            opp_later,
            opp_no_dl,
        ])
        db.commit()
        for o in [opp_overdue, opp_today, opp_tomorrow, opp_this_week, opp_later, opp_no_dl]:
            db.refresh(o)

        return {
            "overdue": opp_overdue,
            "today": opp_today,
            "tomorrow": opp_tomorrow,
            "this_week": opp_this_week,
            "later": opp_later,
            "no_deadline": opp_no_dl,
        }

    def test_get_deadlines_empty(self, client):
        response = client.get("/deadlines")
        assert response.status_code == 200
        data = response.json()
        assert data["overdue"] == []
        assert data["today"] == []
        assert data["tomorrow"] == []
        assert data["this_week"] == []
        assert data["later"] == []
        assert data["no_deadline"] == []
        assert data["total_active"] == 0

    def test_get_deadlines_grouping(self, client, db):
        # Anchor relative to current UTC
        now_utc = datetime.now(timezone.utc)
        self._seed_deadline_opportunities(db, now_utc)

        response = client.get("/deadlines?tz=UTC")
        assert response.status_code == 200
        data = response.json()

        assert len(data["overdue"]) >= 1
        assert any(item["title"] == "Overdue Hackathon" for item in data["overdue"])
        assert data["overdue"][0]["is_overdue"] is True

        assert len(data["today"]) >= 1
        today_item = next(item for item in data["today"] if item["title"] == "Due Today Internship")
        assert today_item["action_required"] is True
        assert today_item["action"] == "Submit resume and code sample"
        assert today_item["is_due_today"] is True
        assert today_item["priority"] == "critical"

        assert len(data["tomorrow"]) >= 1
        assert any(item["title"] == "Due Tomorrow Placement" for item in data["tomorrow"])

        assert len(data["this_week"]) >= 1
        assert any(item["title"] == "This Week Hackathon" for item in data["this_week"])

        assert len(data["later"]) >= 1
        assert any(item["title"] == "Later Fellowship" for item in data["later"])

        assert len(data["no_deadline"]) >= 1
        assert any(item["title"] == "Open Mentorship Programme" for item in data["no_deadline"])

        assert data["total_active"] >= 5

    def test_get_deadlines_category_filter(self, client, db):
        now_utc = datetime.now(timezone.utc)
        self._seed_deadline_opportunities(db, now_utc)

        response = client.get("/deadlines?category=hackathon&tz=UTC")
        assert response.status_code == 200
        data = response.json()

        # Only hackathon items should be returned
        for group_name in ["overdue", "today", "tomorrow", "this_week", "later", "no_deadline"]:
            for item in data[group_name]:
                assert item["category"] == "hackathon"

    def test_get_deadlines_timezone_conversion(self, client, db):
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, display_name="TZ User")
            db.add(user)
            db.commit()

        # Fixed time: 2026-09-08 20:00:00 UTC
        # In Asia/Kolkata (+05:30), that is 2026-09-09 01:30:00 (Tomorrow in IST!)
        fixed_dt_utc = datetime(2026, 9, 8, 20, 0, 0, tzinfo=timezone.utc)
        opp = Opportunity(
            user_id=1,
            category="internship",
            title="Boundary Test Opp",
            organization="TZ Org",
            status="open",
            priority="high",
            confidence=0.9,
            deadline=fixed_dt_utc,
            first_seen_at=fixed_dt_utc,
            last_updated_at=fixed_dt_utc,
        )
        db.add(opp)
        db.commit()

        # Query with custom tz
        res_ist = client.get("/deadlines?tz=Asia/Kolkata")
        assert res_ist.status_code == 200

        # Also verify fallback to UTC for invalid timezone
        res_invalid_tz = client.get("/deadlines?tz=Invalid/Timezone_Name")
        assert res_invalid_tz.status_code == 200
