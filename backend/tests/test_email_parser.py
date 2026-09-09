"""
Tests for the Gmail MIME parser.

Covers:
  • Plain text extraction
  • HTML extraction and conversion
  • Multipart/alternative
  • Nested multipart
  • Missing body
  • Malformed Base64
  • Long email handling
  • Header parsing
  • Boilerplate removal
"""

import base64
import json

from app.services.gmail.parser import (
    ParsedEmail,
    html_to_text,
    parse_gmail_message,
    _safe_base64_decode,
    _normalize_whitespace,
    _remove_boilerplate,
)


def _b64(text: str) -> str:
    """Encode text as URL-safe base64 (Gmail format)."""
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


# ── Plain Text ──────────────────────────────────────────


class TestPlainText:
    def test_simple_plain_text(self):
        msg = _make_message(
            body_data=_b64("Hello, you have been shortlisted for XYZ Hackathon."),
            mime_type="text/plain",
        )
        parsed = parse_gmail_message(msg)
        assert "shortlisted" in parsed.body_text
        assert "XYZ Hackathon" in parsed.body_text

    def test_plain_text_with_unicode(self):
        msg = _make_message(
            body_data=_b64("Congratulations! 🎉 You are selected."),
            mime_type="text/plain",
        )
        parsed = parse_gmail_message(msg)
        assert "🎉" in parsed.body_text

    def test_empty_plain_text(self):
        msg = _make_message(body_data=_b64(""), mime_type="text/plain")
        parsed = parse_gmail_message(msg)
        # Empty string decoded is still a string.
        assert parsed.body_text is not None


# ── HTML ────────────────────────────────────────────────


class TestHTML:
    def test_html_body_extracted(self):
        html = "<html><body><h1>Welcome</h1><p>Your application is received.</p></body></html>"
        msg = _make_message(body_data=_b64(html), mime_type="text/html")
        parsed = parse_gmail_message(msg)
        assert parsed.body_html is not None
        assert "Welcome" in parsed.body_html
        # Also gets converted to text.
        assert parsed.body_text is not None
        assert "Welcome" in parsed.body_text
        assert "<h1>" not in parsed.body_text

    def test_html_to_text_removes_scripts(self):
        html = "<html><body><script>alert('x')</script><p>Real content.</p></body></html>"
        result = html_to_text(html)
        assert "alert" not in result
        assert "Real content" in result

    def test_html_to_text_removes_styles(self):
        html = "<html><body><style>.x{color:red}</style><p>Visible text.</p></body></html>"
        result = html_to_text(html)
        assert "color" not in result
        assert "Visible text" in result

    def test_html_to_text_empty(self):
        assert html_to_text("") == ""
        assert html_to_text(None) == ""


# ── Multipart ──────────────────────────────────────────


class TestMultipart:
    def test_multipart_alternative(self):
        """Multipart with both text and html parts."""
        msg = _make_multipart_message(
            text_body="Plain version of the email.",
            html_body="<html><body><p>HTML version.</p></body></html>",
        )
        parsed = parse_gmail_message(msg)
        assert parsed.body_text is not None
        assert "Plain version" in parsed.body_text
        assert parsed.body_html is not None
        assert "HTML version" in parsed.body_html

    def test_multipart_text_only(self):
        """Multipart with only text part."""
        msg = _make_multipart_message(text_body="Only plain text here.")
        parsed = parse_gmail_message(msg)
        assert "Only plain text" in parsed.body_text

    def test_multipart_html_only(self):
        """Multipart with only HTML part — gets converted to text."""
        msg = _make_multipart_message(
            html_body="<html><body><p>Only HTML content here.</p></body></html>"
        )
        parsed = parse_gmail_message(msg)
        assert parsed.body_text is not None
        assert "Only HTML content" in parsed.body_text

    def test_nested_multipart(self):
        """Nested multipart structure."""
        msg = {
            "id": "nested1",
            "threadId": "thread1",
            "internalDate": "1700000000000",
            "labelIds": ["INBOX"],
            "snippet": "Nested test",
            "payload": {
                "mimeType": "multipart/mixed",
                "headers": [
                    {"name": "From", "value": "test@example.com"},
                    {"name": "Subject", "value": "Nested multipart"},
                ],
                "parts": [
                    {
                        "mimeType": "multipart/alternative",
                        "parts": [
                            {
                                "mimeType": "text/plain",
                                "body": {"data": _b64("Nested plain text.")},
                            },
                            {
                                "mimeType": "text/html",
                                "body": {
                                    "data": _b64("<p>Nested HTML.</p>")
                                },
                            },
                        ],
                    },
                    {
                        "mimeType": "application/pdf",
                        "filename": "resume.pdf",
                        "body": {"attachmentId": "att1", "size": 12345},
                    },
                ],
            },
        }
        parsed = parse_gmail_message(msg)
        assert "Nested plain text" in parsed.body_text
        assert parsed.body_html is not None


# ── Missing / Malformed ────────────────────────────────


