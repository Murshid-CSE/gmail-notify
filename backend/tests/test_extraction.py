"""
CareerMail AI — Extraction Service & Schema Tests.

Tests:
  • EmailAnalysis Pydantic schema validation & defaults
  • GeminiClient parsing, error handling, retries, and markdown cleaning
  • Extractor pipeline orchestrator (filter → Gemini → DB state update)
  • Batch processing of pending emails
"""

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock, patch
import pytest
from pydantic import ValidationError

from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.models.user import User
from app.schemas.extraction import (
    Category,
    EmailAnalysis,
    ExtractionResult,
    Priority,
    Status,
)
from app.services.ai.gemini import GeminiClient, is_gemini_configured
from app.services.extraction.extractor import process_email, process_pending_emails


class TestExtractionSchemas:
    def test_full_email_analysis_valid(self):
        data = {
            "category": "hackathon",
            "title": "Smart India Hackathon 2026",
            "organization": "Ministry of Education",
            "description": "National hackathon for engineering students.",
            "status": "shortlisted",
            "round_name": "Round 2",
            "deadline": "2026-10-15T23:59:59Z",
            "event_date": "2026-11-01",
            "location": "New Delhi / Online",
            "eligibility": "B.Tech students",
            "action_required": True,
            "action": "Submit prototype presentation",
            "apply_url": "https://sih.gov.in",
            "event_url": "https://sih.gov.in/guidelines",
            "contact_emails": ["support@sih.gov.in"],
            "priority": "high",
            "confidence": 0.95,
            "important_facts": ["Round 2 presentation due Oct 15", "Team size max 6"],
        }
        analysis = EmailAnalysis.model_validate(data)
        assert analysis.category == Category.hackathon
        assert analysis.status == Status.shortlisted
        assert analysis.priority == Priority.high
        assert analysis.title == "Smart India Hackathon 2026"
        assert analysis.action_required is True
        assert analysis.confidence == 0.95

    def test_minimal_email_analysis_defaults(self):
        analysis = EmailAnalysis(category=Category.internship)
        assert analysis.category == Category.internship
        assert analysis.title is None
        assert analysis.organization is None
        assert analysis.status == Status.unknown
        assert analysis.priority == Priority.medium
        assert analysis.action_required is False
        assert analysis.confidence == 0.5
        assert analysis.deadline is None
        assert analysis.apply_url is None

    def test_invalid_category_raises(self):
        with pytest.raises(ValidationError):
            EmailAnalysis.model_validate({"category": "crypto_scam"})

    def test_confidence_clamping(self):
        high = EmailAnalysis(category=Category.exam, confidence=1.5)
        assert high.confidence == 1.0

        low = EmailAnalysis(category=Category.exam, confidence=-0.5)
        assert low.confidence == 0.0

        none_val = EmailAnalysis(category=Category.exam, confidence=None)
        assert none_val.confidence == 0.5

    def test_empty_string_date_becomes_none(self):
        analysis = EmailAnalysis(
            category=Category.placement,
            deadline="   ",
            event_date="",
        )
        assert analysis.deadline is None
        assert analysis.event_date is None


class TestGeminiClient:
    def test_client_raises_without_api_key(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        with patch("app.services.ai.gemini.get_settings") as mock_settings:
            mock_settings.return_value.GEMINI_API_KEY = ""
            with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not configured"):
                GeminiClient(api_key="")

    @patch("app.services.ai.gemini.genai.Client")
    def test_extract_email_data_success(self, mock_genai_cls):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "category": "hackathon",
            "title": "HackMIT 2026",
            "organization": "MIT",
            "status": "next_round",
            "action_required": True,
            "action": "RSVP by tomorrow",
            "confidence": 0.9,
        })
        mock_genai_cls.return_value.models.generate_content.return_value = mock_response

        client = GeminiClient(api_key="test-api-key")
        result = client.extract_email_data(
            sender="team@hackmit.org",
            subject="You are through to Round 2!",
            received_at="2026-09-08T10:00:00Z",
            body_text="Congrats! You made it to Round 2.",
        )

        assert result.processing_status == "extracted"
        assert result.analysis is not None
        assert result.analysis.category == Category.hackathon
        assert result.analysis.status == Status.next_round
        assert result.analysis.title == "HackMIT 2026"

    @patch("app.services.ai.gemini.genai.Client")
    def test_extract_strips_markdown_code_fences(self, mock_genai_cls):
        mock_response = MagicMock()
        mock_response.text = "```json\n" + json.dumps({
            "category": "internship",
            "title": "Summer SDE",
            "organization": "Google",
            "status": "assessment",
        }) + "\n```"
        mock_genai_cls.return_value.models.generate_content.return_value = mock_response

        client = GeminiClient(api_key="test-key")
        result = client.extract_email_data(
            sender="google@recruiting.com",
            subject="Snapshot Assessment",
            received_at="2026-09-08T10:00:00Z",
            body_text="Complete the snapshot test.",
        )

        assert result.processing_status == "extracted"
        assert result.analysis.category == Category.internship
        assert result.analysis.organization == "Google"

    @patch("app.services.ai.gemini.genai.Client")
    def test_extract_handles_empty_response(self, mock_genai_cls):
        mock_response = MagicMock()
        mock_response.text = ""
        mock_genai_cls.return_value.models.generate_content.return_value = mock_response

        client = GeminiClient(api_key="test-key")
        result = client.extract_email_data(
            sender="test@test.com",
            subject="Test",
            received_at="2026-09-08T10:00:00Z",
            body_text="Body",
            max_retries=1,
        )

        assert result.processing_status == "extraction_failed"
        assert result.analysis is None
        assert "Empty response" in (result.error or "")

    @patch("app.services.ai.gemini.genai.Client")
    def test_extract_handles_invalid_json_gracefully(self, mock_genai_cls):
        mock_response = MagicMock()
        mock_response.text = "This is definitely not JSON."
        mock_genai_cls.return_value.models.generate_content.return_value = mock_response

        client = GeminiClient(api_key="test-key")
        result = client.extract_email_data(
            sender="test@test.com",
            subject="Test",
            received_at="2026-09-08T10:00:00Z",
            body_text="Body",
            max_retries=1,
        )

        assert result.processing_status == "extraction_failed"
        assert result.analysis is None
        assert "JSON parsing failed" in (result.error or "")


