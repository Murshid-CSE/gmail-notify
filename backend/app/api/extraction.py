"""
CareerMail AI — Extraction API Routes.

POST /extraction/process   — Process pending emails through the pipeline.
GET  /extraction/status     — Check extraction pipeline status and multi-provider AI telemetry.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.email_message import EmailMessage
from app.services.ai.gemini import is_gemini_configured
from app.services.ai.orchestrator import get_ai_orchestrator
from app.services.extraction.extractor import process_pending_emails
from app.utils.logging import get_logger

logger = get_logger("api.extraction")

router = APIRouter(prefix="/extraction", tags=["extraction"])


@router.post("/process")
def trigger_extraction(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Process pending emails through the relevance + multi-provider AI extraction pipeline.

    - Emails are first filtered by keyword relevance.
    - Relevant emails are processed through the AIOrchestrator fallback chain.
    - If no AI providers are configured, emails are marked 'pending_extraction'.
    """
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit must be 1-200")

    summary = process_pending_emails(db, limit=limit)
    orchestrator = get_ai_orchestrator()
    metrics = orchestrator.get_metrics()

    return {
        "message": f"Processed {summary['total']} emails",
        "gemini_configured": is_gemini_configured(),
        "active_provider": metrics.get("last_provider_used") or (orchestrator.configured_providers[0] if orchestrator.configured_providers else None),
        "configured_providers": orchestrator.configured_providers,
        **summary,
    }


@router.get("/status")
def extraction_status(db: Session = Depends(get_db)):
    """Get the current state of email processing across all statuses and AI provider health."""
    settings = get_settings()
    orchestrator = get_ai_orchestrator()
    metrics = orchestrator.get_metrics()

    statuses = ["pending", "filtered_out", "pending_extraction", "extracted", "extraction_failed"]
    counts = {}

    for status in statuses:
        count = (
            db.query(EmailMessage)
            .filter(EmailMessage.processing_status == status)
            .count()
        )
        counts[status] = count

    return {
        "gemini_configured": is_gemini_configured(),
        "ai_configured": settings.ai_configured,
        "active_provider": metrics.get("last_provider_used") or (orchestrator.configured_providers[0] if orchestrator.configured_providers else None),
        "configured_providers": orchestrator.configured_providers,
        "provider_health": metrics.get("provider_health", {}),
        "metrics": {
            "requests_total": metrics.get("requests_total", {}),
            "requests_success": metrics.get("requests_success", {}),
            "requests_failed": metrics.get("requests_failed", {}),
            "fallbacks_count": metrics.get("fallbacks_count", 0),
        },
        "email_counts": counts,
        "total_emails": sum(counts.values()),
    }
