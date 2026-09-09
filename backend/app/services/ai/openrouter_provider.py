"""
CareerMail AI — OpenRouter AI Provider.

Implementation of BaseAIProvider using OpenRouter API.
Enables access to multi-model routing (including free and open-source models)
with standardized exception mapping and robust JSON extraction.
"""

from __future__ import annotations

import time
from typing import Optional

import httpx

from app.config import get_settings
from app.schemas.composer import EmailDraft
from app.schemas.extraction import ExtractionResult

from app.services.ai.base import (
    AIAuthError,
    AIConfigurationError,
    AIRateLimitError,
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


logger = get_logger("ai.provider.openrouter")

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(BaseAIProvider):
    """OpenRouter provider implementing BaseAIProvider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 20.0,
    ):
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.OPENROUTER_API_KEY
        self._model = model if model is not None else settings.OPENROUTER_MODEL
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "openrouter"

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
        """Extract structured career data using OpenRouter API."""
        if not self.is_configured():
            raise AIConfigurationError("OpenRouter API key is not configured", provider=self.name)

        start_time = time.time()
        user_prompt = build_extraction_prompt(sender, subject, received_at, body_text)

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "https://careermail.ai",
            "X-Title": "CareerMail AI",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(OPENROUTER_CHAT_URL, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            logger.warning("OPENROUTER_TIMEOUT | provider=%s", self.name)
            raise AITimeoutError("OpenRouter request timed out", provider=self.name) from exc
        except (httpx.NetworkError, httpx.ConnectError) as exc:
            logger.warning("OPENROUTER_CONNECTION_ERROR | provider=%s", self.name)
            raise AITransientError(f"OpenRouter network error: {type(exc).__name__}", provider=self.name) from exc
        except Exception as exc:
            logger.error("OPENROUTER_REQUEST_ERROR | provider=%s | error_type=%s", self.name, type(exc).__name__)
            raise AITransientError(f"OpenRouter request failed: {type(exc).__name__}", provider=self.name) from exc

        if response.status_code != 200:
            self._handle_error_response(response)

        latency_ms = (time.time() - start_time) * 1000

        try:
            res_json = response.json()
            raw_text = res_json["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("OPENROUTER_RESPONSE_FORMAT_ERROR | provider=%s", self.name)
            raise AITransientError(f"Malformed JSON response envelope from OpenRouter: {exc}", provider=self.name) from exc

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
        """Generate structured email draft using OpenRouter API."""
        if not self.is_configured():
            raise AIConfigurationError("OpenRouter API key is not configured", provider=self.name)

        user_prompt = build_composer_prompt(opportunity_context, instruction)
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": EMAIL_COMPOSER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://careermail.ai",
            "X-Title": "CareerMail AI",
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(OPENROUTER_CHAT_URL, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise AITimeoutError("OpenRouter request timed out", provider=self.name) from exc
        except (httpx.NetworkError, httpx.ConnectError) as exc:
            raise AITransientError(f"OpenRouter network error: {type(exc).__name__}", provider=self.name) from exc
        except Exception as exc:
            raise AITransientError(f"OpenRouter request failed: {type(exc).__name__}", provider=self.name) from exc

        if response.status_code != 200:
            self._handle_error_response(response)

        try:
            res_json = response.json()
            raw_text = res_json["choices"][0]["message"]["content"]
        except Exception as exc:
            raise AITransientError(f"Malformed JSON response envelope from OpenRouter: {exc}", provider=self.name) from exc

        return parse_and_validate_draft(raw_text, provider_name=self.name)


    def _handle_error_response(self, response: httpx.Response) -> None:
        """Map HTTP error status codes to standard AIProviderError exceptions."""
        status_code = response.status_code
        try:
            body = response.json()
            err_msg = str(body.get("error", {})).lower()
        except Exception:
            err_msg = response.text.lower()

        if status_code == 429:
            logger.warning("OPENROUTER_RATE_LIMITED | provider=%s | status=429", self.name)
            raise AIRateLimitError("OpenRouter rate limit or quota exceeded", provider=self.name, status_code=429)

        if status_code == 401:
            logger.warning("OPENROUTER_AUTH_ERROR | provider=%s | status=401", self.name)
            raise AIAuthError("OpenRouter authentication failed: invalid API key", provider=self.name, status_code=401)

        if status_code == 403:
            logger.warning("OPENROUTER_FORBIDDEN | provider=%s | status=403", self.name)
            raise AIConfigurationError("OpenRouter access forbidden: model or account permission issue", provider=self.name, status_code=403)

        if status_code in (400, 404) and ("model" in err_msg or "not_found" in err_msg or "unavailable" in err_msg):
            logger.warning("OPENROUTER_MODEL_CONFIG_ERROR | provider=%s | status=%d", self.name, status_code)
            raise AIConfigurationError(f"OpenRouter model error: {self._model}", provider=self.name, status_code=status_code)

        if status_code >= 500:
            logger.warning("OPENROUTER_SERVER_ERROR | provider=%s | status=%d", self.name, status_code)
            raise AITransientError(f"OpenRouter server error: {status_code}", provider=self.name, status_code=status_code)

        logger.error("OPENROUTER_UNKNOWN_ERROR | provider=%s | status=%d", self.name, status_code)
        raise AITransientError(f"OpenRouter API call returned HTTP {status_code}", provider=self.name, status_code=status_code)
