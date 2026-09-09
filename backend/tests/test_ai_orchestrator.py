"""
CareerMail AI — AI Orchestrator & Fallback Chain Tests.

Tests:
  1. Primary provider succeeds -> no fallback, metrics tracked
  2. Primary 429 rate limit -> immediate fallback to secondary
  3. Transient 5xx error -> retry once with backoff -> fallback to secondary
  4. Timeout error -> retry once with backoff -> fallback
  5. Schema error -> retry once -> fallback
  6. Multi-level fallback chain (Gemini -> Groq -> OpenRouter -> Hugging Face)
  7. All providers fail -> graceful ExtractionResult(processing_status="extraction_failed")
  8. No providers configured -> ExtractionResult(processing_status="pending_extraction")
  9. 401/403 auth error -> provider temporarily disabled for orchestrator lifecycle
 10. Data-driven provider ordering from settings
 11. Unconfigured providers skipped
 12. In-memory metrics tracking
 13. Strict security: zero secrets or authorization headers in metrics/logs
 14. Test isolation: fresh orchestrator instances with mock injection
"""

from unittest.mock import MagicMock, patch
import pytest

from app.schemas.extraction import Category, EmailAnalysis, ExtractionResult, Status
from app.services.ai.base import (
    AIAuthError,
    AIConfigurationError,
    AIRateLimitError,
    AISchemaError,
    AITimeoutError,
    AITransientError,
    BaseAIProvider,
)
from app.services.ai.orchestrator import AIOrchestrator, get_ai_orchestrator


class MockProvider(BaseAIProvider):
    """Configurable mock provider for orchestrator unit testing."""

    def __init__(self, name: str, configured: bool = True, model: str = "mock-model"):
        self._name = name
        self._configured = configured
        self._model = model
        self.call_count = 0
        self.side_effects = []
        self.return_analysis = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return self._configured

    def extract_email_data(self, sender: str, subject: str, received_at: str, body_text: str) -> ExtractionResult:
        self.call_count += 1
        if self.side_effects:
            effect = self.side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect

        analysis = self.return_analysis or EmailAnalysis(
            category=Category.hackathon,
            title=f"Opportunity from {self._name}",
            status=Status.shortlisted,
        )
        return ExtractionResult(
            analysis=analysis,
            processing_status="extracted",
            model_used=self._model,
            latency_ms=42.0,
        )


