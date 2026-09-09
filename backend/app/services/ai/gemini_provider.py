"""
CareerMail AI — Google Gemini AI Provider.

Implementation of BaseAIProvider using google-genai SDK.
Standardizes Google Gemini responses and maps SDK exceptions to AIProviderError types.
"""

from __future__ import annotations

import time
from typing import Optional

from google import genai
from google.genai import types

from app.config import get_settings
from app.schemas.composer import EmailDraft
from app.schemas.extraction import ExtractionResult
from app.services.ai.base import (
    AIAuthError,
    AIConfigurationError,
    AIRateLimitError,
    AISchemaError,
    AITimeoutError,
    AITransientError,
    BaseAIProvider,
    parse_and_validate_analysis,
    parse_and_validate_draft,
)
from app.services.ai.composer_prompts import (
    EMAIL_COMPOSER_SYSTEM_PROMPT,
    build_composer_prompt,
)
from app.services.extraction.prompts import SYSTEM_PROMPT, build_extraction_prompt
from app.utils.logging import get_logger

logger = get_logger("ai.provider.gemini")


class GeminiProvider(BaseAIProvider):
    """Gemini provider implementing BaseAIProvider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self._model = model if model is not None else settings.GEMINI_MODEL
        self._client: Optional[genai.Client] = None

        if self._api_key:
            self._client = genai.Client(api_key=self._api_key)

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def extract_email_data(
        self,
        sender: str,
        subject: str,
        received_at: str,
        body_text: str,
    ) -> ExtractionResult:
        """Extract structured career data using Gemini API.

        Raises:
            AIRateLimitError: on quota or rate limit.
            AITransientError: on transient 5xx or server errors.
            AITimeoutError: on request timeouts.
            AIAuthError: on 401 or invalid API key.
            AIConfigurationError: on model permissions or configuration issues.
            AISchemaError: on invalid JSON or malformed schema.
        """
        if not self.is_configured() or self._client is None:
            raise AIConfigurationError(
                "Gemini API key is not configured",
                provider=self.name,
            )

        start_time = time.time()
        user_prompt = build_extraction_prompt(sender, subject, received_at, body_text)

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                    top_p=0.95,
                    max_output_tokens=2048,
                    response_mime_type="application/json",
                ),
            )
            raw_text = response.text or ""
        except Exception as exc:
            self._map_exception(exc)

        latency_ms = (time.time() - start_time) * 1000
        analysis = parse_and_validate_analysis(raw_text, provider_name=self.name)

        return ExtractionResult(
            analysis=analysis,
            processing_status="extracted",
            model_used=self._model,
            latency_ms=round(latency_ms, 1),
        )

    def generate_email_draft(
        self,
        opportunity_context: dict,
        instruction: str,
    ) -> EmailDraft:
        """Generate a structured email draft using Gemini API."""
        if not self.is_configured() or self._client is None:
            raise AIConfigurationError(
                "Gemini API key is not configured",
                provider=self.name,
            )

        user_prompt = build_composer_prompt(opportunity_context, instruction)

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=EMAIL_COMPOSER_SYSTEM_PROMPT,
                    temperature=0.2,
                    top_p=0.95,
                    max_output_tokens=2048,
                    response_mime_type="application/json",
                ),
            )
            raw_text = response.text or ""
        except Exception as exc:
            self._map_exception(exc)

        return parse_and_validate_draft(raw_text, provider_name=self.name)


    def _map_exception(self, exc: Exception) -> None:
        """Classify exceptions from google-genai into standardized provider errors."""
        err_msg = str(exc).lower()

        # 429 / Quota / Rate limit
        if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
            logger.warning("GEMINI_RATE_LIMITED | provider=%s", self.name)
            raise AIRateLimitError("Gemini rate limit or quota exceeded", provider=self.name, status_code=429) from exc

        # 401 / Invalid Key -> AIAuthError
        if "401" in err_msg or "api_key_invalid" in err_msg or "unauthenticated" in err_msg:
            logger.warning("GEMINI_AUTH_ERROR | provider=%s", self.name)
            raise AIAuthError("Gemini authentication failed: invalid or unauthorized key", provider=self.name, status_code=401) from exc

        # Model permission / Not Found / Access Forbidden -> AIConfigurationError
        if "403" in err_msg or "permission_denied" in err_msg or "not_found" in err_msg or "invalid_argument" in err_msg:
            logger.warning("GEMINI_CONFIG_ERROR | provider=%s", self.name)
            raise AIConfigurationError(f"Gemini configuration error: {type(exc).__name__}", provider=self.name, status_code=403) from exc

        # Timeout
        if "timeout" in err_msg or "timed out" in err_msg or "deadline_exceeded" in err_msg:
            logger.warning("GEMINI_TIMEOUT | provider=%s", self.name)
            raise AITimeoutError("Gemini request timed out", provider=self.name) from exc

        # 5xx / Transient
        if any(token in err_msg for token in ("500", "503", "502", "504", "unavailable", "internal")):
            logger.warning("GEMINI_TRANSIENT_ERROR | provider=%s", self.name)
            raise AITransientError(f"Gemini service unavailable or internal error: {type(exc).__name__}", provider=self.name, status_code=503) from exc

        # Generic fallback to transient error
        logger.error("GEMINI_ERROR | provider=%s | error_type=%s", self.name, type(exc).__name__)
        raise AITransientError(f"Gemini call failed: {type(exc).__name__}", provider=self.name) from exc
