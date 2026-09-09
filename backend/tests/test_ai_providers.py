"""
CareerMail AI — Unit Tests for Multi-Provider AI Implementations.

Tests:
  • BaseAIProvider response parsing (clean JSON, code fences, conversational wrapper)
  • GeminiProvider error mapping (429, 401, 403, 500, timeout)
  • GroqProvider HTTP execution and exception mapping
  • OpenRouterProvider HTTP execution and exception mapping
  • HuggingFaceProvider HTTP execution, model loading handling, and exception mapping
  • Unconfigured provider handling
"""

import json
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.schemas.extraction import Category, ExtractionResult, Priority, Status
from app.services.ai.base import (
    AIAuthError,
    AIConfigurationError,
    AIRateLimitError,
    AISchemaError,
    AITimeoutError,
    AITransientError,
    clean_json_text,
    parse_and_validate_analysis,
)
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.groq_provider import GroqProvider
from app.services.ai.huggingface_provider import HuggingFaceProvider
from app.services.ai.openrouter_provider import OpenRouterProvider


# ── Sample Extraction Payloads ─────────────────────────────────

SAMPLE_ANALYSIS_DICT = {
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
    "important_facts": ["Round 2 presentation due Oct 15"],
}


class TestBaseAIResponseParsing:
    def test_clean_json_text_pure_json(self):
        raw = json.dumps(SAMPLE_ANALYSIS_DICT)
        cleaned = clean_json_text(raw)
        assert cleaned.startswith("{") and cleaned.endswith("}")

    def test_clean_json_text_markdown_fence(self):
        raw = f"```json\n{json.dumps(SAMPLE_ANALYSIS_DICT)}\n```"
        cleaned = clean_json_text(raw)
        assert cleaned.startswith("{") and cleaned.endswith("}")

    def test_clean_json_text_conversational_wrapping(self):
        raw = f"Here is your structured JSON:\n\n{json.dumps(SAMPLE_ANALYSIS_DICT)}\n\nHope this helps!"
        cleaned = clean_json_text(raw)
        assert cleaned.startswith("{") and cleaned.endswith("}")

    def test_parse_and_validate_valid_payload(self):
        raw = json.dumps(SAMPLE_ANALYSIS_DICT)
        analysis = parse_and_validate_analysis(raw, provider_name="test")
        assert analysis.category == Category.hackathon
        assert analysis.title == "Smart India Hackathon 2026"
        assert analysis.status == Status.shortlisted

    def test_parse_and_validate_empty_raises_schema_error(self):
        with pytest.raises(AISchemaError) as exc_info:
            parse_and_validate_analysis("", provider_name="test")
        assert "empty" in exc_info.value.message.lower()

    def test_parse_and_validate_invalid_json_raises_schema_error(self):
        with pytest.raises(AISchemaError) as exc_info:
            parse_and_validate_analysis("not json", provider_name="test")
        assert "invalid json" in exc_info.value.message.lower()


