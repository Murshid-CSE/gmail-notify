"""
CareerMail AI — Email MIME Parser.

Independent, unit-testable module that converts raw Gmail API
message payloads into clean structured data.

Handles:
  • text/plain
  • text/html (→ readable text via BeautifulSoup)
  • multipart/alternative
  • multipart/mixed
  • nested multipart structures
  • missing bodies
  • malformed Base64 data
"""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

from bs4 import BeautifulSoup

from app.utils.logging import get_logger

logger = get_logger("gmail.parser")


class ParsedEmail:
    """Structured result of parsing a Gmail API message."""

    __slots__ = (
        "gmail_message_id",
        "gmail_thread_id",
        "sender",
        "recipients",
        "subject",
        "received_at",
        "body_text",
        "body_html",
        "labels",
        "snippet",
    )

    def __init__(
        self,
        gmail_message_id: str = "",
        gmail_thread_id: str = "",
        sender: str = "",
        recipients: list[str] | None = None,
        subject: str = "(no subject)",
        received_at: datetime | None = None,
        body_text: str | None = None,
        body_html: str | None = None,
        labels: list[str] | None = None,
        snippet: str = "",
    ):
        self.gmail_message_id = gmail_message_id
        self.gmail_thread_id = gmail_thread_id
        self.sender = sender
        self.recipients = recipients or []
        self.subject = subject
        self.received_at = received_at or datetime.now(timezone.utc)
        self.body_text = body_text
        self.body_html = body_html
        self.labels = labels or []
        self.snippet = snippet

    def recipients_json(self) -> str:
        """Serialize recipients list as JSON string for DB storage."""
        return json.dumps(self.recipients)

    def labels_json(self) -> str:
        """Serialize labels list as JSON string for DB storage."""
        return json.dumps(self.labels)


def parse_gmail_message(message: dict[str, Any]) -> ParsedEmail:
    """Parse a Gmail API message (format='full') into a ParsedEmail.

    Args:
        message: The raw dict from ``gmail.users().messages().get(format='full')``.

    Returns:
        Populated ParsedEmail instance.
    """
    gmail_id = message.get("id", "")
    thread_id = message.get("threadId", "")
    label_ids = message.get("labelIds", [])
    snippet = message.get("snippet", "")

    payload = message.get("payload", {})
    headers = _extract_headers(payload)

    # Parse received time from internalDate (milliseconds since epoch).
    internal_date_ms = message.get("internalDate")
    received_at = _parse_internal_date(internal_date_ms)

    # Extract bodies from the MIME tree.
    body_text, body_html = _extract_bodies(payload)

    # Convert HTML to readable text if we only have HTML.
    if not body_text and body_html:
        body_text = html_to_text(body_html)

    return ParsedEmail(
        gmail_message_id=gmail_id,
        gmail_thread_id=thread_id,
        sender=headers.get("from", ""),
        recipients=_parse_recipients(headers),
        subject=headers.get("subject", "(no subject)"),
        received_at=received_at,
        body_text=body_text,
        body_html=body_html,
        labels=label_ids,
        snippet=snippet,
    )


# ── Internal helpers ─────────────────────────────────────


def _extract_headers(payload: dict) -> dict[str, str]:
    """Extract a flat dict of header name → value from payload headers."""
    headers: dict[str, str] = {}
    for hdr in payload.get("headers", []):
        name = hdr.get("name", "").lower()
        value = hdr.get("value", "")
        headers[name] = value
    return headers


def _parse_recipients(headers: dict[str, str]) -> list[str]:
    """Combine To and Cc into a recipients list."""
    recipients: list[str] = []
    for field in ("to", "cc"):
        value = headers.get(field, "")
        if value:
            # Split on comma, but be careful with quoted display names.
            recipients.extend(
                addr.strip() for addr in value.split(",") if addr.strip()
            )
    return recipients


def _parse_internal_date(internal_date_ms: str | int | None) -> datetime:
    """Convert Gmail internalDate (ms since epoch) to datetime."""
    if internal_date_ms is None:
        return datetime.now(timezone.utc)
    try:
        ts = int(internal_date_ms) / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return datetime.now(timezone.utc)


def _extract_bodies(payload: dict) -> tuple[Optional[str], Optional[str]]:
    """Walk the MIME tree and extract text/plain and text/html bodies.

    Handles:
      • Simple single-part messages
      • multipart/alternative (prefers text/plain)
      • multipart/mixed
      • Nested multipart structures
    """
    text_parts: list[str] = []
    html_parts: list[str] = []

    _walk_parts(payload, text_parts, html_parts)

    body_text = "\n".join(text_parts) if text_parts else None
    body_html = "\n".join(html_parts) if html_parts else None

    return body_text, body_html


def _walk_parts(
    part: dict,
    text_parts: list[str],
    html_parts: list[str],
) -> None:
    """Recursively walk a MIME part tree."""
    mime_type = part.get("mimeType", "")

    # Leaf node: has body data.
    body_data = part.get("body", {}).get("data")
    if body_data is not None:
        decoded = _safe_base64_decode(body_data)
        if decoded is not None:
            if mime_type == "text/plain":
                text_parts.append(decoded)
            elif mime_type == "text/html":
                html_parts.append(decoded)

    # Container node: has sub-parts.
    sub_parts = part.get("parts", [])
    for sub_part in sub_parts:
        _walk_parts(sub_part, text_parts, html_parts)


def _safe_base64_decode(data: str) -> Optional[str]:
    """Decode URL-safe Base64 data from Gmail, handling malformed input."""
    try:
        # Gmail uses URL-safe base64 without padding.
        decoded_bytes = base64.urlsafe_b64decode(data + "==")
        return decoded_bytes.decode("utf-8", errors="replace")
    except Exception:
        logger.warning("BASE64_DECODE_FAILED | length=%d", len(data))
        return None


def html_to_text(html: str) -> str:
    """Convert HTML to clean readable text.

    Removes:
      • Script/style tags
      • Excessive whitespace
      • Common email boilerplate
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    # Remove scripts, styles, and hidden elements.
    for tag in soup(["script", "style", "head", "meta", "link"]):
        tag.decompose()

    # Get text with newlines between block elements.
    text = soup.get_text(separator="\n")

    # Clean up whitespace.
    text = _normalize_whitespace(text)

    # Remove common boilerplate patterns.
    text = _remove_boilerplate(text)

    return text.strip()


def _normalize_whitespace(text: str) -> str:
    """Collapse excessive whitespace while preserving paragraph breaks."""
    # Replace \r\n with \n.
    text = text.replace("\r\n", "\n")
    # Collapse runs of blank lines to max 2 newlines.
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse horizontal whitespace (tabs, spaces) to single space per line.
    lines = []
    for line in text.split("\n"):
        cleaned = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(cleaned)
    return "\n".join(lines)


def _remove_boilerplate(text: str) -> str:
    """Remove common email footer boilerplate."""
    # Common unsubscribe / footer patterns.
    boilerplate_patterns = [
        r"(?i)unsubscribe\s+from\s+this\s+(?:list|email)",
        r"(?i)if\s+you\s+no\s+longer\s+wish\s+to\s+receive",
        r"(?i)this\s+email\s+was\s+sent\s+to\s+you\s+because",
        r"(?i)view\s+this\s+email\s+in\s+your?\s+browser",
        r"(?i)having\s+trouble\s+viewing\s+this\s+email",
    ]

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        if any(re.search(pattern, line) for pattern in boilerplate_patterns):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)
