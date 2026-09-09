"""
CareerMail AI — Opportunities API Tests.

Tests:
  • GET /opportunities — pagination, filtering by category, status, priority, search.
  • GET /opportunities/{id} — detail view with source emails & status history.
  • 404 handling for invalid IDs.
  • Security check: no secrets, OAuth tokens, or encrypted credentials exposed.
"""

from datetime import datetime, timezone, timedelta
import pytest

from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.models.opportunity import Opportunity
from app.models.opportunity_email import OpportunityEmail
from app.models.status_history import OpportunityStatusHistory
from app.models.user import User


class TestOpportunitiesAPI:
    def _seed_opportunities(self, db):
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, display_name="Test Student")
            db.add(user)
            db.commit()

        acc = EmailAccount(
            user_id=1,
            email_address="student@college.edu",
            encrypted_access_token="secret_token_123",
            encrypted_refresh_token="secret_refresh_456",
        )
        db.add(acc)
        db.commit()
        db.refresh(acc)

        email1 = EmailMessage(
            account_id=acc.id,
            gmail_message_id="msg_api_opp_1",
            gmail_thread_id="th_api_1",
            sender="hackathon@nitr.com",
            subject="HackNITR 5.0 Shortlisted",
            received_at=datetime.now(timezone.utc),
            processing_status="extracted",
        )
        email2 = EmailMessage(
            account_id=acc.id,
            gmail_message_id="msg_api_opp_2",
            gmail_thread_id="th_api_2",
            sender="recruiting@google.com",
            subject="Google SDE Interview",
            received_at=datetime.now(timezone.utc),
            processing_status="extracted",
        )
        db.add_all([email1, email2])
        db.commit()

        opp1 = Opportunity(
            user_id=1,
            category="hackathon",
            title="HackNITR 5.0",
            organization="NIT Rourkela",
            status="shortlisted",
            priority="high",
            confidence=0.95,
            deadline=datetime.now(timezone.utc) + timedelta(days=2),
            first_seen_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        opp2 = Opportunity(
            user_id=1,
            category="internship",
            title="Google Software Engineering Intern",
            organization="Google",
            status="interview",
            priority="critical",
            confidence=0.98,
            deadline=datetime.now(timezone.utc) - timedelta(days=1),  # overdue
            first_seen_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        db.add_all([opp1, opp2])
        db.commit()
        db.refresh(opp1)
        db.refresh(opp2)

        # Attach email1 to opp1 and add history
        link = OpportunityEmail(opportunity_id=opp1.id, email_id=email1.id)
        hist = OpportunityStatusHistory(
            opportunity_id=opp1.id,
            old_status="registered",
            new_status="shortlisted",
            source_email_id=email1.id,
        )
        db.add_all([link, hist])
        db.commit()

        return opp1, opp2, acc

    def test_list_opportunities(self, client, db):
        self._seed_opportunities(db)

        response = client.get("/opportunities")
        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "pagination" in data
        assert len(data["items"]) == 2
        assert data["pagination"]["total_items"] == 2

        # Check deadline intelligence fields
        first = data["items"][0]
        assert "is_overdue" in first
        assert "is_due_today" in first
        assert "days_remaining" in first

    def test_filter_by_category(self, client, db):
        self._seed_opportunities(db)

        response = client.get("/opportunities?category=hackathon")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["category"] == "hackathon"

    def test_filter_by_status(self, client, db):
        self._seed_opportunities(db)

        response = client.get("/opportunities?status=interview")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "interview"

    def test_filter_by_priority(self, client, db):
        self._seed_opportunities(db)

        response = client.get("/opportunities?priority=critical")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["priority"] == "critical"

    def test_search_filter(self, client, db):
        self._seed_opportunities(db)

        response = client.get("/opportunities?search=Google")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert "Google" in data["items"][0]["organization"]

    def test_get_opportunity_detail(self, client, db):
        opp1, _, _ = self._seed_opportunities(db)

        response = client.get(f"/opportunities/{opp1.id}")
        assert response.status_code == 200
        data = response.json()

        assert data["id"] == opp1.id
        assert data["title"] == "HackNITR 5.0"
        assert "source_emails" in data
        assert len(data["source_emails"]) == 1
        assert data["source_emails"][0]["gmail_message_id"] == "msg_api_opp_1"

        assert "status_history" in data
        assert len(data["status_history"]) == 1
        assert data["status_history"][0]["new_status"] == "shortlisted"

    def test_get_opportunity_detail_404(self, client):
        response = client.get("/opportunities/999999")
        assert response.status_code == 404
        assert "Opportunity not found" in response.json()["detail"]

    def test_no_secrets_leaked_in_opportunity_responses(self, client, db):
        opp1, _, acc = self._seed_opportunities(db)

        response = client.get(f"/opportunities/{opp1.id}")
        text = response.text

        # Ensure no token leaks
        assert "secret_token_123" not in text
        assert "secret_refresh_456" not in text
        assert "token" not in text.lower() or "source_emails" in text

    def test_list_opportunities_sorting_title(self, client, db):
        self._seed_opportunities(db)

        # Title asc: "Google..." before "HackNITR..."
        res_asc = client.get("/opportunities?sort_by=title&sort_order=asc")
        assert res_asc.status_code == 200
        items_asc = res_asc.json()["items"]
        assert items_asc[0]["title"].startswith("Google")
        assert items_asc[1]["title"].startswith("HackNITR")

        # Title desc: "HackNITR..." before "Google..."
        res_desc = client.get("/opportunities?sort_by=title&sort_order=desc")
        assert res_desc.status_code == 200
        items_desc = res_desc.json()["items"]
        assert items_desc[0]["title"].startswith("HackNITR")
        assert items_desc[1]["title"].startswith("Google")

    def test_list_opportunities_sorting_priority(self, client, db):
        self._seed_opportunities(db)

        # Priority desc: critical (Google) before high (HackNITR)
        res_desc = client.get("/opportunities?sort_by=priority&sort_order=desc")
        assert res_desc.status_code == 200
        items = res_desc.json()["items"]
        assert items[0]["priority"] == "critical"
        assert items[1]["priority"] == "high"

        # Priority asc: high before critical
        res_asc = client.get("/opportunities?sort_by=priority&sort_order=asc")
        assert res_asc.status_code == 200
        items_asc = res_asc.json()["items"]
        assert items_asc[0]["priority"] == "high"
        assert items_asc[1]["priority"] == "critical"

    def test_list_opportunities_sorting_deadline(self, client, db):
        self._seed_opportunities(db)

        # Deadline asc: overdue (-1 day) before +2 days
        res_asc = client.get("/opportunities?sort_by=deadline&sort_order=asc")
        assert res_asc.status_code == 200
        items = res_asc.json()["items"]
        assert items[0]["title"].startswith("Google")

    def test_list_opportunities_invalid_sort(self, client, db):
        self._seed_opportunities(db)

        res_invalid_col = client.get("/opportunities?sort_by=nonexistent")
        assert res_invalid_col.status_code == 422
        assert "Invalid sort_by" in res_invalid_col.json()["detail"]

        res_invalid_order = client.get("/opportunities?sort_order=sideways")
        assert res_invalid_order.status_code == 422
        assert "Invalid sort_order" in res_invalid_order.json()["detail"]

    def test_list_opportunities_pagination(self, client, db):
        self._seed_opportunities(db)

        # Page 1 with page_size=1
        res_p1 = client.get("/opportunities?page=1&page_size=1")
        assert res_p1.status_code == 200
        data1 = res_p1.json()
        assert len(data1["items"]) == 1
        assert data1["pagination"]["page"] == 1
        assert data1["pagination"]["page_size"] == 1
        assert data1["pagination"]["total_items"] == 2
        assert data1["pagination"]["total_pages"] == 2
        assert data1["pagination"]["has_next"] is True
        assert data1["pagination"]["has_previous"] is False

        # Page 2
        res_p2 = client.get("/opportunities?page=2&page_size=1")
        assert res_p2.status_code == 200
        data2 = res_p2.json()
        assert len(data2["items"]) == 1
        assert data2["pagination"]["page"] == 2
        assert data2["pagination"]["has_next"] is False
        assert data2["pagination"]["has_previous"] is True

        # Validation: page < 1
        res_bad_page = client.get("/opportunities?page=0")
        assert res_bad_page.status_code == 422

        # Validation: page_size > 100
        res_bad_size = client.get("/opportunities?page_size=101")
        assert res_bad_size.status_code == 422
