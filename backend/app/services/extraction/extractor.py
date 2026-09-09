"""
CareerMail AI — Email Extraction Orchestrator.

Coordinates the full extraction pipeline:
  1. Relevance filtering (cheap keyword check)
  2. Multi-provider AI extraction (Gemini -> Groq -> OpenRouter -> Hugging Face)
  3. Result storage, opportunity management, and state progression

Maintains backward compatibility with GeminiClient injection for existing tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.email_message import EmailMessage
from app.schemas.extraction import EmailAnalysis, ExtractionResult
from app.services.ai.gemini import GeminiClient, is_gemini_configured
from app.services.ai.orchestrator import AIOrchestrator, get_ai_orchestrator
from app.services.extraction.filter import FilterResult, check_relevance
from app.services.opportunities.manager import create_or_update_opportunity
from app.utils.logging import get_logger, log_event

logger = get_logger("extraction.extractor")


def process_email(
    db: Session,
    email: EmailMessage,
    gemini_client: Optional[GeminiClient] = None,
    orchestrator: Optional[AIOrchestrator] = None,
) -> ExtractionResult:
    """Process a single email through the extraction pipeline.

    Steps:
        1. Check relevance via keyword filter.
        2. If relevant, extract structured career data via AIOrchestrator (or injected client).
        3. Update the email's processing_status.
        4. Link or advance corresponding Opportunity if extracted.
        5. Return the result (caller decides whether to commit).

    Args:
        db: Active database session.
        email: The EmailMessage to process.
        gemini_client: Optional pre-configured client (for backward-compatible tests).
        orchestrator: Optional AIOrchestrator (for testing custom provider chains).

    Returns:
        ExtractionResult with analysis or error.
    """
    # ── Step 1: Relevance filtering ──────────────────────
    filter_result = check_relevance(
        subject=email.subject,
        sender=email.sender,
        body_text=email.body_text,
    )

    if not filter_result.is_relevant:
        email.is_relevant = False
        email.processing_status = "filtered_out"

        log_event(
            logger,
            "EMAIL_FILTERED_OUT",
            email_id=email.id,
            subject_length=len(email.subject or ""),
        )

        return ExtractionResult(
            analysis=None,
            processing_status="filtered_out",
        )

    # Mark as relevant.
    email.is_relevant = True

    log_event(
        logger,
        "EMAIL_RELEVANT",
        email_id=email.id,
        category=filter_result.primary_category,
        score=f"{filter_result.score:.2f}",
        keywords=len(filter_result.matched_keywords),
    )

    # ── Step 2: AI extraction via Orchestrator or Client ──
    settings = get_settings()
    has_fallback_providers = (
        settings.groq_configured
        or settings.openrouter_configured
        or settings.huggingface_configured
    )
    is_available = is_gemini_configured() or has_fallback_providers

    received_at_str = (
        email.received_at.isoformat()
        if isinstance(email.received_at, datetime)
        else str(email.received_at)
    )

    if orchestrator is not None:
        result = orchestrator.extract_email_data(
            sender=email.sender,
            subject=email.subject,
            received_at=received_at_str,
            body_text=email.body_text or "",
        )
    elif gemini_client is not None:
        result = gemini_client.extract_email_data(
            sender=email.sender,
            subject=email.subject,
            received_at=received_at_str,
            body_text=email.body_text or "",
        )
    elif not is_available:
        email.processing_status = "pending_extraction"
        logger.info(
            "AI_NOT_CONFIGURED | email_id=%d | marking as pending_extraction",
            email.id,
        )
        return ExtractionResult(
            analysis=None,
            error="No AI providers configured",
            processing_status="pending_extraction",
        )
    else:
        active_orchestrator = get_ai_orchestrator()
        result = active_orchestrator.extract_email_data(
            sender=email.sender,
            subject=email.subject,
            received_at=received_at_str,
            body_text=email.body_text or "",
        )

    # ── Step 3: Update email state ───────────────────────
    email.processing_status = result.processing_status

    if result.analysis:
        log_event(
            logger,
            "EXTRACTION_COMPLETE",
            email_id=email.id,
            category=result.analysis.category.value,
            status=result.analysis.status.value,
            confidence=f"{result.analysis.confidence:.2f}",
            action_required=result.analysis.action_required,
        )

        # ── Step 4: Opportunity Management (Milestone 3) ────
        opp, was_created, status_changed = create_or_update_opportunity(
            db, email, result.analysis
        )
        result.opportunity_id = opp.id
    elif result.error:
        logger.warning(
            "EXTRACTION_INCOMPLETE | email_id=%d | error=%s",
            email.id,
            result.error,
        )

    return result


def process_pending_emails(
    db: Session,
    *,
    limit: int = 50,
    gemini_client: Optional[GeminiClient] = None,
    orchestrator: Optional[AIOrchestrator] = None,
) -> dict:
    """Process all emails with processing_status='pending'.

    Args:
        db: Active database session.
        limit: Max number of emails to process in one batch.
        gemini_client: Optional pre-configured client (backward compatibility).
        orchestrator: Optional custom orchestrator.

    Returns:
        Summary dict with counts.
    """
    pending_emails = (
        db.query(EmailMessage)
        .filter(EmailMessage.processing_status == "pending")
        .order_by(EmailMessage.received_at.desc())
        .limit(limit)
        .all()
    )

    summary = {
        "total": len(pending_emails),
        "filtered_out": 0,
        "extracted": 0,
        "pending_extraction": 0,
        "extraction_failed": 0,
    }

    for email in pending_emails:
        try:
            result = process_email(
                db,
                email,
                gemini_client=gemini_client,
                orchestrator=orchestrator,
            )
            status_key = result.processing_status
            if status_key in summary:
                summary[status_key] += 1
        except Exception as exc:
            logger.error(
                "PROCESS_EMAIL_ERROR | email_id=%d | error=%s",
                email.id,
                str(exc),
            )
            email.processing_status = "extraction_failed"
            summary["extraction_failed"] += 1

    db.commit()

    log_event(logger, "BATCH_PROCESSING_COMPLETE", **summary)
    return summary
