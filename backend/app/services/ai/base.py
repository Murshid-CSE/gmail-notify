"""
CareerMail AI — Base AI Provider Specification & Unified Exceptions.

Defines the abstract interface all AI providers (Gemini, Groq, OpenRouter, Hugging Face)
must implement, alongside standardized exception classifications for resilient failover.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import re
from typing import Optional

from app.schemas.extraction import EmailAnalysis, ExtractionResult
from app.schemas.composer import EmailDraft


# ── Standardized AI Exceptions ────────────────────────────────


class AIProviderError(Exception):
    """Base exception for all AI provider errors."""

    def __init__(self, message: str, provider: str = "", status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code


class AIRateLimitError(AIProviderError):
    """429 / Quota / Rate limit exceeded — triggers immediate failover to next provider."""
    pass


class AITransientError(AIProviderError):
    """5xx / Service Unavailable / Connection reset — retry once with backoff, then failover."""
    pass


class AITimeoutError(AIProviderError):
    """Read/connect timeout — retry once with backoff, then failover."""
    pass


class AIAuthError(AIProviderError):
    """401/403 Invalid or missing credentials — authentication failure; temporarily disable provider for lifecycle."""
    pass


class AIConfigurationError(AIProviderError):
    """Model access, non-existent model, missing permissions, or invalid configuration."""
    pass


class AISchemaError(AIProviderError):
    """Invalid JSON or schema validation failure — retry once where appropriate, then failover."""
    pass


# ── Response Parser & Normalizer ──────────────────────────────


def clean_json_text(raw_text: str) -> str:
    """Extract clean JSON string from raw model text output.

    Handles:
      • Standard raw JSON
      • Markdown code fences (```json ... ``` or ``` ... ```)
      • Embedded JSON with conversational preambles/postambles
      • Leading/trailing whitespace
    """
    cleaned = (raw_text or "").strip()
    if not cleaned:
        return ""

    # Match markdown code fences (```json ... ``` or ``` ... ```)
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # If starts with '{' and ends with '}'
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    # Attempt to extract outermost JSON object between first { and last }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return cleaned[first_brace : last_brace + 1].strip()

    return cleaned


def parse_and_validate_analysis(raw_text: str, provider_name: str = "") -> EmailAnalysis:
    """Parse JSON and validate against EmailAnalysis schema.

    Raises:
        AISchemaError: If text is empty, invalid JSON, or fails Pydantic validation.
    """
    cleaned = clean_json_text(raw_text)
    if not cleaned:
        raise AISchemaError("Empty response received from provider", provider=provider_name)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AISchemaError(f"Invalid JSON response: {exc}", provider=provider_name) from exc

    if not isinstance(data, dict):
        raise AISchemaError(
            f"Expected JSON object, got {type(data).__name__}",
            provider=provider_name,
        )

    try:
        return EmailAnalysis.model_validate(data)
    except Exception as exc:
        raise AISchemaError(f"Schema validation error: {exc}", provider=provider_name) from exc


def parse_and_validate_draft(raw_text: str, provider_name: str = "") -> EmailDraft:
    """Parse JSON and validate against EmailDraft schema.

    Raises:
        AISchemaError: If text is empty, invalid JSON, or fails Pydantic validation.
    """
    cleaned = clean_json_text(raw_text)
    if not cleaned:
        raise AISchemaError("Empty response received from provider", provider=provider_name)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AISchemaError(f"Invalid JSON response: {exc}", provider=provider_name) from exc

    if not isinstance(data, dict):
        raise AISchemaError(
            f"Expected JSON object, got {type(data).__name__}",
            provider=provider_name,
        )

    # Normalize 'to', 'cc', 'bcc' if strings were returned
    for key in ("to", "cc", "bcc"):
        if key in data and isinstance(data[key], str):
            val = data[key].strip()
            data[key] = [val] if val else []

    try:
        return EmailDraft.model_validate(data)
    except Exception as exc:
        raise AISchemaError(f"Email draft schema validation error: {exc}", provider=provider_name) from exc


# ── Base Provider Interface ───────────────────────────────────


class BaseAIProvider(ABC):
    """Abstract Base Class for all AI extraction providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'gemini', 'groq', 'openrouter', 'huggingface')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Active model identifier."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider has credentials configured."""
        pass

    @abstractmethod
    def extract_email_data(
        self,
        sender: str,
        subject: str,
        received_at: str,
        body_text: str,
    ) -> ExtractionResult:
        """Extract structured career data from an email.

        Must return an ExtractionResult with analysis or raise a standardized AIProviderError.
        """
        pass

    def generate_email_draft(
        self,
        opportunity_context: dict,
        instruction: str,
    ) -> EmailDraft:
        """Generate an email draft based on opportunity context and user instruction.

        Subclasses implement this using their respective LLM endpoints.
        """
        raise NotImplementedError(f"generate_email_draft not implemented for provider {self.name}")

