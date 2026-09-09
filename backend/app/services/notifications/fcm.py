"""
CareerMail AI — Firebase Cloud Messaging (FCM) Service.

Provides client abstraction for sending push notifications:
  • Live mode: Authenticated FCM dispatch via firebase-admin when credentials exist.
  • Mock/Dry-Run mode: Safe simulated dispatch during development and tests.
  • Deactivation of invalid/unregistered tokens detected by provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import uuid

from app.config import get_settings
from app.utils.logging import get_logger, log_event

logger = get_logger("notifications.fcm")


@dataclass
class FCMResult:
    """Result of an FCM notification send attempt."""

    success: bool
    status: str  # "sent", "mock_sent", "failed"
    recipient_count: int
    message_id: Optional[str] = None
    invalid_tokens: list[str] = field(default_factory=list)
    detail: str = ""


class FCMClient:
    """Abstraction over Firebase Cloud Messaging."""

    def __init__(self, credentials_path: Optional[str] = None) -> None:
        self.settings = get_settings()
        self.credentials_path = (
            credentials_path
            if credentials_path is not None
            else self.settings.FIREBASE_CREDENTIALS_PATH
        )
        self.is_live: bool = False
        self._app: Any = None

        self._initialize_firebase()

    def _initialize_firebase(self) -> None:
        """Attempt to initialize firebase-admin SDK if credentials are valid."""
        if not self.settings.FCM_ENABLED:
            logger.info("FCM is disabled in configuration. Running in mock mode.")
            self.is_live = False
            return

        if not self.credentials_path or not Path(self.credentials_path).is_file():
            logger.info(
                "FCM credentials not found at %r. Running in mock/dry-run mode.",
                self.credentials_path,
            )
            self.is_live = False
            return

        try:
            import firebase_admin
            from firebase_admin import credentials

            app_name = "careermail_fcm"
            try:
                self._app = firebase_admin.get_app(app_name)
            except ValueError:
                cred = credentials.Certificate(self.credentials_path)
                self._app = firebase_admin.initialize_app(cred, name=app_name)

            self.is_live = True
            log_event(logger, "FIREBASE_INITIALIZED_LIVE", path=self.credentials_path)
        except Exception as exc:
            logger.warning(
                "Failed to initialize Firebase credentials at %r: %s. Falling back to mock mode.",
                self.credentials_path,
                exc,
            )
            self.is_live = False

    def send_to_tokens(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data_payload: Optional[dict[str, Any]] = None,
    ) -> FCMResult:
        """Send a push notification to a list of device tokens.

        Args:
            tokens: List of FCM device registration tokens.
            title: Notification title.
            body: Notification body text.
            data_payload: Safe dictionary of string key-values for deep-linking.

        Returns:
            FCMResult indicating status ('sent', 'mock_sent', or 'failed').
        """
        if not tokens:
            return FCMResult(
                success=True,
                status="mock_sent" if not self.is_live else "sent",
                recipient_count=0,
                detail="No device tokens provided",
            )

        # Prepare payload - FCM requires all data values to be strings
        safe_data: dict[str, str] = {}
        if data_payload:
            for k, v in data_payload.items():
                safe_data[str(k)] = str(v)

        # ── Mock Mode ──────────────────────────────────────────
        if not self.is_live:
            mock_id = f"mock-msg-{uuid.uuid4().hex[:12]}"
            logger.info(
                "FCM_MOCK_SENT | recipients=%d | title=%r | message_id=%s",
                len(tokens),
                title,
                mock_id,
            )
            return FCMResult(
                success=True,
                status="mock_sent",
                recipient_count=len(tokens),
                message_id=mock_id,
                invalid_tokens=[],
                detail=f"Notification simulated for {len(tokens)} device(s) (mock/dry-run mode)",
            )


        # ── Live Mode ──────────────────────────────────────────
        try:
            from firebase_admin import messaging

            message = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data=safe_data,
                tokens=tokens,
            )

            # Send via firebase_admin
            batch_response = messaging.send_each_for_multicast(message, app=self._app)

            success_count = batch_response.success_count
            failure_count = batch_response.failure_count

            invalid_tokens: list[str] = []
            for idx, resp in enumerate(batch_response.responses):
                if not resp.success and resp.exception:
                    err_code = getattr(resp.exception, "code", "")
                    err_str = str(resp.exception)
                    # Detect unregistered/invalid token errors
                    if (
                        "registration-token-not-registered" in err_str
                        or "invalid-argument" in err_str
                        or "NOT_FOUND" in err_str
                        or err_code in ("NOT_FOUND", "UNREGISTERED")
                    ):
                        invalid_tokens.append(tokens[idx])

            if failure_count > 0:
                logger.warning(
                    "FCM_PARTIAL_FAILURE | success=%d | failure=%d | invalid_tokens=%d",
                    success_count,
                    failure_count,
                    len(invalid_tokens),
                )

            if success_count == 0 and failure_count > 0:
                return FCMResult(
                    success=False,
                    status="failed",
                    recipient_count=0,
                    invalid_tokens=invalid_tokens,
                    detail=f"All {failure_count} FCM deliveries failed",
                )

            message_id = f"fcm-batch-{uuid.uuid4().hex[:10]}"
            return FCMResult(
                success=True,
                status="sent",
                recipient_count=success_count,
                message_id=message_id,
                invalid_tokens=invalid_tokens,
                detail=f"Successfully sent to {success_count} device(s)",
            )

        except Exception as exc:
            logger.error("FCM_SEND_EXCEPTION | error=%s", exc)
            return FCMResult(
                success=False,
                status="failed",
                recipient_count=0,
                detail=f"Firebase FCM dispatch error: {exc}",
            )


_global_fcm_client: Optional[FCMClient] = None


def get_fcm_client(credentials_path: Optional[str] = None) -> FCMClient:
    """Get or create singleton FCM client instance."""
    global _global_fcm_client
    if credentials_path is not None:
        return FCMClient(credentials_path=credentials_path)
    if _global_fcm_client is None:
        _global_fcm_client = FCMClient()
    return _global_fcm_client
