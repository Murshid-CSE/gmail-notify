"""
CareerMail AI — AI Orchestrator & Fallback Chain.

Coordinates resilient multi-provider AI extraction across Gemini, Groq, OpenRouter, and Hugging Face.
Implements:
  • Configurable, data-driven provider chain ordering (AI_PRIMARY_PROVIDER, AI_FALLBACK_PROVIDERS)
  • Immediate failover on 429 rate limits
  • 1x bounded backoff retry on transient 5xx, timeouts, and schema errors before failover
  • Temporary disablement of providers failing with 401/403 authentication errors for the lifecycle
  • Accurate categorization of auth failures vs configuration/model access errors
  • Safe in-memory metrics without exposing secrets
  • Graceful aggregate extraction failure without crashing Gmail sync
"""

from __future__ import annotations

import time
from typing import Optional

from app.config import get_settings
from app.schemas.composer import EmailDraft
from app.schemas.extraction import ExtractionResult
from app.services.ai.base import (
    AIAuthError,
    AIConfigurationError,
    AIProviderError,
    AIRateLimitError,
    AISchemaError,
    AITimeoutError,
    AITransientError,
    BaseAIProvider,
)
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.groq_provider import GroqProvider
from app.services.ai.huggingface_provider import HuggingFaceProvider
from app.services.ai.openrouter_provider import OpenRouterProvider
from app.utils.logging import get_logger, log_event

logger = get_logger("ai.orchestrator")


