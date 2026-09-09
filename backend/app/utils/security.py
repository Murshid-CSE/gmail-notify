"""
CareerMail AI — Token Encryption Utilities.

Uses Fernet symmetric encryption to protect OAuth tokens at rest.
The ENCRYPTION_KEY env var must be a valid Fernet key (base64-encoded 32 bytes).
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger("security")


def _get_fernet() -> Fernet:
    """Return a Fernet instance from the configured encryption key."""
    settings = get_settings()
    settings.require_encryption()
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value and return the ciphertext as a UTF-8 string.

    Args:
        plaintext: The value to encrypt (e.g., an OAuth refresh token).

    Returns:
        Base64-encoded ciphertext string.

    Raises:
        RuntimeError: If ENCRYPTION_KEY is not configured.
    """
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a previously encrypted string.

    Args:
        ciphertext: The encrypted value from :func:`encrypt_value`.

    Returns:
        The original plaintext string.

    Raises:
        RuntimeError: If ENCRYPTION_KEY is not configured.
        ValueError: If decryption fails (wrong key, corrupted data).
    """
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        logger.error("TOKEN_DECRYPT_FAILED | Fernet decryption error")
        raise ValueError(
            "Failed to decrypt value. The ENCRYPTION_KEY may have changed "
            "or the stored data is corrupted."
        ) from exc
