"""
CareerMail AI — Email Composer API Schemas.

Pydantic models for AI draft generation, Gmail draft creation,
and explicit email sending with safety confirmation checks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EmailDraftGenerateRequest(BaseModel):
    """Request to generate a context-aware email draft using AI."""

    opportunity_id: int
    instruction: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Natural language instruction describing the desired email.",
    )
    account_id: Optional[int] = Field(
        None,
        description="Optional preferred account ID to send from.",
    )


class EmailDraft(BaseModel):
    """Structured email draft produced by AI or edited by the user."""

    model_config = ConfigDict(from_attributes=True)

    to: list[str] = Field(
        default_factory=list,
        description="Recipient email addresses (derived strictly from source email or user input).",
    )
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    subject: str = Field(..., description="Subject line for the email.")
    body_text: str = Field(..., description="Plain-text body of the email.")
    in_reply_to: Optional[str] = Field(
        None,
        description="Gmail Message-ID header for threading/replies.",
    )
    thread_id: Optional[str] = Field(
        None,
        description="Gmail threadId for threading.",
    )
    suggested_account_id: Optional[int] = Field(
        None,
        description="Account ID linked to the opportunity's source email.",
    )


class GmailDraftCreateRequest(BaseModel):
    """Request to create an actual Gmail draft in the user's connected mailbox."""

    account_id: int
    opportunity_id: int
    draft: EmailDraft


class GmailDraftResponse(BaseModel):
    """Confirmation of a draft created in Gmail."""

    draft_id: str
    message_id: str
    account_id: int
    subject: str


class EmailSendRequest(BaseModel):
    """Request to explicitly send an email via Gmail API."""

    account_id: int
    opportunity_id: int
    to: list[str] = Field(..., min_length=1, description="At least one recipient address is required.")
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    subject: str = Field(..., min_length=1)
    body_text: str = Field(..., min_length=1)
    in_reply_to: Optional[str] = None
    thread_id: Optional[str] = None
    confirmed: bool = Field(
        False,
        description="Explicit user confirmation flag. Must be True to allow transmission.",
    )


class EmailSendResponse(BaseModel):
    """Confirmation of an email sent via Gmail API."""

    message_id: str
    thread_id: Optional[str] = None
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    account_id: int
    to: list[str]
    subject: str