class TestGeminiProvider:
    def test_gemini_unconfigured_raises(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        provider = GeminiProvider(api_key="")
        assert not provider.is_configured()
        with pytest.raises(AIConfigurationError):
            provider.extract_email_data("sender", "subject", "2026-09-08T00:00:00Z", "body")

    def test_gemini_success(self):
        provider = GeminiProvider(api_key="mock-key", model="gemini-2.0-flash")
        provider._client = MagicMock()

        mock_resp = MagicMock()
        mock_resp.text = json.dumps(SAMPLE_ANALYSIS_DICT)
        provider._client.models.generate_content.return_value = mock_resp

        result = provider.extract_email_data("sender@ex.com", "Hackathon", "2026-09-08T00:00:00Z", "body")
        assert isinstance(result, ExtractionResult)
        assert result.processing_status == "extracted"
        assert result.analysis.category == Category.hackathon

    def test_gemini_rate_limited_maps_to_airatelimiterror(self):
        provider = GeminiProvider(api_key="mock-key")
        provider._client = MagicMock()
        provider._client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED Quota exceeded")

        with pytest.raises(AIRateLimitError):
            provider.extract_email_data("sender@ex.com", "Subject", "2026-09-08T00:00:00Z", "body")

    def test_gemini_auth_error_maps_to_aiautherror(self):
        provider = GeminiProvider(api_key="mock-key")
        provider._client = MagicMock()
        provider._client.models.generate_content.side_effect = Exception("401 API_KEY_INVALID")

        with pytest.raises(AIAuthError):
            provider.extract_email_data("sender@ex.com", "Subject", "2026-09-08T00:00:00Z", "body")

    def test_gemini_config_error_maps_to_aiconfigurationerror(self):
        provider = GeminiProvider(api_key="mock-key")
        provider._client = MagicMock()
        provider._client.models.generate_content.side_effect = Exception("403 PERMISSION_DENIED model not found")

        with pytest.raises(AIConfigurationError):
            provider.extract_email_data("sender@ex.com", "Subject", "2026-09-08T00:00:00Z", "body")

    def test_gemini_transient_error_maps_to_aitransienterror(self):
        provider = GeminiProvider(api_key="mock-key")
        provider._client = MagicMock()
        provider._client.models.generate_content.side_effect = Exception("503 Service Unavailable")

        with pytest.raises(AITransientError):
            provider.extract_email_data("sender@ex.com", "Subject", "2026-09-08T00:00:00Z", "body")

    def test_gemini_timeout_maps_to_aitimeouterror(self):
        provider = GeminiProvider(api_key="mock-key")
        provider._client = MagicMock()
        provider._client.models.generate_content.side_effect = Exception("Deadline exceeded timeout")

        with pytest.raises(AITimeoutError):
            provider.extract_email_data("sender@ex.com", "Subject", "2026-09-08T00:00:00Z", "body")


class TestGroqProvider:
    def test_groq_unconfigured_raises(self):
        provider = GroqProvider(api_key="")
        assert not provider.is_configured()
        with pytest.raises(AIConfigurationError):
            provider.extract_email_data("s", "sub", "2026-09-08T00:00:00Z", "body")

    @patch("httpx.Client.post")
    def test_groq_success(self, mock_post):
        provider = GroqProvider(api_key="mock-groq-key", model="llama-3.3-70b-versatile")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(SAMPLE_ANALYSIS_DICT)}}]
        }
        mock_post.return_value = mock_resp

        result = provider.extract_email_data("sender@groq.com", "Internship", "2026-09-08T00:00:00Z", "body")
        assert result.processing_status == "extracted"
        assert result.analysis.title == "Smart India Hackathon 2026"
        assert result.model_used == "llama-3.3-70b-versatile"

    @patch("httpx.Client.post")
    def test_groq_429_rate_limit(self, mock_post):
        provider = GroqProvider(api_key="mock-groq-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = {"error": {"message": "Rate limit reached"}}
        mock_post.return_value = mock_resp

        with pytest.raises(AIRateLimitError):
            provider.extract_email_data("s", "sub", "2026-09-08T00:00:00Z", "body")

    @patch("httpx.Client.post")
    def test_groq_401_auth_error(self, mock_post):
        provider = GroqProvider(api_key="mock-groq-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": {"message": "Invalid API key"}}
        mock_post.return_value = mock_resp

        with pytest.raises(AIAuthError):
            provider.extract_email_data("s", "sub", "2026-09-08T00:00:00Z", "body")

    @patch("httpx.Client.post")
    def test_groq_timeout_exception(self, mock_post):
        provider = GroqProvider(api_key="mock-groq-key")
        mock_post.side_effect = httpx.ReadTimeout("Read timed out")

        with pytest.raises(AITimeoutError):
            provider.extract_email_data("s", "sub", "2026-09-08T00:00:00Z", "body")


class TestOpenRouterProvider:
    def test_openrouter_unconfigured_raises(self):
        provider = OpenRouterProvider(api_key="")
        assert not provider.is_configured()
        with pytest.raises(AIConfigurationError):
            provider.extract_email_data("s", "sub", "2026-09-08T00:00:00Z", "body")

    @patch("httpx.Client.post")
    def test_openrouter_success(self, mock_post):
        provider = OpenRouterProvider(api_key="mock-or-key", model="meta-llama/llama-3.3-70b-instruct:free")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(SAMPLE_ANALYSIS_DICT)}}]
        }
        mock_post.return_value = mock_resp

        result = provider.extract_email_data("sender@or.ai", "Event", "2026-09-08T00:00:00Z", "body")
        assert result.processing_status == "extracted"
        assert result.analysis.category == Category.hackathon

    @patch("httpx.Client.post")
    def test_openrouter_403_config_error(self, mock_post):
        provider = OpenRouterProvider(api_key="mock-or-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"error": {"message": "Model access denied"}}
        mock_post.return_value = mock_resp

        with pytest.raises(AIConfigurationError):
            provider.extract_email_data("s", "sub", "2026-09-08T00:00:00Z", "body")


class TestHuggingFaceProvider:
    def test_huggingface_unconfigured_raises(self):
        provider = HuggingFaceProvider(api_key="")
        assert not provider.is_configured()
        with pytest.raises(AIConfigurationError):
            provider.extract_email_data("s", "sub", "2026-09-08T00:00:00Z", "body")

    @patch("httpx.Client.post")
    def test_huggingface_success_choices_format(self, mock_post):
        provider = HuggingFaceProvider(api_key="mock-hf-key", model="meta-llama/Llama-3.3-70B-Instruct")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(SAMPLE_ANALYSIS_DICT)}}]
        }
        mock_post.return_value = mock_resp

        result = provider.extract_email_data("sender@hf.co", "Coding Contest", "2026-09-08T00:00:00Z", "body")
        assert result.processing_status == "extracted"
        assert result.analysis.category == Category.hackathon

    @patch("httpx.Client.post")
    def test_huggingface_model_loading_503_transient(self, mock_post):
        provider = HuggingFaceProvider(api_key="mock-hf-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.json.return_value = {"error": "Model is currently loading", "estimated_time": 20.0}
        mock_post.return_value = mock_resp

        with pytest.raises(AITransientError) as exc_info:
            provider.extract_email_data("s", "sub", "2026-09-08T00:00:00Z", "body")
        assert "loading" in exc_info.value.message.lower()
