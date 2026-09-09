"""
CareerMail AI — Live AI Provider Connectivity Smoke Test.

Executes a live test extraction against each configured AI provider (Gemini, Groq,
OpenRouter, Hugging Face) using your local backend/.env configuration.

Validates:
  1. API key authentication
  2. Model catalog availability / reachability
  3. Real JSON inference & Pydantic EmailAnalysis schema validation
  4. Precise error classification (Auth vs Configuration vs Rate Limit vs Transient)

Usage:
  cd backend
  python scripts/smoke_test_providers.py
"""

import sys
import time
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.config import get_settings
from app.services.ai.base import (
    AIAuthError,
    AIConfigurationError,
    AIRateLimitError,
    AISchemaError,
    AITimeoutError,
    AITransientError,
)
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.groq_provider import GroqProvider
from app.services.ai.huggingface_provider import HuggingFaceProvider
from app.services.ai.openrouter_provider import OpenRouterProvider

SAMPLE_EMAIL = {
    "sender": "organizer@hackindia2026.org",
    "subject": "HackIndia 2026 -- Team Registration Confirmed",
    "received_at": "2026-09-08T12:00:00Z",
    "body_text": (
        "Congratulations! Your team registration for HackIndia 2026 has been confirmed. "
        "The preliminary prototype submission deadline is October 15, 2026. "
        "Round 2 shortlisted teams will be announced on November 1, 2026. "
        "Visit https://hackindia2026.org for rules and guidelines."
    ),
}


def test_provider(provider) -> dict:
    """Run a single test extraction against a provider and return structured diagnostics."""
    start_time = time.time()
    try:
        result = provider.extract_email_data(
            sender=SAMPLE_EMAIL["sender"],
            subject=SAMPLE_EMAIL["subject"],
            received_at=SAMPLE_EMAIL["received_at"],
            body_text=SAMPLE_EMAIL["body_text"],
        )
        latency_ms = round((time.time() - start_time) * 1000, 1)

        title = result.analysis.title if result.analysis else "N/A"
        category = result.analysis.category.value if result.analysis else "N/A"
        status = result.analysis.status.value if result.analysis else "N/A"

        return {
            "status": "PASS",
            "latency_ms": latency_ms,
            "category": category,
            "opp_status": status,
            "title": title,
            "model_used": result.model_used,
            "error_type": None,
            "error_msg": None,
        }

    except AIRateLimitError as exc:
        return {
            "status": "FAIL",
            "error_type": "AIRateLimitError (429 Rate Limit)",
            "error_msg": exc.message,
        }
    except AIAuthError as exc:
        return {
            "status": "FAIL",
            "error_type": "AIAuthError (Invalid API Key / Unauthorized)",
            "error_msg": exc.message,
        }
    except AIConfigurationError as exc:
        return {
            "status": "FAIL",
            "error_type": "AIConfigurationError (Model Permission / Not Found / Gated)",
            "error_msg": exc.message,
        }
    except AITransientError as exc:
        return {
            "status": "FAIL",
            "error_type": "AITransientError (5xx Server / Network Failure)",
            "error_msg": exc.message,
        }
    except AITimeoutError as exc:
        return {
            "status": "FAIL",
            "error_type": "AITimeoutError (Request Timeout)",
            "error_msg": exc.message,
        }
    except AISchemaError as exc:
        return {
            "status": "FAIL",
            "error_type": "AISchemaError (Malformed JSON / Validation Error)",
            "error_msg": exc.message,
        }
    except Exception as exc:
        return {
            "status": "FAIL",
            "error_type": f"Unexpected ({type(exc).__name__})",
            "error_msg": str(exc),
        }


def main():
    print("=" * 70)
    print("CareerMail AI -- Live AI Provider Smoke Test")
    print("=" * 70)

    settings = get_settings()

    providers = [
        ("gemini", GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)),
        ("groq", GroqProvider(api_key=settings.GROQ_API_KEY, model=settings.GROQ_MODEL)),
        ("openrouter", OpenRouterProvider(api_key=settings.OPENROUTER_API_KEY, model=settings.OPENROUTER_MODEL)),
        ("huggingface", HuggingFaceProvider(api_key=settings.HUGGINGFACE_API_KEY, model=settings.HUGGINGFACE_MODEL)),
    ]

    configured_count = 0
    results = {}

    for name, provider in providers:
        print(f"\n[Provider: {name.upper()}]")
        print(f"  Configured Model : {provider.model_name}")

        if not provider.is_configured():
            print("  Status           : [SKIPPED] (No API key found in .env)")
            results[name] = {"status": "SKIPPED", "reason": "No API key configured"}
            continue

        configured_count += 1
        print("  Status           : Testing live inference request...")

        res = test_provider(provider)
        results[name] = res

        if res["status"] == "PASS":
            print(f"  Result           : [PASS] ({res['latency_ms']}ms)")
            print(f"  Extracted Title  : {res['title']}")
            print(f"  Category / Status: {res['category']} | {res['opp_status']}")
        else:
            print(f"  Result           : [FAIL]")
            print(f"  Classification   : {res['error_type']}")
            print(f"  Reason           : {res['error_msg']}")

    print("\n" + "=" * 70)
    print("SMOKE TEST SUMMARY")
    print("=" * 70)
    print(f"AI_PRIMARY_PROVIDER   : {settings.AI_PRIMARY_PROVIDER}")
    print(f"AI_FALLBACK_PROVIDERS : {settings.AI_FALLBACK_PROVIDERS}")
    print("-" * 70)

    for name, res in results.items():
        st = res["status"]
        if st == "PASS":
            print(f"  {name.upper():<14} : [PASS]  ({res['latency_ms']}ms via {res['model_used']})")
        elif st == "SKIPPED":
            print(f"  {name.upper():<14} : [SKIPPED] (Unconfigured)")
        else:
            print(f"  {name.upper():<14} : [FAIL]  ({res['error_type']})")

    print("=" * 70)

    if configured_count == 0:
        print("\nNotice: No AI providers had API keys configured in backend/.env.")
        print("Copy backend/.env.example to backend/.env and add at least one real key to test.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
