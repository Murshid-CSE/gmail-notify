"""
CareerMail AI — Google OAuth 2.0 API routes.

GET  /auth/google/start     → Returns the Google OAuth authorization URL.
GET  /auth/google/callback   → Handles the OAuth callback, stores account.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.email_account import EmailAccount
from app.models.user import User
from app.schemas.account import OAuthStartResponse
from app.services.gmail.auth import exchange_code_for_credentials, get_authorization_url
from app.utils.logging import get_logger, log_event

logger = get_logger("api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])

DEFAULT_USER_ID = 1  # Single-user MVP.


def _ensure_default_user(db: Session) -> User:
    """Create the default user if it doesn't exist."""
    user = db.query(User).filter(User.id == DEFAULT_USER_ID).first()
    if not user:
        user = User(id=DEFAULT_USER_ID, display_name="Default User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get(
    "/google/start",
    response_model=OAuthStartResponse,
    summary="Start Google OAuth flow",
)
def start_google_oauth(db: Session = Depends(get_db)):
    """Generate the Google OAuth authorization URL.

    Open the returned URL in a browser to connect a Gmail account.
    """
    settings = get_settings()
    settings.require_google_oauth()
    settings.require_encryption()

    # Check that user doesn't already have 2 accounts.
    _ensure_default_user(db)
    account_count = (
        db.query(EmailAccount)
        .filter(
            EmailAccount.user_id == DEFAULT_USER_ID,
            EmailAccount.is_active == True,
        )
        .count()
    )
    if account_count >= 2:
        raise HTTPException(
            status_code=400,
            detail="Maximum of 2 Gmail accounts already connected. "
            "Disconnect an account before adding a new one.",
        )

    authorization_url, state = get_authorization_url()
    log_event(logger, "OAUTH_FLOW_STARTED")

    return OAuthStartResponse(authorization_url=authorization_url)


@router.get(
    "/google/callback",
    response_class=HTMLResponse,
    summary="Google OAuth callback",
)
def google_oauth_callback(
    code: str,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Handle the OAuth callback from Google.

    Exchanges the auth code for tokens, creates/updates an EmailAccount.
    """
    if error:
        log_event(logger, "OAUTH_ERROR", error=error)
        raise HTTPException(status_code=400, detail=f"OAuth authorization failed: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code provided.")

    try:
        result = exchange_code_for_credentials(code)
    except Exception as exc:
        logger.error("OAUTH_EXCHANGE_FAILED | error=%s", str(exc))
        raise HTTPException(
            status_code=500,
            detail="Failed to exchange authorization code. Please try again.",
        )

    email_address = result["email_address"]
    _ensure_default_user(db)

    # Check if this email is already connected.
    existing = (
        db.query(EmailAccount)
        .filter(EmailAccount.email_address == email_address)
        .first()
    )

    if existing:
        # Update tokens for existing account.
        existing.encrypted_access_token = result["access_token_encrypted"]
        if result["refresh_token_encrypted"]:
            existing.encrypted_refresh_token = result["refresh_token_encrypted"]
        existing.token_expiry = result["token_expiry"]
        existing.is_active = True
        log_event(logger, "ACCOUNT_TOKENS_UPDATED", email=email_address)
    else:
        # Check limit.
        active_count = (
            db.query(EmailAccount)
            .filter(
                EmailAccount.user_id == DEFAULT_USER_ID,
                EmailAccount.is_active == True,
            )
            .count()
        )
        if active_count >= 2:
            raise HTTPException(
                status_code=400,
                detail="Maximum of 2 Gmail accounts reached.",
            )

        new_account = EmailAccount(
            user_id=DEFAULT_USER_ID,
            provider="gmail",
            email_address=email_address,
            encrypted_access_token=result["access_token_encrypted"],
            encrypted_refresh_token=result["refresh_token_encrypted"],
            token_expiry=result["token_expiry"],
            is_active=True,
        )
        db.add(new_account)
        log_event(logger, "ACCOUNT_CONNECTED", email=email_address)

    db.commit()

    # Return a simple success page.
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>CareerMail AI — Account Connected</title></head>
        <body style="font-family: system-ui; max-width: 600px; margin: 80px auto; text-align: center;">
            <h1>✅ Gmail Account Connected</h1>
            <p><strong>{email_address}</strong> has been connected to CareerMail AI.</p>
            <p>You can close this window and return to the application.</p>
            <p style="margin-top: 40px; color: #666;">
                Next step: <code>POST /accounts/&lt;id&gt;/sync</code> to fetch your emails.
            </p>
        </body>
        </html>
        """,
        status_code=200,
    )