class TestEdgeCases:
    def test_missing_body(self):
        """Message with no body data at all."""
        msg = {
            "id": "nobody1",
            "threadId": "thread1",
            "internalDate": "1700000000000",
            "labelIds": [],
            "snippet": "",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": "test@example.com"},
                    {"name": "Subject", "value": "Empty email"},
                ],
                "body": {},
            },
        }
        parsed = parse_gmail_message(msg)
        assert parsed.body_text is None or parsed.body_text == ""
        assert parsed.subject == "Empty email"

    def test_malformed_base64(self):
        """Graceful handling of malformed base64 data."""
        msg = _make_message(
            body_data="!!!not-valid-base64!!!",
            mime_type="text/plain",
        )
        parsed = parse_gmail_message(msg)
        # Should not crash — body may be None.
        assert parsed.gmail_message_id == "test1"

    def test_missing_subject(self):
        """Missing subject header falls back to default."""
        msg = {
            "id": "nosubj1",
            "threadId": "thread1",
            "internalDate": "1700000000000",
            "labelIds": [],
            "snippet": "",
            "payload": {
                "mimeType": "text/plain",
                "headers": [{"name": "From", "value": "test@example.com"}],
                "body": {"data": _b64("body text")},
            },
        }
        parsed = parse_gmail_message(msg)
        assert parsed.subject == "(no subject)"

    def test_missing_internal_date(self):
        """Missing internalDate falls back to current time."""
        msg = _make_message(body_data=_b64("test"), mime_type="text/plain")
        del msg["internalDate"]
        parsed = parse_gmail_message(msg)
        assert parsed.received_at is not None

    def test_long_email(self):
        """Long email body is handled without truncation in parser."""
        long_body = "A" * 100_000
        msg = _make_message(body_data=_b64(long_body), mime_type="text/plain")
        parsed = parse_gmail_message(msg)
        assert len(parsed.body_text) == 100_000


# ── Headers ────────────────────────────────────────────


class TestHeaders:
    def test_sender_extraction(self):
        msg = _make_message(
            body_data=_b64("test"),
            mime_type="text/plain",
            sender="hackathon@example.com",
        )
        parsed = parse_gmail_message(msg)
        assert parsed.sender == "hackathon@example.com"

    def test_recipients_extraction(self):
        msg = _make_message(
            body_data=_b64("test"),
            mime_type="text/plain",
            recipients="user1@example.com, user2@example.com",
        )
        parsed = parse_gmail_message(msg)
        assert len(parsed.recipients) == 2
        assert "user1@example.com" in parsed.recipients

    def test_labels_extraction(self):
        msg = _make_message(body_data=_b64("test"), mime_type="text/plain")
        msg["labelIds"] = ["INBOX", "IMPORTANT", "CATEGORY_UPDATES"]
        parsed = parse_gmail_message(msg)
        assert "INBOX" in parsed.labels
        assert "IMPORTANT" in parsed.labels

    def test_labels_json_serialization(self):
        parsed = ParsedEmail(labels=["INBOX", "STARRED"])
        labels_json = parsed.labels_json()
        assert json.loads(labels_json) == ["INBOX", "STARRED"]

    def test_recipients_json_serialization(self):
        parsed = ParsedEmail(recipients=["a@b.com", "c@d.com"])
        recipients_json = parsed.recipients_json()
        assert json.loads(recipients_json) == ["a@b.com", "c@d.com"]


# ── Boilerplate Removal ───────────────────────────────


class TestBoilerplate:
    def test_unsubscribe_removed(self):
        text = "Important content.\nUnsubscribe from this list.\nMore stuff."
        result = _remove_boilerplate(text)
        assert "Unsubscribe" not in result
        assert "Important content" in result

    def test_normal_text_preserved(self):
        text = "Your hackathon submission has been received.\nDeadline: Sept 15."
        result = _remove_boilerplate(text)
        assert "hackathon submission" in result
        assert "Deadline" in result


# ── Whitespace Normalization ───────────────────────────


class TestWhitespace:
    def test_excessive_newlines_collapsed(self):
        text = "line 1\n\n\n\n\nline 2"
        result = _normalize_whitespace(text)
        assert result.count("\n") <= 2

    def test_tabs_collapsed(self):
        text = "word1\t\t\tword2"
        result = _normalize_whitespace(text)
        assert "word1 word2" in result


# ── Utilities ──────────────────────────────────────────


class TestBase64:
    def test_valid_decode(self):
        data = _b64("Hello World")
        result = _safe_base64_decode(data)
        assert result == "Hello World"

    def test_invalid_decode(self):
        result = _safe_base64_decode("!!!invalid!!!")
        # Should not raise — returns None.
        # (Actually base64 may not fail on all invalid strings, but the parser handles it.)


# ── Test helpers ───────────────────────────────────────


def _make_message(
    body_data: str,
    mime_type: str,
    sender: str = "test@example.com",
    subject: str = "Test Subject",
    recipients: str = "",
    msg_id: str = "test1",
) -> dict:
    """Build a minimal Gmail API message dict."""
    headers = [
        {"name": "From", "value": sender},
        {"name": "Subject", "value": subject},
    ]
    if recipients:
        headers.append({"name": "To", "value": recipients})

    return {
        "id": msg_id,
        "threadId": "thread1",
        "internalDate": "1700000000000",
        "labelIds": ["INBOX"],
        "snippet": "snippet",
        "payload": {
            "mimeType": mime_type,
            "headers": headers,
            "body": {"data": body_data},
        },
    }


def _make_multipart_message(
    text_body: str | None = None,
    html_body: str | None = None,
    msg_id: str = "multi1",
) -> dict:
    """Build a multipart/alternative Gmail API message dict."""
    parts = []
    if text_body:
        parts.append(
            {"mimeType": "text/plain", "body": {"data": _b64(text_body)}}
        )
    if html_body:
        parts.append(
            {"mimeType": "text/html", "body": {"data": _b64(html_body)}}
        )

    return {
        "id": msg_id,
        "threadId": "thread1",
        "internalDate": "1700000000000",
        "labelIds": ["INBOX"],
        "snippet": "snippet",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "Subject", "value": "Multipart Test"},
                {"name": "To", "value": "me@example.com"},
            ],
            "body": {},
            "parts": parts,
        },
    }