class AIOrchestrator:
    """Orchestrates AI extraction across a prioritized, configurable provider fallback chain."""

    def __init__(self, providers: Optional[list[BaseAIProvider]] = None):
        """Initialize the orchestrator.

        Args:
            providers: Explicit list of providers (ideal for unit tests).
                       If None, providers are initialized dynamically from settings.
        """
        if providers is not None:
            self._providers = list(providers)
        else:
            self._providers = self._build_providers_from_settings()

        # In-memory lifecycle & health state
        self._disabled_providers: set[str] = set()
        self._provider_health: dict[str, str] = {p.name: "healthy" for p in self._providers}
        self._last_provider_used: Optional[str] = None

        # Lightweight in-memory metrics
        self._requests_total: dict[str, int] = {p.name: 0 for p in self._providers}
        self._requests_success: dict[str, int] = {p.name: 0 for p in self._providers}
        self._requests_failed: dict[str, int] = {p.name: 0 for p in self._providers}
        self._fallbacks_count: int = 0

    @classmethod
    def _build_providers_from_settings(cls) -> list[BaseAIProvider]:
        """Construct the ordered list of configured AI providers from application settings."""
        settings = get_settings()

        registry: dict[str, BaseAIProvider] = {
            "gemini": GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL),
            "groq": GroqProvider(api_key=settings.GROQ_API_KEY, model=settings.GROQ_MODEL),
            "openrouter": OpenRouterProvider(api_key=settings.OPENROUTER_API_KEY, model=settings.OPENROUTER_MODEL),
            "huggingface": HuggingFaceProvider(api_key=settings.HUGGINGFACE_API_KEY, model=settings.HUGGINGFACE_MODEL),
        }

        chain_names: list[str] = []
        if settings.AI_PRIMARY_PROVIDER:
            p = settings.AI_PRIMARY_PROVIDER.strip().lower()
            if p and p not in chain_names:
                chain_names.append(p)

        if settings.AI_FALLBACK_PROVIDERS:
            for item in settings.AI_FALLBACK_PROVIDERS.split(","):
                p = item.strip().lower()
                if p and p not in chain_names:
                    chain_names.append(p)

        ordered_providers: list[BaseAIProvider] = []
        for name in chain_names:
            provider = registry.get(name)
            if provider and provider.is_configured():
                ordered_providers.append(provider)

        return ordered_providers

    @property
    def configured_providers(self) -> list[str]:
        """Names of all configured providers in configured priority order."""
        return [p.name for p in self._providers]

    @property
    def active_providers(self) -> list[str]:
        """Configured providers not currently disabled."""
        return [p.name for p in self._providers if p.name not in self._disabled_providers]

    def reset_state(self) -> None:
        """Reset internal metrics, provider health, and disabled states."""
        self._disabled_providers.clear()
        self._provider_health = {p.name: "healthy" for p in self._providers}
        self._last_provider_used = None
        self._requests_total = {p.name: 0 for p in self._providers}
        self._requests_success = {p.name: 0 for p in self._providers}
        self._requests_failed = {p.name: 0 for p in self._providers}
        self._fallbacks_count = 0

    def get_metrics(self) -> dict:
        """Return safe, sanitized in-memory metrics without credentials or tokens."""
        return {
            "requests_total": dict(self._requests_total),
            "requests_success": dict(self._requests_success),
            "requests_failed": dict(self._requests_failed),
            "fallbacks_count": self._fallbacks_count,
            "last_provider_used": self._last_provider_used,
            "provider_health": dict(self._provider_health),
            "disabled_providers": list(self._disabled_providers),
            "configured_providers": self.configured_providers,
        }

    def extract_email_data(
        self,
        sender: str,
        subject: str,
        received_at: str,
        body_text: str,
    ) -> ExtractionResult:
        """Process email extraction through the provider fallback chain.

        Returns:
            ExtractionResult with validated analysis or graceful failure details.
        """
        active_chain = [p for p in self._providers if p.name not in self._disabled_providers]

        if not active_chain:
            logger.warning("NO_AI_PROVIDERS_AVAILABLE | all unconfigured or disabled")
            return ExtractionResult(
                analysis=None,
                error="No active AI providers available",
                processing_status="pending_extraction",
            )

        errors_encountered: list[str] = []

        for idx, provider in enumerate(active_chain):
            p_name = provider.name
            self._requests_total[p_name] = self._requests_total.get(p_name, 0) + 1

            try:
                # Attempt extraction with single bounded retry for retryable failures
                result = self._execute_with_retry(
                    provider=provider,
                    sender=sender,
                    subject=subject,
                    received_at=received_at,
                    body_text=body_text,
                )

                # Successful extraction
                self._requests_success[p_name] = self._requests_success.get(p_name, 0) + 1
                self._provider_health[p_name] = "healthy"
                self._last_provider_used = p_name

                log_event(
                    logger,
                    "AI_EXTRACTION_SUCCESS",
                    provider=p_name,
                    model=provider.model_name,
                    fallback_level=idx,
                    category=result.analysis.category.value if result.analysis else "unknown",
                )
                return result

            except AIRateLimitError as exc:
                self._requests_failed[p_name] = self._requests_failed.get(p_name, 0) + 1
                self._provider_health[p_name] = "rate_limited"
                self._fallbacks_count += 1
                errors_encountered.append(f"{p_name}: 429 rate limit exceeded")
                logger.warning("PROVIDER_RATE_LIMITED | provider=%s | failing over", p_name)
                continue

            except AIAuthError as exc:
                self._requests_failed[p_name] = self._requests_failed.get(p_name, 0) + 1
                self._provider_health[p_name] = "auth_error"
                # Temporarily disable provider for the lifecycle to prevent repeated bad auth calls
                self._disabled_providers.add(p_name)
                self._fallbacks_count += 1
                errors_encountered.append(f"{p_name}: authentication failed")
                logger.warning("PROVIDER_AUTH_ERROR | provider=%s temporarily disabled for lifecycle", p_name)
                continue

            except AIConfigurationError as exc:
                self._requests_failed[p_name] = self._requests_failed.get(p_name, 0) + 1
                self._provider_health[p_name] = "configuration_error"
                self._fallbacks_count += 1
                errors_encountered.append(f"{p_name}: configuration error ({exc.message})")
                logger.warning("PROVIDER_CONFIG_ERROR | provider=%s | error=%s", p_name, exc.message)
                continue

            except (AITransientError, AITimeoutError, AISchemaError, AIProviderError) as exc:
                self._requests_failed[p_name] = self._requests_failed.get(p_name, 0) + 1
                self._provider_health[p_name] = "transient_error"
                self._fallbacks_count += 1
                errors_encountered.append(f"{p_name}: {type(exc).__name__} ({exc.message})")
                logger.warning("PROVIDER_FAILED | provider=%s | error=%s | failing over", p_name, type(exc).__name__)
                continue

            except Exception as exc:
                self._requests_failed[p_name] = self._requests_failed.get(p_name, 0) + 1
                self._provider_health[p_name] = "unexpected_error"
                self._fallbacks_count += 1
                errors_encountered.append(f"{p_name}: unexpected error ({type(exc).__name__})")
                logger.error("PROVIDER_UNEXPECTED_ERROR | provider=%s | error=%s", p_name, type(exc).__name__)
                continue

        # All configured providers exhausted without crashing
        aggregate_error = "; ".join(errors_encountered) or "All providers failed"
        logger.error("ALL_PROVIDERS_FAILED | errors=%s", aggregate_error)

        return ExtractionResult(
            analysis=None,
            error=aggregate_error,
            processing_status="extraction_failed",
            model_used=self._last_provider_used or "none",
        )

    def _execute_with_retry(
        self,
        provider: BaseAIProvider,
        sender: str,
        subject: str,
        received_at: str,
        body_text: str,
    ) -> ExtractionResult:
        """Execute extraction on a provider with at most 1 bounded retry for retryable errors.

        Non-retryable errors (e.g. AIRateLimitError, AIAuthError, AIConfigurationError)
        raise immediately to trigger immediate failover.
        """
        try:
            return provider.extract_email_data(sender, subject, received_at, body_text)
        except (AITransientError, AITimeoutError, AISchemaError) as first_exc:
            logger.info(
                "PROVIDER_RETRYING | provider=%s | reason=%s | waiting 0.3s",
                provider.name,
                type(first_exc).__name__,
            )
            time.sleep(0.3)
            # Retry once
            return provider.extract_email_data(sender, subject, received_at, body_text)

    def generate_email_draft(
        self,
        opportunity_context: dict,
        instruction: str,
    ) -> EmailDraft:
        """Generate a context-aware email draft using the prioritized provider fallback chain.

        Returns:
            Validated EmailDraft instance.
        """
        active_chain = [p for p in self._providers if p.name not in self._disabled_providers]

        if not active_chain:
            logger.warning("NO_AI_PROVIDERS_AVAILABLE | cannot draft email")
            raise AIConfigurationError("No active AI providers available to draft email")

        errors_encountered: list[str] = []

        for idx, provider in enumerate(active_chain):
            p_name = provider.name
            self._requests_total[p_name] = self._requests_total.get(p_name, 0) + 1

            try:
                draft = self._execute_draft_with_retry(
                    provider=provider,
                    opportunity_context=opportunity_context,
                    instruction=instruction,
                )

                self._requests_success[p_name] = self._requests_success.get(p_name, 0) + 1
                self._provider_health[p_name] = "healthy"
                self._last_provider_used = p_name

                log_event(
                    logger,
                    "AI_DRAFT_SUCCESS",
                    provider=p_name,
                    model=provider.model_name,
                    fallback_level=idx,
                    subject=draft.subject,
                )
                return draft

            except AIRateLimitError:
                self._requests_failed[p_name] = self._requests_failed.get(p_name, 0) + 1
                self._provider_health[p_name] = "rate_limited"
                self._fallbacks_count += 1
                errors_encountered.append(f"{p_name}: 429 rate limit exceeded")
                logger.warning("DRAFT_PROVIDER_RATE_LIMITED | provider=%s | failing over", p_name)
                continue

            except AIAuthError:
                self._requests_failed[p_name] = self._requests_failed.get(p_name, 0) + 1
                self._provider_health[p_name] = "auth_error"
                self._disabled_providers.add(p_name)
                self._fallbacks_count += 1
                errors_encountered.append(f"{p_name}: authentication failed")
                logger.warning("DRAFT_PROVIDER_AUTH_ERROR | provider=%s temporarily disabled", p_name)
                continue

            except AIConfigurationError as exc:
                self._requests_failed[p_name] = self._requests_failed.get(p_name, 0) + 1
                self._provider_health[p_name] = "config_error"
                self._fallbacks_count += 1
                errors_encountered.append(f"{p_name}: {exc.message}")
                logger.warning("DRAFT_PROVIDER_CONFIG_ERROR | provider=%s | failing over", p_name)
                continue

            except (AITransientError, AITimeoutError, AISchemaError) as exc:
                self._requests_failed[p_name] = self._requests_failed.get(p_name, 0) + 1
                self._provider_health[p_name] = "degraded"
                self._fallbacks_count += 1
                errors_encountered.append(f"{p_name}: {exc.message}")
                logger.warning("DRAFT_PROVIDER_FAILED | provider=%s | failing over", p_name)
                continue

            except Exception as exc:
                self._requests_failed[p_name] = self._requests_failed.get(p_name, 0) + 1
                self._fallbacks_count += 1
                errors_encountered.append(f"{p_name}: unexpected error {exc}")
                logger.error("DRAFT_PROVIDER_UNEXPECTED | provider=%s | error=%s", p_name, exc)
                continue

        aggregate_error = "; ".join(errors_encountered)
        logger.error("ALL_AI_PROVIDERS_FAILED_DRAFT | errors=%s", aggregate_error)
        raise AIProviderError(f"Failed to generate email draft: {aggregate_error}")

    def _execute_draft_with_retry(
        self,
        provider: BaseAIProvider,
        opportunity_context: dict,
        instruction: str,
    ) -> EmailDraft:
        """Execute draft generation on provider with 1 bounded retry for retryable errors."""
        try:
            return provider.generate_email_draft(opportunity_context, instruction)
        except (AITransientError, AITimeoutError, AISchemaError) as first_exc:
            logger.info(
                "DRAFT_PROVIDER_RETRYING | provider=%s | reason=%s | waiting 0.3s",
                provider.name,
                type(first_exc).__name__,
            )
            time.sleep(0.3)
            return provider.generate_email_draft(opportunity_context, instruction)



# Module-level instance with reset capability for tests
_orchestrator_instance: Optional[AIOrchestrator] = None


def get_ai_orchestrator(reset: bool = False) -> AIOrchestrator:
    """Return the central AIOrchestrator instance.

    Args:
        reset: If True, forces re-initialization of the orchestrator from current settings.
    """
    global _orchestrator_instance
    if _orchestrator_instance is None or reset:
        _orchestrator_instance = AIOrchestrator()
    return _orchestrator_instance