class TestExtractorPipeline:
    def _create_test_account(self, db):
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
        return account

    def test_process_email_filtered_out(self, db):
        account = self._create_test_account(db)
        email = EmailMessage(
            account_id=account.id,
            gmail_message_id="msg_noise_1",
            gmail_thread_id="th_noise_1",
            sender="promo@deals.com",
            subject="Flash sale 50% discount on clothes",
            received_at=datetime.now(timezone.utc),
            body_text="Unsubscribe from this list. Limited time offer on shoes.",
            processing_status="pending",
        )
        db.add(email)
        db.commit()

        result = process_email(db, email)
        assert result.processing_status == "filtered_out"
        assert email.is_relevant is False
        assert email.processing_status == "filtered_out"

    def test_process_email_gemini_not_configured(self, db, monkeypatch):
        account = self._create_test_account(db)
        email = EmailMessage(
            account_id=account.id,
            gmail_message_id="msg_rel_1",
            gmail_thread_id="th_rel_1",
            sender="hackathon@devpost.com",
            subject="Devpost Hackathon Submission Open",
            received_at=datetime.now(timezone.utc),
            body_text="Register now for the hackathon competition.",
            processing_status="pending",
        )
        db.add(email)
        db.commit()

        with patch("app.services.extraction.extractor.is_gemini_configured", return_value=False):
            result = process_email(db, email)
            assert result.processing_status == "pending_extraction"
            assert email.is_relevant is True
            assert email.processing_status == "pending_extraction"

    def test_process_email_with_mock_gemini_client(self, db):
        account = self._create_test_account(db)
        email = EmailMessage(
            account_id=account.id,
            gmail_message_id="msg_rel_2",
            gmail_thread_id="th_rel_2",
            sender="cdc@college.edu",
            subject="Placement Drive: Microsoft Campus Hiring",
            received_at=datetime.now(timezone.utc),
            body_text="Microsoft is conducting campus recruitment for SDE. Pre-placement talk tomorrow.",
            processing_status="pending",
        )
        db.add(email)
        db.commit()

        mock_gemini = MagicMock()
        mock_analysis = EmailAnalysis(
            category=Category.placement,
            title="Microsoft Campus Hiring",
            organization="Microsoft",
            status=Status.opportunity,
            action_required=True,
            action="Attend pre-placement talk",
            priority=Priority.high,
            confidence=0.95,
        )
        mock_gemini.extract_email_data.return_value = ExtractionResult(
            analysis=mock_analysis,
            processing_status="extracted",
            model_used="gemini-2.0-flash",
            latency_ms=250.0,
        )

        with patch("app.services.extraction.extractor.is_gemini_configured", return_value=True):
            result = process_email(db, email, gemini_client=mock_gemini)
            assert result.processing_status == "extracted"
            assert email.is_relevant is True
            assert email.processing_status == "extracted"
            assert result.analysis.organization == "Microsoft"

    def test_process_pending_emails_batch(self, db):
        account = self._create_test_account(db)
        # Add 1 noise email and 1 relevant email
        noise_email = EmailMessage(
            account_id=account.id,
            gmail_message_id="batch_noise_1",
            gmail_thread_id="th_b1",
            sender="spam@sale.com",
            subject="Special discount offer",
            received_at=datetime.now(timezone.utc),
            body_text="Unsubscribe from this list. Flash sale on electronics.",
            processing_status="pending",
        )
        rel_email = EmailMessage(
            account_id=account.id,
            gmail_message_id="batch_rel_1",
            gmail_thread_id="th_b2",
            sender="internships@meta.com",
            subject="Meta SWE Internship Application Update",
            received_at=datetime.now(timezone.utc),
            body_text="Thank you for applying to the software engineer internship.",
            processing_status="pending",
        )
        db.add_all([noise_email, rel_email])
        db.commit()

        with patch("app.services.extraction.extractor.is_gemini_configured", return_value=False):
            summary = process_pending_emails(db, limit=10)

        assert summary["total"] == 2
        assert summary["filtered_out"] == 1
        assert summary["pending_extraction"] == 1
        assert noise_email.processing_status == "filtered_out"
        assert rel_email.processing_status == "pending_extraction"
