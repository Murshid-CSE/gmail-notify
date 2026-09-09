"""
CareerMail AI — Tests for AI Email Composer (Milestone 9).

Covers:
  • MIME construction (To, From, Subject, Cc, Bcc, threading headers)
  • Base64url encoding / decoding fidelity
  • Gmail composer service (draft creation, sending, 403 scope error mapping)
  • AI Orchestrator draft generation & provider fallback
  • Anti-hallucination recipient enforcement
  • Confirmation requirement before sending
  • Opportunity activity timeline recording
  • Re-authorization handling (HTTP 403 with error_code='reauth_required')
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from email import message_from_bytes, policy
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from httpx import Response as HttpxResponse

from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.models.opportunity import Opportunity
from app.models.status_history import OpportunityStatusHistory
from app.models.user import User
from app.schemas.composer import EmailDraft
from app.services.ai.base import (
    AIRateLimitError,
    AISchemaError,
    BaseAIProvider,
)
from app.services.ai.orchestrator import AIOrchestrator
from app.services.gmail.auth import OAuthScopeError
from app.services.gmail.composer import (
    create_mime_message,
    create_gmail_draft,
    send_gmail_message,
)


# ── MIME Construction Tests ───────────────────────────────────


class TestMimeConstruction:
    def test_mime_basic_headers(self):
        encoded = create_mime_message(
            sender="student@gmail.com",
            to=["organizer@hackathon.org"],
            subject="Question regarding rules",
            body_text="Dear Organizer,\n\nI have a question.",
        )
        assert isinstance(encoded, str)
        raw_bytes = base64.urlsafe_b64decode(encoded.encode("utf-8"))
        msg = message_from_bytes(raw_bytes, policy=policy.default)

        assert msg["From"] == "student@gmail.com"
        assert msg["To"] == "organizer@hackathon.org"
        assert msg["Subject"] == "Question regarding rules"
        assert "I have a question." in msg.get_content()

    def test_mime_with_cc_bcc(self):
        encoded = create_mime_message(
            sender="student@gmail.com",
            to=["recruiter@tech.com"],
            subject="Interview Availability",
            body_text="Attached is my availability.",
            cc=["mentor@college.edu"],
            bcc=["archive@gmail.com"],
        )
        raw_bytes = base64.urlsafe_b64decode(encoded.encode("utf-8"))
        msg = message_from_bytes(raw_bytes, policy=policy.default)

        assert msg["Cc"] == "mentor@college.edu"
        assert msg["Bcc"] == "archive@gmail.com"

    def test_mime_threading_headers(self):
        encoded = create_mime_message(
            sender="student@gmail.com",
            to=["recruiter@tech.com"],
            subject="Re: Next Steps",
            body_text="Thank you for the update.",
            in_reply_to="<orig_msg_123@mail.gmail.com>",
            references="<root_msg_001@mail.gmail.com>",
        )
        raw_bytes = base64.urlsafe_b64decode(encoded.encode("utf-8"))
        msg = message_from_bytes(raw_bytes, policy=policy.default)

        assert msg["In-Reply-To"] == "<orig_msg_123@mail.gmail.com>"
        assert msg["References"] == "<root_msg_001@mail.gmail.com>"



# ── Gmail API Composer Service Tests ──────────────────────────


class TestGmailComposerService:
    def test_create_gmail_draft_success(self):
        mock_creds = MagicMock()
        mock_service = MagicMock()
        mock_service.users().drafts().create().execute.return_value = {
            "id": "draft_abc123",
            "message": {"id": "msg_xyz789"},
        }

        with patch("app.services.gmail.composer.build_gmail_service", return_value=mock_service):
            result = create_gmail_draft(
                credentials=mock_creds,
                sender_email="user@gmail.com",
                to=["contact@company.com"],
                subject="Test Draft",
                body_text="Draft body text",
                account_id=1,
            )

        assert result["draft_id"] == "draft_abc123"
        assert result["message_id"] == "msg_xyz789"
        assert result["account_id"] == 1
        assert result["subject"] == "Test Draft"

    def test_send_gmail_message_success(self):
        mock_creds = MagicMock()
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.return_value = {
            "id": "msg_sent_999",
            "threadId": "th_sent_999",
        }

        with patch("app.services.gmail.composer.build_gmail_service", return_value=mock_service):
            result = send_gmail_message(
                credentials=mock_creds,
                sender_email="user@gmail.com",
                to=["contact@company.com"],
                subject="Test Send",
                body_text="Send body text",
                account_id=1,
            )

        assert result["message_id"] == "msg_sent_999"
        assert result["thread_id"] == "th_sent_999"
        assert result["account_id"] == 1
        assert result["to"] == ["contact@company.com"]

    def test_create_draft_insufficient_permissions_raises_oauthscopeerror(self):
        mock_creds = MagicMock()
        mock_service = MagicMock()

        # Simulate Google 403 insufficientPermissions error
        mock_resp = MagicMock()
        mock_resp.status = 403
        http_err = HttpError(resp=mock_resp, content=b'{"error": {"message": "Insufficient Permission: ACCESS_TOKEN_SCOPE_INSUFFICIENT"}}')
        mock_service.users().drafts().create().execute.side_effect = http_err

        with patch("app.services.gmail.composer.build_gmail_service", return_value=mock_service):
            with pytest.raises(OAuthScopeError) as exc_info:
                create_gmail_draft(
                    credentials=mock_creds,
                    sender_email="user@gmail.com",
                    to=["contact@company.com"],
                    subject="Draft Fail",
                    body_text="Body",
                    account_id=2,
                )

        assert exc_info.value.account_id == 2
        assert "re-authorization" in str(exc_info.value).lower()

    def test_send_message_insufficient_permissions_raises_oauthscopeerror(self):
        mock_creds = MagicMock()
        mock_service = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status = 403
        http_err = HttpError(resp=mock_resp, content=b'{"error": {"message": "insufficientPermissions"}}')
        mock_service.users().messages().send().execute.side_effect = http_err

        with patch("app.services.gmail.composer.build_gmail_service", return_value=mock_service):
            with pytest.raises(OAuthScopeError) as exc_info:
                send_gmail_message(
                    credentials=mock_creds,
                    sender_email="user@gmail.com",
                    to=["contact@company.com"],
                    subject="Send Fail",
                    body_text="Body",
                    account_id=3,
                )

        assert exc_info.value.account_id == 3


# ── AI Orchestrator Draft Tests ───────────────────────────────


class MockDraftProvider(BaseAIProvider):
    def __init__(self, name: str, draft: EmailDraft = None, side_effect: Exception = None):
        self._name = name
        self._draft = draft
        self._side_effect = side_effect

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return f"{self._name}-model"

    def is_configured(self) -> bool:
        return True

    def extract_email_data(self, sender, subject, received_at, body_text):
        raise NotImplementedError()

    def generate_email_draft(self, opportunity_context, instruction):
        if self._side_effect:
            raise self._side_effect
        return self._draft


class TestAIOrchestratorDraft:
    def test_orchestrator_generate_email_draft_success(self):
        valid_draft = EmailDraft(
            to=["recruiter@tech.com"],
            subject="Request for Extension",
            body_text="Dear Recruiter,\n\nMay I request an extension?",
        )
        provider = MockDraftProvider("mock_gemini", draft=valid_draft)
        orchestrator = AIOrchestrator(providers=[provider])

        result = orchestrator.generate_email_draft({"title": "Tech Internship"}, "Ask for extension")
        assert result.subject == "Request for Extension"
        assert result.to == ["recruiter@tech.com"]

    def test_orchestrator_generate_email_draft_fallback_on_rate_limit(self):
        valid_draft = EmailDraft(
            to=["recruiter@tech.com"],
            subject="Fallback Draft",
            body_text="Draft generated via fallback provider.",
        )
        p1 = MockDraftProvider("p1", side_effect=AIRateLimitError("Rate limit hit", provider="p1", status_code=429))
        p2 = MockDraftProvider("p2", draft=valid_draft)
        orchestrator = AIOrchestrator(providers=[p1, p2])

        result = orchestrator.generate_email_draft({"title": "Opportunity"}, "Draft email")
        assert result.subject == "Fallback Draft"
        assert orchestrator.get_metrics()["fallbacks_count"] == 1


# ── API Endpoint Integration Tests ────────────────────────────


class TestEmailComposerAPI:
    def _setup_entities(self, db):
        user = User(display_name="Test Student")
        db.add(user)
        db.commit()
        db.refresh(user)


        account = EmailAccount(
            user_id=user.id,
            email_address="student@gmail.com",
            encrypted_access_token="enc_tok",
            encrypted_refresh_token="enc_ref",
        )
        db.add(account)
        db.commit()
        db.refresh(account)


        now = datetime.now(timezone.utc)
        email = EmailMessage(
            account_id=account.id,
            gmail_message_id="msg_src_123",
            gmail_thread_id="th_src_123",
            sender="Hackathon Team <support@hackathon.org>",
            subject="Hackathon Submission Portal Open",
            received_at=now,
            body_text="The portal is open. Deadline is tomorrow at midnight.",
            processing_status="extracted",
        )
        db.add(email)
        db.commit()
        db.refresh(email)

        opp = Opportunity(
            user_id=user.id,
            source_account_id=account.id,
            category="hackathon",
            title="Global AI Hackathon",
            organization="HackGlobal",
            status="registered",
            deadline=now,
            action_required=True,
            action="Submit project repository",
            first_seen_at=now,
            last_updated_at=now,
        )
        db.add(opp)
        db.commit()
        db.refresh(opp)

        from app.models.opportunity_email import OpportunityEmail
        db.add(OpportunityEmail(opportunity_id=opp.id, email_id=email.id))
        db.commit()

        return user, account, opp, email

    def test_draft_generation_api_success(self, client, db):
        user, account, opp, email = self._setup_entities(db)

        mock_draft = EmailDraft(
            to=["support@hackathon.org"],
            subject="Request for 2-Day Extension – Global AI Hackathon",
            body_text="Dear Hackathon Team,\n\nMay I request a two-day extension?",
        )

        with patch("app.api.email_composer.get_ai_orchestrator") as mock_orch:
            mock_orch.return_value.generate_email_draft.return_value = mock_draft

            response = client.post(
                "/email-composer/draft",
                json={
                    "opportunity_id": opp.id,
                    "instruction": "Ask for a 2-day extension because my project is almost ready.",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["subject"] == "Request for 2-Day Extension – Global AI Hackathon"
        assert data["to"] == ["support@hackathon.org"]
        assert data["in_reply_to"] == "msg_src_123"
        assert data["thread_id"] == "th_src_123"
        assert data["suggested_account_id"] == account.id

    def test_draft_generation_anti_hallucination_recipient(self, client, db):
        """Verify AI cannot invent an arbitrary recipient address."""
        user, account, opp, email = self._setup_entities(db)

        # AI maliciously returns a hallucinated recipient
        fake_draft = EmailDraft(
            to=["invented_fake@nowhere.com"],
            subject="Inquiry",
            body_text="Text",
        )

        with patch("app.api.email_composer.get_ai_orchestrator") as mock_orch:
            mock_orch.return_value.generate_email_draft.return_value = fake_draft

            response = client.post(
                "/email-composer/draft",
                json={
                    "opportunity_id": opp.id,
                    "instruction": "Ask about submission",
                },
            )

        assert response.status_code == 200
        data = response.json()
        # Enforced: replaced with trusted source recipient support@hackathon.org
        assert data["to"] == ["support@hackathon.org"]
        assert "invented_fake@nowhere.com" not in data["to"]

    def test_draft_generation_missing_recipient_returns_empty(self, client, db):
        """When no email sender exists, draft.to MUST be empty."""
        user = User(display_name="Student")
        db.add(user)
        db.commit()


        opp = Opportunity(
            user_id=user.id,
            category="internship",
            title="Campus Job",
            status="opportunity",
            first_seen_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        db.add(opp)
        db.commit()

        ai_draft = EmailDraft(
            to=["someone@unverified.com"],
            subject="Inquiry",
            body_text="Hello",
        )

        with patch("app.api.email_composer.get_ai_orchestrator") as mock_orch:
            mock_orch.return_value.generate_email_draft.return_value = ai_draft

            response = client.post(
                "/email-composer/draft",
                json={
                    "opportunity_id": opp.id,
                    "instruction": "Ask about requirements",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["to"] == []  # Flutter will prompt the user

    def test_save_gmail_draft_api_success(self, client, db):
        user, account, opp, email = self._setup_entities(db)

        with patch("app.api.email_composer.build_credentials_from_encrypted"), \
             patch("app.api.email_composer.create_gmail_draft", return_value={"draft_id": "d_100", "message_id": "m_100", "account_id": account.id}):

            response = client.post(
                "/email-composer/gmail-draft",
                json={
                    "account_id": account.id,
                    "opportunity_id": opp.id,
                    "draft": {
                        "to": ["support@hackathon.org"],
                        "subject": "Extension Request",
                        "body_text": "Please grant extension.",
                    },
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["draft_id"] == "d_100"
        assert data["message_id"] == "m_100"
        assert data["account_id"] == account.id

    def test_save_gmail_draft_reauth_required(self, client, db):
        user, account, opp, email = self._setup_entities(db)

        with patch("app.api.email_composer.build_credentials_from_encrypted"), \
             patch("app.api.email_composer.create_gmail_draft", side_effect=OAuthScopeError("Scope error", account_id=account.id)):

            response = client.post(
                "/email-composer/gmail-draft",
                json={
                    "account_id": account.id,
                    "opportunity_id": opp.id,
                    "draft": {
                        "to": ["support@hackathon.org"],
                        "subject": "Extension Request",
                        "body_text": "Body",
                    },
                },
            )

        assert response.status_code == 403
        data = response.json()
        assert data["error_code"] == "reauth_required"
        assert data["account_id"] == account.id

    def test_send_email_confirmation_enforcement(self, client, db):
        """Sending without confirmed=True MUST be rejected."""
        user, account, opp, email = self._setup_entities(db)

        response = client.post(
            "/email-composer/send",
            json={
                "account_id": account.id,
                "opportunity_id": opp.id,
                "to": ["support@hackathon.org"],
                "subject": "Extension Request",
                "body_text": "Body",
                "confirmed": False,  # Explicitly False
            },
        )
        assert response.status_code == 400
        assert "confirmation" in response.json()["detail"].lower()

    def test_send_email_success_records_timeline(self, client, db):
        user, account, opp, email = self._setup_entities(db)

        now = datetime.now(timezone.utc)
        mock_result = {
            "message_id": "sent_msg_999",
            "thread_id": "th_src_123",
            "sent_at": now,
            "account_id": account.id,
            "to": ["support@hackathon.org"],
            "subject": "Final Extension Request",
        }

        with patch("app.api.email_composer.build_credentials_from_encrypted"), \
             patch("app.api.email_composer.send_gmail_message", return_value=mock_result):

            response = client.post(
                "/email-composer/send",
                json={
                    "account_id": account.id,
                    "opportunity_id": opp.id,
                    "to": ["support@hackathon.org"],
                    "subject": "Final Extension Request",
                    "body_text": "Body of email.",
                    "confirmed": True,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["message_id"] == "sent_msg_999"

        # Verify activity timeline recorded in DB
        timeline = (
            db.query(OpportunityStatusHistory)
            .filter(
                OpportunityStatusHistory.opportunity_id == opp.id,
                OpportunityStatusHistory.new_status == "EMAIL_SENT",
            )
            .first()
        )
        assert timeline is not None
        assert timeline.opportunity_id == opp.id

    def test_send_email_reauth_required(self, client, db):
        user, account, opp, email = self._setup_entities(db)

        with patch("app.api.email_composer.build_credentials_from_encrypted"), \
             patch("app.api.email_composer.send_gmail_message", side_effect=OAuthScopeError("Scope error", account_id=account.id)):

            response = client.post(
                "/email-composer/send",
                json={
                    "account_id": account.id,
                    "opportunity_id": opp.id,
                    "to": ["support@hackathon.org"],
                    "subject": "Subject",
                    "body_text": "Body",
                    "confirmed": True,
                },
            )

        assert response.status_code == 403
        data = response.json()
        assert data["error_code"] == "reauth_required"
        assert data["account_id"] == account.id
