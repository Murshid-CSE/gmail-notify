"""
CareerMail AI — Email Composer API Routes.

Endpoints:
  POST /email-composer/draft       — Generate context-aware email draft using AI.
  POST /email-composer/gmail-draft — Save draft to connected Gmail account.
  POST /email-composer/send        — Explicitly send email via connected Gmail account.

Enforces:
  • Anti-hallucination recipient verification (only trusted source sender or explicit user input).
  • Explicit confirmation before sending (never autonomous).
  • Thread preservation headers (In-Reply-To, References, threadId).
  • Re-authorization error detection (HTTP 403 with error_code='reauth_required').
  • Opportunity activity timeline updates on send.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.email_account import EmailAccount
from app.models.opportunity import Opportunity
from app.models.status_history import OpportunityStatusHistory
from app.schemas.composer import (
    EmailDraft,
    EmailDraftGenerateRequest,
    EmailSendRequest,
    EmailSendResponse,
    GmailDraftCreateRequest,
    GmailDraftResponse,
)
from app.services.ai.base import AIProviderError
from app.services.ai.orchestrator import get_ai_orchestrator
from app.services.gmail.auth import OAuthScopeError, build_credentials_from_encrypted
from app.services.gmail.composer import create_gmail_draft, send_gmail_message
from app.utils.logging import get_logger, log_event

logger = get_logger("api.email_composer")

router = APIRouter(prefix="/email-composer", tags=["email-composer"])


def _extract_email_address(text: str) -> Optional[str]:
    """Extract clean email address from a header string like 'Name <email@example.com>'."""
    if not text:
        return None
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    if match:
        return match.group(0).lower()
    return None


@router.post("/draft", response_model=EmailDraft)
def generate_draft(
    req: EmailDraftGenerateRequest,
    db: Session = Depends(get_db),
):
    """Generate a context-aware email draft using AI orchestrator."""
    opp = (
        db.query(Opportunity)
        .options(joinedload(Opportunity.emails))
        .filter(Opportunity.id == req.opportunity_id)
        .first()
    )
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    # Extract source email context if linked
    source_email = opp.emails[-1] if opp.emails else None
    source_sender = source_email.sender if source_email else ""
    source_subject = source_email.subject if source_email else ""
    source_body = source_email.body_text if source_email else (opp.description or "")
    in_reply_to = source_email.gmail_message_id if source_email else None
    thread_id = source_email.gmail_thread_id if source_email else None

    # Suggested account preference: requested -> opp source -> source email account
    suggested_account_id = req.account_id or opp.source_account_id
    if not suggested_account_id and source_email:
        suggested_account_id = source_email.account_id

    trusted_recipient = _extract_email_address(source_sender)

    context = {
        "title": opp.title,
        "organization": opp.organization,
        "category": opp.category,
        "status": opp.status,
        "deadline": opp.deadline.isoformat() if opp.deadline else None,
        "source_sender": source_sender,
        "source_subject": source_subject,
        "source_body": source_body,
    }

    orchestrator = get_ai_orchestrator()
    try:
        draft = orchestrator.generate_email_draft(context, req.instruction)
    except AIProviderError as exc:
        logger.error("DRAFT_GENERATION_FAILED | %s", exc)
        raise HTTPException(status_code=502, detail=f"AI generation failed: {exc}")

    # Strict anti-hallucination recipient safety:
    # Only trusted recipient from source email is permitted. Never allow invented addresses.
    if trusted_recipient:
        draft.to = [trusted_recipient]
    else:
        draft.to = []

    draft.in_reply_to = in_reply_to
    draft.thread_id = thread_id
    draft.suggested_account_id = suggested_account_id

    log_event(logger, "DRAFT_GENERATED", opportunity_id=opp.id, recipient_count=len(draft.to))
    return draft


@router.post("/gmail-draft", response_model=GmailDraftResponse)
def save_gmail_draft(
    req: GmailDraftCreateRequest,
    db: Session = Depends(get_db),
):
    """Save an email draft to the connected user's Gmail account."""
    account = db.query(EmailAccount).filter(EmailAccount.id == req.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")

    try:
        credentials = build_credentials_from_encrypted(
            account.encrypted_access_token,
            account.encrypted_refresh_token,
            account.token_expiry,
        )
        result = create_gmail_draft(

            credentials=credentials,
            sender_email=account.email_address,
            to=req.draft.to,
            subject=req.draft.subject,
            body_text=req.draft.body_text,
            cc=req.draft.cc,
            bcc=req.draft.bcc,
            thread_id=req.draft.thread_id,
            in_reply_to=req.draft.in_reply_to,
            account_id=account.id,
        )
        return GmailDraftResponse(
            draft_id=result["draft_id"],
            message_id=result["message_id"],
            account_id=account.id,
            subject=req.draft.subject,
        )
    except OAuthScopeError as exc:
        logger.warning("GMAIL_DRAFT_SCOPE_ERROR | account_id=%d | %s", account.id, exc)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "This account requires additional permissions to create drafts in Gmail. Please re-authorize.",
                "error_code": "reauth_required",
                "account_id": account.id,
            },
        )
    except Exception as exc:
        logger.error("GMAIL_DRAFT_FAILED | %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to create Gmail draft: {exc}")


@router.post("/send", response_model=EmailSendResponse)
def send_email(
    req: EmailSendRequest,
    db: Session = Depends(get_db),
):
    """Explicitly send an email via the user's Gmail account."""
    if not req.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit confirmation (confirmed=True) is required to send emails.",
        )

    if not req.to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one recipient email address is required.",
        )

    account = db.query(EmailAccount).filter(EmailAccount.id == req.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")

    opp = db.query(Opportunity).filter(Opportunity.id == req.opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    try:
        credentials = build_credentials_from_encrypted(
            account.encrypted_access_token,
            account.encrypted_refresh_token,
            account.token_expiry,
        )
        result = send_gmail_message(

            credentials=credentials,
            sender_email=account.email_address,
            to=req.to,
            subject=req.subject,
            body_text=req.body_text,
            cc=req.cc,
            bcc=req.bcc,
            thread_id=req.thread_id,
            in_reply_to=req.in_reply_to,
            account_id=account.id,
        )

        # Record activity entry in Opportunity timeline
        history_entry = OpportunityStatusHistory(
            opportunity_id=opp.id,
            old_status=opp.status,
            new_status="EMAIL_SENT",
            changed_at=datetime.now(timezone.utc),
        )
        db.add(history_entry)
        opp.last_updated_at = datetime.now(timezone.utc)
        db.commit()

        log_event(
            logger,
            "EMAIL_SENT_LOGGED",
            opportunity_id=opp.id,
            account_id=account.id,
            message_id=result["message_id"],
        )

        return EmailSendResponse(
            message_id=result["message_id"],
            thread_id=result.get("thread_id"),
            sent_at=result["sent_at"],
            account_id=account.id,
            to=req.to,
            subject=req.subject,
        )

    except OAuthScopeError as exc:
        logger.warning("GMAIL_SEND_SCOPE_ERROR | account_id=%d | %s", account.id, exc)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "This account requires additional permissions to send emails via Gmail. Please re-authorize.",
                "error_code": "reauth_required",
                "account_id": account.id,
            },
        )
    except Exception as exc:
        logger.error("GMAIL_SEND_FAILED | %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}")
