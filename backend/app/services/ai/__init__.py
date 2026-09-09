"""CareerMail AI — Multi-Provider AI Services Package."""

from app.services.ai.base import (
    AIAuthError,
    AIConfigurationError,
    AIProviderError,
    AIRateLimitError,
    AISchemaError,
    AITimeoutError,
    AITransientError,
    BaseAIProvider,
    clean_json_text,
    parse_and_validate_analysis,
)
from app.services.ai.gemini import GeminiClient, is_gemini_configured
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.groq_provider import GroqProvider
from app.services.ai.huggingface_provider import HuggingFaceProvider
from app.services.ai.openrouter_provider import OpenRouterProvider
from app.services.ai.orchestrator import AIOrchestrator, get_ai_orchestrator

__all__ = [
    "AIAuthError",
    "AIConfigurationError",
    "AIProviderError",
    "AIRateLimitError",
    "AISchemaError",
    "AITimeoutError",
    "AITransientError",
    "BaseAIProvider",
    "clean_json_text",
    "parse_and_validate_analysis",
    "GeminiClient",
    "is_gemini_configured",
    "GeminiProvider",
    "GroqProvider",
    "HuggingFaceProvider",
    "OpenRouterProvider",
    "AIOrchestrator",
    "get_ai_orchestrator",
]
