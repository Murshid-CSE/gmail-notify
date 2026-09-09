"""
CareerMail AI — Extraction API Tests.

Tests:
  • POST /extraction/process (validation, batch triggering)
  • GET /extraction/status (status breakdown counts)
"""

from datetime import datetime, timezone
from unittest.mock import patch
from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.models.user import User


class TestExtractionAPI:
    def _setup_account_and_emails(self, db):
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, display_name="Test User")
            db.add(user)
            db.commit()

        account = EmailAccount(
            user_id=1,
            email_address="student@college.edu",
            encrypted_access_token="enc_acc",
            encrypted_refresh_token="enc_ref",
        )
        db.add(account)
        db.commit()
        db.refresh(account)

        emails = [
            EmailMessage(
                account_id=account.id,
                gmail_message_id="ext_api_1",
                gmail_thread_id="th_api_1",
                sender="tpo@college.edu",
                subject="Placement Notice",
                received_at=datetime.now(timezone.utc),
                processing_status="pending",
            ),
            EmailMessage(
                account_id=account.id,
                gmail_message_id="ext_api_2",
                gmail_thread_id="th_api_2",
                sender="newsletter@deals.com",
                subject="Deals of the day",
                received_at=datetime.now(timezone.utc),
                processing_status="filtered_out",
            ),
            EmailMessage(
                account_id=account.id,
                gmail_message_id="ext_api_3",
                gmail_thread_id="th_api_3",
                sender="hackathon@mlh.io",
                subject="MLH Hackathon",
                received_at=datetime.now(timezone.utc),
                processing_status="extracted",
            ),
        ]
        db.add_all(emails)
        db.commit()
        return account

    def test_get_extraction_status(self, client, db):
        self._setup_account_and_emails(db)

        response = client.get("/extraction/status")
        assert response.status_code == 200
        data = response.json()

        assert "gemini_configured" in data
        assert "email_counts" in data
        assert data["email_counts"]["pending"] == 1
        assert data["email_counts"]["filtered_out"] == 1
        assert data["email_counts"]["extracted"] == 1
        assert data["total_emails"] == 3

    def test_trigger_extraction_validation(self, client):
        # Limit < 1
        resp_low = client.post("/extraction/process?limit=0")
        assert resp_low.status_code == 422

        # Limit > 200
        resp_high = client.post("/extraction/process?limit=250")
        assert resp_high.status_code == 422

    def test_trigger_extraction_process_success(self, client, db):
        self._setup_account_and_emails(db)

        with patch("app.api.extraction.process_pending_emails") as mock_proc:
            mock_proc.return_value = {
                "total": 1,
                "filtered_out": 0,
                "extracted": 1,
                "pending_extraction": 0,
                "extraction_failed": 0,
            }
            response = client.post("/extraction/process?limit=10")

            assert response.status_code == 200
            data = response.json()
            assert "Processed 1 emails" in data["message"]
            assert data["extracted"] == 1
            assert "gemini_configured" in data
