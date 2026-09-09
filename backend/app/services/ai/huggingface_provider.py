"""
CareerMail AI — Hugging Face AI Provider.

Implementation of BaseAIProvider using Hugging Face Serverless Inference API
(OpenAI-compatible chat completions interface).
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


logger = get_logger("ai.provider.huggingface")

HF_CHAT_URL = "https://api-inference.huggingface.co/v1/chat/completions"


class HuggingFaceProvider(BaseAIProvider):
    """Hugging Face provider implementing BaseAIProvider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 25.0,
    ):
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.HUGGINGFACE_API_KEY
        self._model = model if model is not None else settings.HUGGINGFACE_MODEL
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "huggingface"

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
        """Extract structured career data using Hugging Face Inference API."""
        if not self.is_configured():
            raise AIConfigurationError("Hugging Face API key is not configured", provider=self.name)

        start_time = time.time()
        user_prompt = build_extraction_prompt(sender, subject, received_at, body_text)

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(HF_CHAT_URL, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            logger.warning("HUGGINGFACE_TIMEOUT | provider=%s", self.name)
            raise AITimeoutError("Hugging Face request timed out", provider=self.name) from exc
        except (httpx.NetworkError, httpx.ConnectError) as exc:
            logger.warning("HUGGINGFACE_CONNECTION_ERROR | provider=%s", self.name)
            raise AITransientError(f"Hugging Face network error: {type(exc).__name__}", provider=self.name) from exc
        except Exception as exc:
            logger.error("HUGGINGFACE_REQUEST_ERROR | provider=%s | error_type=%s", self.name, type(exc).__name__)
            raise AITransientError(f"Hugging Face request failed: {type(exc).__name__}", provider=self.name) from exc

        if response.status_code != 200:
            self._handle_error_response(response)

        latency_ms = (time.time() - start_time) * 1000

        try:
            res_json = response.json()
            if isinstance(res_json, dict) and "choices" in res_json:
                raw_text = res_json["choices"][0]["message"]["content"]
            elif isinstance(res_json, list) and len(res_json) > 0 and "generated_text" in res_json[0]:
                raw_text = res_json[0]["generated_text"]
            else:
                raw_text = str(res_json)
        except Exception as exc:
            logger.warning("HUGGINGFACE_RESPONSE_FORMAT_ERROR | provider=%s", self.name)
            raise AITransientError(f"Malformed JSON response envelope from Hugging Face: {exc}", provider=self.name) from exc

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
        """Generate structured email draft using Hugging Face Inference API."""
        if not self.is_configured():
            raise AIConfigurationError("Hugging Face API key is not configured", provider=self.name)

        user_prompt = build_composer_prompt(opportunity_context, instruction)
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": EMAIL_COMPOSER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(HF_CHAT_URL, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise AITimeoutError("Hugging Face request timed out", provider=self.name) from exc
        except (httpx.NetworkError, httpx.ConnectError) as exc:
            raise AITransientError(f"Hugging Face network error: {type(exc).__name__}", provider=self.name) from exc
        except Exception as exc:
            raise AITransientError(f"Hugging Face request failed: {type(exc).__name__}", provider=self.name) from exc

        if response.status_code != 200:
            self._handle_error_response(response)

        try:
            res_json = response.json()
            raw_text = res_json["choices"][0]["message"]["content"]
        except Exception as exc:
            raise AITransientError(f"Malformed JSON response envelope from Hugging Face: {exc}", provider=self.name) from exc

        return parse_and_validate_draft(raw_text, provider_name=self.name)


    def _handle_error_response(self, response: httpx.Response) -> None:
        """Map HTTP error status codes to standard AIProviderError exceptions."""
        status_code = response.status_code
        try:
            body = response.json()
            err_msg = str(body.get("error", body)).lower()
        except Exception:
            err_msg = response.text.lower()

        if status_code == 429:
            logger.warning("HUGGINGFACE_RATE_LIMITED | provider=%s | status=429", self.name)
            raise AIRateLimitError("Hugging Face rate limit or quota exceeded", provider=self.name, status_code=429)

        if status_code == 401:
            logger.warning("HUGGINGFACE_AUTH_ERROR | provider=%s | status=401", self.name)
            raise AIAuthError("Hugging Face authentication failed: invalid API token", provider=self.name, status_code=401)

        if status_code == 403:
            logger.warning("HUGGINGFACE_FORBIDDEN | provider=%s | status=403", self.name)
            raise AIConfigurationError("Hugging Face access forbidden: gated model or missing repo permission", provider=self.name, status_code=403)

        if status_code in (400, 404) and ("model" in err_msg or "not found" in err_msg or "does not exist" in err_msg):
            logger.warning("HUGGINGFACE_MODEL_CONFIG_ERROR | provider=%s | status=%d", self.name, status_code)
            raise AIConfigurationError(f"Hugging Face model error: {self._model}", provider=self.name, status_code=status_code)

        # Loading models on HF return 503 with estimated_time
        if status_code == 503 and "loading" in err_msg:
            logger.warning("HUGGINGFACE_MODEL_LOADING | provider=%s | status=503", self.name)
            raise AITransientError("Hugging Face model is currently loading", provider=self.name, status_code=503)

        if status_code >= 500:
            logger.warning("HUGGINGFACE_SERVER_ERROR | provider=%s | status=%d", self.name, status_code)
            raise AITransientError(f"Hugging Face server error: {status_code}", provider=self.name, status_code=status_code)

        logger.error("HUGGINGFACE_UNKNOWN_ERROR | provider=%s | status=%d", self.name, status_code)
        raise AITransientError(f"Hugging Face API call returned HTTP {status_code}", provider=self.name, status_code=status_code)
