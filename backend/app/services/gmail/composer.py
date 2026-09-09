"""
CareerMail AI — Gmail Compose & Send Engine.

Handles:
  • MIME message creation using Python email.message.EmailMessage
  • Thread preservation (In-Reply-To, References, threadId)
  • Saving drafts in Gmail (users().drafts().create)
  • Explicit sending via Gmail (users().messages().send)
  • Detection and graceful mapping of 403 / insufficientPermissions to OAuthScopeError

Never logs raw email message bodies.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional, Any

from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from app.services.gmail.auth import OAuthScopeError, build_gmail_service
from app.utils.logging import get_logger, log_event

logger = get_logger("gmail.composer")


def create_mime_message(
    sender: str,
    to: list[str],
    subject: str,
    body_text: str,
    cc: Optional[list[str]] = None,
    bcc: Optional[list[str]] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
) -> str:
    """Construct a RFC 2822 MIME message and return as a URL-safe base64 string.

    Args:
        sender: From email address.
        to: List of recipient email addresses.
        subject: Subject line.
        body_text: Plain-text email body.
        cc: Optional list of CC addresses.
        bcc: Optional list of BCC addresses.
        in_reply_to: Optional Message-ID being replied to.
        references: Optional References header.

    Returns:
        Base64url-encoded message string suitable for the Gmail API.
    """
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject

    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)

    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = references if references else in_reply_to

    msg.set_content(body_text)

    # Gmail API requires base64url encoding without line wraps.
    raw_bytes = msg.as_bytes()
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")


def _handle_google_error(exc: Exception, account_id: Optional[int] = None) -> None:
    """Inspect Google API errors and raise OAuthScopeError if permissions are insufficient."""
    if isinstance(exc, HttpError):
        status = getattr(exc.resp, "status", None)
        content = str(exc).lower()
        if status in (401, 403) or "insufficient" in content or "scope" in content:
            log_event(logger, "GMAIL_SCOPE_INSUFFICIENT", account_id=account_id, status=status)
            raise OAuthScopeError(
                f"Gmail account requires re-authorization to compose or send emails. (HTTP {status})",
                account_id=account_id,
            ) from exc
    raise exc


def create_gmail_draft(
    credentials: Credentials,
    sender_email: str,
    to: list[str],
    subject: str,
    body_text: str,
    cc: Optional[list[str]] = None,
    bcc: Optional[list[str]] = None,
    thread_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    account_id: Optional[int] = None,
) -> dict[str, Any]:
    """Create a draft message in the user's Gmail mailbox.

    Args:
        credentials: Authenticated Google credentials.
        sender_email: Sender email address.
        to: List of recipient email addresses.
        subject: Subject line.
        body_text: Plain text content.
        cc: Optional CC addresses.
        bcc: Optional BCC addresses.
        thread_id: Optional Gmail threadId.
        in_reply_to: Optional Message-ID.
        account_id: Optional internal account ID.

    Returns:
        Dict with draft_id, message_id, account_id, and subject.
    """
    try:
        service = build_gmail_service(credentials)
        raw_msg = create_mime_message(
            sender=sender_email,
            to=to,
            subject=subject,
            body_text=body_text,
            cc=cc,
            bcc=bcc,
            in_reply_to=in_reply_to,
        )

        message_body: dict[str, Any] = {"raw": raw_msg}
        if thread_id:
            message_body["threadId"] = thread_id

        draft_body = {"message": message_body}
        res = service.users().drafts().create(userId="me", body=draft_body).execute()

        draft_id = res.get("id", "")
        message_id = res.get("message", {}).get("id", "")

        log_event(
            logger,
            "GMAIL_DRAFT_CREATED",
            account_id=account_id,
            draft_id=draft_id,
            recipient_count=len(to),
        )

        return {
            "draft_id": draft_id,
            "message_id": message_id,
            "account_id": account_id or 0,
            "subject": subject,
        }

    except Exception as exc:
        _handle_google_error(exc, account_id=account_id)
        raise


def send_gmail_message(
    credentials: Credentials,
    sender_email: str,
    to: list[str],
    subject: str,
    body_text: str,
    cc: Optional[list[str]] = None,
    bcc: Optional[list[str]] = None,
    thread_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    account_id: Optional[int] = None,
) -> dict[str, Any]:
    """Explicitly send an email message via Gmail API.

    Args:
        credentials: Authenticated Google credentials.
        sender_email: Sender email address.
        to: List of recipient email addresses.
        subject: Subject line.
        body_text: Plain text content.
        cc: Optional CC addresses.
        bcc: Optional BCC addresses.
        thread_id: Optional Gmail threadId.
        in_reply_to: Optional Message-ID.
        account_id: Optional internal account ID.

    Returns:
        Dict with message_id, thread_id, sent_at, account_id, to, and subject.
    """
    try:
        service = build_gmail_service(credentials)
        raw_msg = create_mime_message(
            sender=sender_email,
            to=to,
            subject=subject,
            body_text=body_text,
            cc=cc,
            bcc=bcc,
            in_reply_to=in_reply_to,
        )

        body: dict[str, Any] = {"raw": raw_msg}
        if thread_id:
            body["threadId"] = thread_id

        res = service.users().messages().send(userId="me", body=body).execute()

        msg_id = res.get("id", "")
        res_thread_id = res.get("threadId", thread_id)

        log_event(
            logger,
            "GMAIL_MESSAGE_SENT",
            account_id=account_id,
            message_id=msg_id,
            recipient_count=len(to),
        )

        return {
            "message_id": msg_id,
            "thread_id": res_thread_id,
            "sent_at": datetime.now(timezone.utc),
            "account_id": account_id or 0,
            "to": to,
            "subject": subject,
        }

    except Exception as exc:
        _handle_google_error(exc, account_id=account_id)
        raise
