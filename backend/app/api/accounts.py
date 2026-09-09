"""
CareerMail AI — Account Management API routes.

GET    /accounts            → List connected accounts (no secrets).
POST   /accounts/{id}/sync  → Trigger email sync for an account.
DELETE /accounts/{id}        → Disconnect and delete an account.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.schemas.account import AccountListResponse, AccountResponse, SyncResponse
from app.services.gmail.auth import revoke_token
from app.services.gmail.sync import sync_account
from app.utils.logging import get_logger, log_event

logger = get_logger("api.accounts")

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get(
    "",
    response_model=AccountListResponse,
    summary="List connected Gmail accounts",
)
def list_accounts(db: Session = Depends(get_db)):
    """Return all connected accounts with message counts. Never exposes tokens."""
    accounts = (
        db.query(EmailAccount)
        .filter(EmailAccount.is_active == True)
        .order_by(EmailAccount.created_at)
        .all()
    )

    account_responses = []
    for acct in accounts:
        msg_count = (
            db.query(EmailMessage)
            .filter(EmailMessage.account_id == acct.id)
            .count()
        )
        resp = AccountResponse(
            id=acct.id,
            email_address=acct.email_address,
            provider=acct.provider,
            is_active=acct.is_active,
            last_sync_at=acct.last_sync_at,
            message_count=msg_count,
            created_at=acct.created_at,
        )
        account_responses.append(resp)

    return AccountListResponse(accounts=account_responses, total=len(account_responses))


@router.post(
    "/{account_id}/sync",
    response_model=SyncResponse,
    summary="Sync emails for an account",
)
def trigger_sync(account_id: int, db: Session = Depends(get_db)):
    """Fetch new emails from Gmail for the specified account."""
    account = (
        db.query(EmailAccount)
        .filter(EmailAccount.id == account_id, EmailAccount.is_active == True)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found or inactive.")

    if not account.encrypted_refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Account has no refresh token. Please re-connect the account.",
        )

    try:
        result = sync_account(db, account)
    except Exception as exc:
        logger.error(
            "SYNC_API_ERROR | account_id=%d | error=%s", account_id, str(exc)
        )
        raise HTTPException(
            status_code=502,
            detail=f"Gmail sync failed: {str(exc)}",
        )

    total_in_db = (
        db.query(EmailMessage)
        .filter(EmailMessage.account_id == account_id)
        .count()
    )

    return SyncResponse(
        account_id=account.id,
        email_address=account.email_address,
        new_messages=result.new_messages,
        skipped_duplicates=result.skipped_duplicates,
        total_messages_in_db=total_in_db,
        sync_duration_seconds=result.duration_seconds,
        message=f"Synced {result.new_messages} new messages.",
    )


@router.delete(
    "/{account_id}",
    summary="Disconnect a Gmail account",
)
def delete_account(account_id: int, db: Session = Depends(get_db)):
    """Disconnect a Gmail account: revoke tokens, delete account and messages."""
    account = db.query(EmailAccount).filter(EmailAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")

    email_address = account.email_address

    # Revoke OAuth tokens with Google.
    if account.encrypted_refresh_token:
        revoke_token(account.encrypted_refresh_token)

    # Delete all messages for this account (cascade should handle this,
    # but be explicit for safety).
    db.query(EmailMessage).filter(EmailMessage.account_id == account_id).delete()

    # Delete the account.
    db.delete(account)
    db.commit()

    log_event(logger, "ACCOUNT_DISCONNECTED", email=email_address)

    return {"message": f"Account {email_address} has been disconnected and all data deleted."}