class TestAIOrchestrator:
    def test_primary_succeeds_no_fallback(self):
        primary = MockProvider("gemini")
        fallback = MockProvider("groq")
        orchestrator = AIOrchestrator(providers=[primary, fallback])

        result = orchestrator.extract_email_data("sender", "subject", "2026-09-08T00:00:00Z", "body")

        assert result.processing_status == "extracted"
        assert result.analysis.title == "Opportunity from gemini"
        assert primary.call_count == 1
        assert fallback.call_count == 0

        metrics = orchestrator.get_metrics()
        assert metrics["fallbacks_count"] == 0
        assert metrics["last_provider_used"] == "gemini"
        assert metrics["requests_success"]["gemini"] == 1

    def test_gemini_429_immediately_falls_back_to_groq(self):
        gemini = MockProvider("gemini")
        gemini.side_effects = [AIRateLimitError("429 rate limit exceeded", provider="gemini", status_code=429)]
        groq = MockProvider("groq")

        orchestrator = AIOrchestrator(providers=[gemini, groq])
        result = orchestrator.extract_email_data("sender", "subject", "2026-09-08T00:00:00Z", "body")

        assert result.processing_status == "extracted"
        assert result.analysis.title == "Opportunity from groq"
        # 429 should NOT retry gemini — immediate failover
        assert gemini.call_count == 1
        assert groq.call_count == 1

        metrics = orchestrator.get_metrics()
        assert metrics["fallbacks_count"] == 1
        assert metrics["last_provider_used"] == "groq"
        assert metrics["provider_health"]["gemini"] == "rate_limited"

    @patch("time.sleep", return_value=None)
    def test_transient_error_retries_once_then_falls_back(self, mock_sleep):
        gemini = MockProvider("gemini")
        # Fails both initial and retry
        gemini.side_effects = [
            AITransientError("503 Service Unavailable", provider="gemini"),
            AITransientError("503 Service Unavailable", provider="gemini"),
        ]
        groq = MockProvider("groq")

        orchestrator = AIOrchestrator(providers=[gemini, groq])
        result = orchestrator.extract_email_data("sender", "subject", "2026-09-08T00:00:00Z", "body")

        assert result.processing_status == "extracted"
        assert result.analysis.title == "Opportunity from groq"
        # Called twice (initial + 1 bounded retry)
        assert gemini.call_count == 2
        assert groq.call_count == 1
        assert mock_sleep.call_count == 1

    @patch("time.sleep", return_value=None)
    def test_timeout_error_retries_once_then_falls_back(self, mock_sleep):
        gemini = MockProvider("gemini")
        gemini.side_effects = [
            AITimeoutError("Read timeout", provider="gemini"),
            AITimeoutError("Read timeout", provider="gemini"),
        ]
        groq = MockProvider("groq")

        orchestrator = AIOrchestrator(providers=[gemini, groq])
        result = orchestrator.extract_email_data("sender", "subject", "2026-09-08T00:00:00Z", "body")

        assert result.processing_status == "extracted"
        assert gemini.call_count == 2
        assert groq.call_count == 1

    @patch("time.sleep", return_value=None)
    def test_schema_error_retries_once_then_falls_back(self, mock_sleep):
        gemini = MockProvider("gemini")
        gemini.side_effects = [
            AISchemaError("Invalid JSON from LLM", provider="gemini"),
            AISchemaError("Invalid JSON from LLM", provider="gemini"),
        ]
        groq = MockProvider("groq")

        orchestrator = AIOrchestrator(providers=[gemini, groq])
        result = orchestrator.extract_email_data("sender", "subject", "2026-09-08T00:00:00Z", "body")

        assert result.processing_status == "extracted"
        assert gemini.call_count == 2
        assert groq.call_count == 1

    def test_multi_level_fallback_chain(self):
        gemini = MockProvider("gemini")
        gemini.side_effects = [AIRateLimitError("429 rate limit", provider="gemini")]

        groq = MockProvider("groq")
        groq.side_effects = [
            AITransientError("500 internal server error", provider="groq"),
            AITransientError("500 internal server error", provider="groq"),
        ]

        openrouter = MockProvider("openrouter")
        openrouter.side_effects = [AIConfigurationError("Model not accessible", provider="openrouter")]

        huggingface = MockProvider("huggingface")

        with patch("time.sleep", return_value=None):
            orchestrator = AIOrchestrator(providers=[gemini, groq, openrouter, huggingface])
            result = orchestrator.extract_email_data("sender", "subject", "2026-09-08T00:00:00Z", "body")

        assert result.processing_status == "extracted"
        assert result.analysis.title == "Opportunity from huggingface"
        assert gemini.call_count == 1
        assert groq.call_count == 2
        assert openrouter.call_count == 1
        assert huggingface.call_count == 1

        metrics = orchestrator.get_metrics()
        assert metrics["fallbacks_count"] == 3
        assert metrics["last_provider_used"] == "huggingface"

    def test_all_providers_fail_graceful_extraction_failure(self):
        p1 = MockProvider("gemini")
        p1.side_effects = [AIRateLimitError("429", provider="gemini")]
        p2 = MockProvider("groq")
        p2.side_effects = [
            AITransientError("500", provider="groq"),
            AITransientError("500", provider="groq"),
        ]

        with patch("time.sleep", return_value=None):
            orchestrator = AIOrchestrator(providers=[p1, p2])
            result = orchestrator.extract_email_data("sender", "subject", "2026-09-08T00:00:00Z", "body")

        assert result.processing_status == "extraction_failed"
        assert result.analysis is None
        assert "gemini" in result.error
        assert "groq" in result.error

    def test_no_providers_available_pending_extraction(self):
        orchestrator = AIOrchestrator(providers=[])
        result = orchestrator.extract_email_data("sender", "subject", "2026-09-08T00:00:00Z", "body")

        assert result.processing_status == "pending_extraction"
        assert result.analysis is None
        assert "No active AI providers" in result.error

    def test_auth_error_temporarily_disables_provider_and_falls_back(self):
        gemini = MockProvider("gemini")
        gemini.side_effects = [AIAuthError("401 Invalid Key", provider="gemini")]
        groq = MockProvider("groq")

        orchestrator = AIOrchestrator(providers=[gemini, groq])

        # First call: gemini fails with auth error -> disabled -> groq succeeds
        res1 = orchestrator.extract_email_data("sender", "subject", "2026-09-08T00:00:00Z", "body")
        assert res1.processing_status == "extracted"
        assert res1.analysis.title == "Opportunity from groq"
        assert "gemini" in orchestrator._disabled_providers

        # Second call: gemini is skipped immediately without being called again!
        res2 = orchestrator.extract_email_data("sender", "subject", "2026-09-08T00:00:00Z", "body")
        assert res2.processing_status == "extracted"
        assert gemini.call_count == 1  # Still 1! Not called again
        assert groq.call_count == 2

        # Reset state clears disabled list
        orchestrator.reset_state()
        assert "gemini" not in orchestrator._disabled_providers

    def test_orchestrator_respects_settings_chain(self, monkeypatch):
        monkeypatch.setenv("AI_PRIMARY_PROVIDER", "groq")
        monkeypatch.setenv("AI_FALLBACK_PROVIDERS", "gemini,openrouter")
        monkeypatch.setenv("GROQ_API_KEY", "mock-groq")
        monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini")
        monkeypatch.setenv("OPENROUTER_API_KEY", "")  # unconfigured

        with patch("app.services.ai.orchestrator.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.AI_PRIMARY_PROVIDER = "groq"
            mock_s.AI_FALLBACK_PROVIDERS = "gemini,openrouter"
            mock_s.GROQ_API_KEY = "mock-groq"
            mock_s.GEMINI_API_KEY = "mock-gemini"
            mock_s.OPENROUTER_API_KEY = ""
            mock_s.HUGGINGFACE_API_KEY = ""
            mock_settings.return_value = mock_s

            orchestrator = AIOrchestrator()
            assert orchestrator.configured_providers == ["groq", "gemini"]

    def test_no_secrets_in_metrics_or_status(self):
        gemini = MockProvider("gemini")
        orchestrator = AIOrchestrator(providers=[gemini])
        orchestrator.extract_email_data("sender", "subject", "2026-09-08T00:00:00Z", "body")

        metrics = orchestrator.get_metrics()
        metrics_str = str(metrics).lower()

        # Sensitive terms should never appear in telemetry
        forbidden = ["bearer", "key", "secret", "token", "password", "sk-", "gsk_"]
        for term in forbidden:
            assert term not in metrics_str

    def test_get_ai_orchestrator_reset(self):
        orch1 = get_ai_orchestrator(reset=True)
        orch2 = get_ai_orchestrator(reset=False)
        assert orch1 is orch2

        orch3 = get_ai_orchestrator(reset=True)
        assert orch3 is not orch1
