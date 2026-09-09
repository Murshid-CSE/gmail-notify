"""
CareerMail AI — Gmail Sync Service.

Fetches emails from a connected Gmail account using the Gmail API.
Handles pagination, deduplication, and token refresh transparently.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Optional

from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.services.gmail.auth import (
    build_credentials_from_encrypted,
    build_gmail_service,
    get_refreshed_tokens,
)
from app.services.gmail.parser import parse_gmail_message
from app.utils.logging import get_logger, log_event
from app.utils.retry import retry_with_backoff

logger = get_logger("gmail.sync")


class SyncResult:
    """Result of a sync operation."""

    __slots__ = ("new_messages", "skipped_duplicates", "errors", "duration_seconds")

    def __init__(self):
        self.new_messages: int = 0
        self.skipped_duplicates: int = 0
        self.errors: int = 0
        self.duration_seconds: float = 0.0


def sync_account(db: Session, account: EmailAccount) -> SyncResult:
    """Synchronize emails for the given account.

    1. Build authenticated Gmail service.
    2. List messages with pagination.
    3. Fetch each message in full.
    4. Parse MIME structure.
    5. Store in DB (skip duplicates).
    6. Update account sync state.

    Args:
        db: Active database session.
        account: The EmailAccount to sync.

    Returns:
        SyncResult with counts of new/skipped/errored messages.
    """
    settings = get_settings()
    result = SyncResult()
    start_time = time.time()

    log_event(
        logger,
        "SYNC_STARTED",
        account_id=account.id,
        email=account.email_address,
    )

    try:
        # 1. Build authenticated service.
        credentials = build_credentials_from_encrypted(
            encrypted_access_token=account.encrypted_access_token,
            encrypted_refresh_token=account.encrypted_refresh_token,
            token_expiry=account.token_expiry,
        )
        service = build_gmail_service(credentials)

        # 2. Fetch message IDs with pagination.
        message_ids = _list_message_ids(
            service, max_results=settings.MAX_SYNC_MESSAGES
        )

        log_event(
            logger,
            "MESSAGES_LISTED",
            account_id=account.id,
            count=len(message_ids),
        )

        # 3. Process each message.
        existing_gmail_ids = _get_existing_gmail_ids(db, account.id)

        for msg_stub in message_ids:
            gmail_id = msg_stub["id"]

            # Skip already-stored messages.
            if gmail_id in existing_gmail_ids:
                result.skipped_duplicates += 1
                continue

            try:
                email_msg = _fetch_and_store_message(
                    service, db, account.id, gmail_id
                )
                if email_msg:
                    result.new_messages += 1
            except Exception as exc:
                result.errors += 1
                logger.error(
                    "MESSAGE_FETCH_FAILED | account_id=%d | gmail_id=%s | error=%s",
                    account.id,
                    gmail_id,
                    str(exc),
                )

        # 4. Update account sync state.
        _update_account_sync_state(db, account, credentials)

        db.commit()

    except HttpError as exc:
        logger.error(
            "GMAIL_API_ERROR | account_id=%d | status=%d | error=%s",
            account.id,
            exc.resp.status if exc.resp else 0,
            str(exc),
        )
        raise
    except Exception as exc:
        logger.error(
            "SYNC_FAILED | account_id=%d | error=%s",
            account.id,
            str(exc),
        )
        raise
    finally:
        result.duration_seconds = round(time.time() - start_time, 2)
        log_event(
            logger,
            "SYNC_COMPLETED",
            account_id=account.id,
            new=result.new_messages,
            skipped=result.skipped_duplicates,
            errors=result.errors,
            duration=f"{result.duration_seconds}s",
        )

    return result


# ── Internal helpers ─────────────────────────────────────


@retry_with_backoff(
    max_retries=3,
    base_delay=1.0,
    retryable_exceptions=(HttpError, ConnectionError, TimeoutError),
)
def _list_message_ids(
    service,
    max_results: int = 500,
    query: str = "",
) -> list[dict]:
    """List Gmail message IDs with full pagination.

    Returns a list of ``{"id": ..., "threadId": ...}`` dicts, up to max_results.
    """
    all_messages: list[dict] = []
    page_token: Optional[str] = None

    while len(all_messages) < max_results:
        batch_size = min(100, max_results - len(all_messages))

        request_kwargs: dict = {
            "userId": "me",
            "maxResults": batch_size,
        }
        if page_token:
            request_kwargs["pageToken"] = page_token
        if query:
            request_kwargs["q"] = query

        response = service.users().messages().list(**request_kwargs).execute()

        messages = response.get("messages", [])
        all_messages.extend(messages)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return all_messages[:max_results]


def _get_existing_gmail_ids(db: Session, account_id: int) -> set[str]:
    """Get the set of gmail_message_ids already stored for this account."""
    rows = (
        db.query(EmailMessage.gmail_message_id)
        .filter(EmailMessage.account_id == account_id)
        .all()
    )
    return {row[0] for row in rows}


@retry_with_backoff(
    max_retries=2,
    base_delay=0.5,
    retryable_exceptions=(HttpError, ConnectionError, TimeoutError),
)
def _fetch_full_message(service, gmail_id: str) -> dict:
    """Fetch a single Gmail message in full format."""
    return (
        service.users()
        .messages()
        .get(userId="me", id=gmail_id, format="full")
        .execute()
    )


def _fetch_and_store_message(
    service,
    db: Session,
    account_id: int,
    gmail_id: str,
) -> Optional[EmailMessage]:
    """Fetch one message from Gmail, parse it, and store in DB."""
    raw_msg = _fetch_full_message(service, gmail_id)
    parsed = parse_gmail_message(raw_msg)

    email_message = EmailMessage(
        account_id=account_id,
        gmail_message_id=parsed.gmail_message_id,
        gmail_thread_id=parsed.gmail_thread_id,
        sender=parsed.sender,
        recipients=parsed.recipients_json(),
        subject=parsed.subject,
        received_at=parsed.received_at,
        body_text=parsed.body_text,
        body_html=parsed.body_html,
        labels=parsed.labels_json(),
        processing_status="pending",
    )

    db.add(email_message)

    # Flush to check for unique constraint violations.
    try:
        db.flush()
        log_event(
            logger,
            "EMAIL_FETCHED",
            account_id=account_id,
            gmail_id=gmail_id,
            subject_length=len(parsed.subject),
        )
        return email_message
    except Exception:
        # Duplicate — roll back just this message.
        db.rollback()
        return None


def _update_account_sync_state(
    db: Session,
    account: EmailAccount,
    credentials,
) -> None:
    """Update the account's last_sync_at and refreshed tokens."""
    account.last_sync_at = datetime.now(timezone.utc)

    # Persist any refreshed tokens.
    refreshed = get_refreshed_tokens(credentials)
    if refreshed["encrypted_access_token"]:
        account.encrypted_access_token = refreshed["encrypted_access_token"]
    if refreshed["encrypted_refresh_token"]:
        account.encrypted_refresh_token = refreshed["encrypted_refresh_token"]
    if refreshed["token_expiry"]:
        account.token_expiry = refreshed["token_expiry"]
