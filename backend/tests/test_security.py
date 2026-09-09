"""
CareerMail AI — Security & Data Protection Tests.

Verifies:
  • No API endpoint exposes OAuth tokens, refresh tokens, encryption keys, or Gemini keys.
  • Schemas and serializers contain no sensitive internal fields.
  • GET /opportunities, /deadlines, /digest, /emails, /accounts never leak credentials in responses.
"""

import json
from datetime import datetime, timezone, timedelta
import pytest

from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.models.opportunity import Opportunity
from app.models.opportunity_email import OpportunityEmail
from app.models.status_history import OpportunityStatusHistory
from app.models.user import User


class TestSecurityAndDataProtection:
    @pytest.fixture(autouse=True)
    def setup_database_with_sensitive_data(self, db):
        """Populate database with known canary secrets to test for accidental leakage."""
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, display_name="Security Tester")
            db.add(user)
            db.commit()

        CANARY_ACCESS_TOKEN = "SUPER_SECRET_ACCESS_TOKEN_XYZ_12345"
        CANARY_REFRESH_TOKEN = "SUPER_SECRET_REFRESH_TOKEN_ABC_67890"

        acc = EmailAccount(
            user_id=1,
            email_address="security@college.edu",
            encrypted_access_token=CANARY_ACCESS_TOKEN,
            encrypted_refresh_token=CANARY_REFRESH_TOKEN,
        )
        db.add(acc)
        db.commit()
        db.refresh(acc)

        email = EmailMessage(
            account_id=acc.id,
            gmail_message_id="sec_msg_1",
            gmail_thread_id="sec_th_1",
            sender="recruiter@tech.com",
            recipients='["student@college.edu"]',
            subject="Interview Invitation",
            body_text="Congratulations! Your interview is confirmed.",
            received_at=datetime.now(timezone.utc),
            processing_status="extracted",
        )
        db.add(email)
        db.commit()
        db.refresh(email)

        opp = Opportunity(
            user_id=1,
            category="internship",
            title="Security Engineer Intern",
            organization="CyberCorp",
            status="interview",
            priority="critical",
            confidence=0.99,
            deadline=datetime.now(timezone.utc) + timedelta(days=1),
            action_required=True,
            action="Confirm interview slot",
            first_seen_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        db.add(opp)
        db.commit()
        db.refresh(opp)

        link = OpportunityEmail(opportunity_id=opp.id, email_id=email.id)
        hist = OpportunityStatusHistory(
            opportunity_id=opp.id,
            old_status="applied",
            new_status="interview",
            source_email_id=email.id,
        )
        db.add_all([link, hist])
        db.commit()

        self.canary_tokens = [CANARY_ACCESS_TOKEN, CANARY_REFRESH_TOKEN]
        self.opp_id = opp.id
        self.email_id = email.id
        self.account_id = acc.id

    def test_opportunities_endpoints_leak_no_secrets(self, client):
        endpoints = [
            "/opportunities",
            f"/opportunities/{self.opp_id}",
        ]
        for ep in endpoints:
            res = client.get(ep)
            assert res.status_code == 200
            content = res.text
            for canary in self.canary_tokens:
                assert canary not in content, f"Canary token leaked in {ep}!"

    def test_deadlines_endpoints_leak_no_secrets(self, client):
        res = client.get("/deadlines")
        assert res.status_code == 200
        content = res.text
        for canary in self.canary_tokens:
            assert canary not in content, "Canary token leaked in /deadlines!"

    def test_digest_endpoints_leak_no_secrets(self, client):
        res = client.get("/digest/today")
        assert res.status_code == 200
        content = res.text
        for canary in self.canary_tokens:
            assert canary not in content, "Canary token leaked in /digest/today!"

    def test_emails_endpoints_leak_no_secrets(self, client):
        endpoints = [
            "/emails",
            f"/emails/{self.email_id}",
        ]
        for ep in endpoints:
            res = client.get(ep)
            assert res.status_code == 200
            content = res.text
            for canary in self.canary_tokens:
                assert canary not in content, f"Canary token leaked in {ep}!"

    def test_accounts_endpoints_leak_no_tokens(self, client):
        res = client.get("/accounts")
        assert res.status_code == 200
        content = res.text
        for canary in self.canary_tokens:
            assert canary not in content, "Canary token leaked in /accounts!"
        assert "encrypted_access_token" not in content
        assert "encrypted_refresh_token" not in content

    def test_devices_and_notifications_leak_no_secrets(self, client, db):
        # Register a device with a unique canary token
        full_canary_token = "fcm_canary_token_very_long_secret_1234567890"
        reg_resp = client.post(
            "/devices/register",
            json={
                "fcm_token": full_canary_token,
                "device_type": "android",
                "device_name": "Secure Phone",
            },
        )
        assert reg_resp.status_code == 200

        # Listing devices should NOT leak the full raw token
        dev_res = client.get("/devices")
        assert dev_res.status_code == 200
        assert full_canary_token not in dev_res.text
        for canary in self.canary_tokens:
            assert canary not in dev_res.text

        # Notifications test and history
        test_resp = client.post("/notifications/test", json={})
        assert test_resp.status_code == 200
        assert full_canary_token not in test_resp.text

        hist_res = client.get("/notifications/history")
        assert hist_res.status_code == 200
        assert full_canary_token not in hist_res.text
        for canary in self.canary_tokens:
            assert canary not in hist_res.text

    def test_response_models_do_not_contain_secret_fields(self):
        """Introspect all Pydantic response models to ensure no secret fields exist."""
        from app.schemas.opportunity import OpportunityResponse, OpportunityDetailResponse, SourceEmailReference
        from app.schemas.deadline import DeadlineCardItem, DeadlinesGroupedResponse
        from app.schemas.digest import DailyDigestResponse
        from app.schemas.email import EmailResponse, EmailDetailResponse
        from app.schemas.account import AccountResponse

        forbidden_substrings = ["token", "secret", "password", "private_key", "encryption_key"]

        models_to_check = [
            OpportunityResponse,
            OpportunityDetailResponse,
            SourceEmailReference,
            DeadlineCardItem,
            DeadlinesGroupedResponse,
            DailyDigestResponse,
            EmailResponse,
            EmailDetailResponse,
            AccountResponse,
        ]

        for model in models_to_check:
            for field_name in model.model_fields.keys():
                for forbidden in forbidden_substrings:
                    assert forbidden not in field_name.lower(), (
                        f"Potentially sensitive field '{field_name}' in response model {model.__name__}"
                    )

