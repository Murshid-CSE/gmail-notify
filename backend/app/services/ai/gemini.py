"""
CareerMail AI — Gemini AI Client.

Wrapper around the google-genai SDK for structured email extraction.
Handles: configuration, API calls, retries, error handling.

Does NOT hardcode API keys or model names — reads from config.
"""

from __future__ import annotations

import json
import re
import time
from typing import Optional

from google import genai
from google.genai import types

from app.config import get_settings
from app.schemas.extraction import EmailAnalysis, ExtractionResult
from app.services.extraction.prompts import SYSTEM_PROMPT, build_extraction_prompt
from app.utils.logging import get_logger

logger = get_logger("ai.gemini")


class GeminiClient:
    """Client for Gemini AI extraction.

    Usage::

        client = GeminiClient()
        result = client.extract_email_data(
            sender="hackathon@example.com",
            subject="You've been shortlisted!",
            received_at="2026-09-01T12:00:00Z",
            body_text="Congratulations, your team has been shortlisted...",
        )
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        settings = get_settings()
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._model = model or settings.GEMINI_MODEL

        if not self._api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured. "
                "Set it in .env or pass api_key to GeminiClient."
            )

        self._client = genai.Client(api_key=self._api_key)

    @property
    def model_name(self) -> str:
        return self._model

    def extract_email_data(
        self,
        sender: str,
        subject: str,
        received_at: str,
        body_text: str,
        *,
        max_retries: int = 3,
    ) -> ExtractionResult:
        """Extract structured data from an email using Gemini.

        Args:
            sender: Email sender.
            subject: Email subject.
            received_at: ISO timestamp of receipt.
            body_text: Cleaned plain-text body.
            max_retries: Max retry attempts for transient failures.

        Returns:
            ExtractionResult with analysis or error information.
        """
        start_time = time.time()
        user_prompt = build_extraction_prompt(sender, subject, received_at, body_text)

        last_error: Optional[str] = None

        for attempt in range(1, max_retries + 1):
            try:
                response = self._call_gemini(user_prompt)
                latency_ms = (time.time() - start_time) * 1000

                if not response:
                    last_error = "Empty response from Gemini"
                    logger.warning(
                        "GEMINI_EMPTY_RESPONSE | attempt=%d/%d",
                        attempt, max_retries,
                    )
                    continue

                # Parse the JSON from response.
                analysis = self._parse_response(response)

                logger.info(
                    "EXTRACTION_SUCCESS | category=%s | status=%s | confidence=%.2f | latency=%.0fms",
                    analysis.category.value,
                    analysis.status.value,
                    analysis.confidence,
                    latency_ms,
                )

                return ExtractionResult(
                    analysis=analysis,
                    processing_status="extracted",
                    model_used=self._model,
                    latency_ms=round(latency_ms, 1),
                )

            except (json.JSONDecodeError, ValueError) as exc:
                last_error = f"JSON parsing failed: {exc}"
                logger.warning(
                    "GEMINI_PARSE_ERROR | attempt=%d/%d | error=%s",
                    attempt, max_retries, str(exc),
                )
                # Don't retry parse errors immediately — model might
                # return same bad format.
                if attempt < max_retries:
                    time.sleep(0.5 * attempt)

            except Exception as exc:
                last_error = str(exc)
                error_str = str(exc).lower()

                # Check for rate limiting.
                if "429" in error_str or "resource_exhausted" in error_str:
                    wait = min(2 ** attempt, 30)
                    logger.warning(
                        "GEMINI_RATE_LIMITED | attempt=%d/%d | wait=%ds",
                        attempt, max_retries, wait,
                    )
                    time.sleep(wait)
                    continue

                # Check for transient errors.
                if any(t in error_str for t in ("503", "500", "timeout", "unavailable")):
                    wait = min(2 ** attempt, 30)
                    logger.warning(
                        "GEMINI_TRANSIENT_ERROR | attempt=%d/%d | wait=%ds | error=%s",
                        attempt, max_retries, wait, str(exc),
                    )
                    time.sleep(wait)
                    continue

                # Non-retryable error.
                logger.error(
                    "GEMINI_ERROR | attempt=%d/%d | error=%s",
                    attempt, max_retries, str(exc),
                )
                break

        # All retries exhausted.
        latency_ms = (time.time() - start_time) * 1000
        logger.error(
            "EXTRACTION_FAILED | retries_exhausted | last_error=%s",
            last_error,
        )
        return ExtractionResult(
            analysis=None,
            error=last_error,
            processing_status="extraction_failed",
            model_used=self._model,
            latency_ms=round(latency_ms, 1),
        )

    def _call_gemini(self, user_prompt: str) -> str:
        """Make a single Gemini API call.

        Uses low temperature for deterministic extraction.
        """
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

        return response.text or ""

    def _parse_response(self, raw_text: str) -> EmailAnalysis:
        """Parse Gemini's response text into a validated EmailAnalysis.

        Handles:
          • Raw JSON
          • JSON wrapped in markdown code fences
          • Minor formatting issues
        """
        cleaned = raw_text.strip()

        # Strip markdown code fences if present.
        if cleaned.startswith("```"):
            # Remove ```json and ``` wrappers.
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```\s*$", "", cleaned)

        data = json.loads(cleaned)

        # Validate through Pydantic.
        return EmailAnalysis.model_validate(data)


def is_gemini_configured() -> bool:
    """Check if Gemini API key is configured."""
    settings = get_settings()
    return bool(settings.GEMINI_API_KEY)
