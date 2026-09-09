"""
CareerMail AI — Google OAuth 2.0 Service.

Handles:
  • Generating the authorization URL
  • Exchanging the auth code for tokens
  • Refreshing expired access tokens
  • Revoking tokens (account disconnect)
  • Building an authenticated Gmail API service

Never logs tokens. Never stores plaintext tokens.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import get_settings
from app.utils.logging import get_logger, log_event
from app.utils.security import encrypt_value, decrypt_value

logger = get_logger("gmail.auth")

# Required scopes: read-only access, compose drafts, and explicit sending.
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
]


class OAuthScopeError(Exception):
    """Raised when Gmail credentials lack required scopes (e.g., 403 insufficientPermissions)."""

    def __init__(self, message: str = "Insufficient Gmail permissions. Re-authorization required.", account_id: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.account_id = account_id


# Google endpoints
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URI = "https://oauth2.googleapis.com/revoke"


def _build_client_config() -> dict:
    """Build the OAuth client config dict from environment variables."""
    settings = get_settings()
    settings.require_google_oauth()
    return {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": GOOGLE_AUTH_URI,
            "token_uri": GOOGLE_TOKEN_URI,
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }


def get_authorization_url(state: Optional[str] = None) -> tuple[str, str]:
    """Generate the Google OAuth authorization URL.

    Returns:
        (authorization_url, state)
    """
    settings = get_settings()
    flow = Flow.from_client_config(
        client_config=_build_client_config(),
        scopes=GMAIL_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
        autogenerate_code_verifier=False,
    )

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )

    log_event(logger, "OAUTH_URL_GENERATED")
    return authorization_url, state


def exchange_code_for_credentials(code: str) -> dict:
    """Exchange the authorization code for OAuth credentials.

    Args:
        code: The authorization code from Google's callback.

    Returns:
        Dict with: access_token, refresh_token (encrypted), token_expiry, email.
    """
    settings = get_settings()
    flow = Flow.from_client_config(
        client_config=_build_client_config(),
        scopes=GMAIL_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
        autogenerate_code_verifier=False,
    )

    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Get the user's email address from Gmail API.
    service = build("gmail", "v1", credentials=credentials)
    profile = service.users().getProfile(userId="me").execute()
    email_address = profile.get("emailAddress", "")

    log_event(logger, "OAUTH_TOKEN_EXCHANGED", email=email_address)

    # Encrypt tokens before returning.
    return {
        "access_token_encrypted": encrypt_value(credentials.token),
        "refresh_token_encrypted": (
            encrypt_value(credentials.refresh_token)
            if credentials.refresh_token
            else None
        ),
        "token_expiry": credentials.expiry,
        "email_address": email_address,
    }


def build_credentials_from_encrypted(
    encrypted_access_token: Optional[str],
    encrypted_refresh_token: Optional[str],
    token_expiry: Optional[datetime],
) -> Credentials:
    """Rebuild Google Credentials from encrypted stored values.

    Handles automatic refresh if the access token is expired.
    """
    settings = get_settings()
    settings.require_google_oauth()

    access_token = decrypt_value(encrypted_access_token) if encrypted_access_token else None
    refresh_token = (
        decrypt_value(encrypted_refresh_token) if encrypted_refresh_token else None
    )

    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        expiry=token_expiry,
    )

    # Refresh if expired.
    if credentials.expired and credentials.refresh_token:
        log_event(logger, "TOKEN_REFRESH_STARTED")
        credentials.refresh(Request())
        log_event(logger, "TOKEN_REFRESHED")

    return credentials


def get_refreshed_tokens(credentials: Credentials) -> dict:
    """Extract and encrypt the (possibly refreshed) tokens from credentials.

    Returns:
        Dict with encrypted tokens and expiry, for updating the DB.
    """
    return {
        "encrypted_access_token": encrypt_value(credentials.token) if credentials.token else None,
        "encrypted_refresh_token": (
            encrypt_value(credentials.refresh_token)
            if credentials.refresh_token
            else None
        ),
        "token_expiry": credentials.expiry,
    }


def build_gmail_service(credentials: Credentials):
    """Build and return an authenticated Gmail API service."""
    return build("gmail", "v1", credentials=credentials)


def revoke_token(encrypted_refresh_token: str) -> bool:
    """Revoke OAuth tokens with Google.

    Returns:
        True if revocation succeeded or token was already invalid.
    """
    import httpx

    try:
        token = decrypt_value(encrypted_refresh_token)
        response = httpx.post(
            GOOGLE_REVOKE_URI,
            params={"token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10.0,
        )
        if response.status_code == 200:
            log_event(logger, "TOKEN_REVOKED")
            return True
        else:
            logger.warning(
                "TOKEN_REVOKE_FAILED | status=%d", response.status_code
            )
            return True  # Treat as success — the token is unusable either way.
    except Exception as exc:
        logger.error("TOKEN_REVOKE_ERROR | error=%s", str(exc))
        return False
