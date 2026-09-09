"""
CareerMail AI — Extraction Pydantic Schemas.

Strict validation for AI-extracted email analysis results.
All fields that may not be present in the email default to None.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    """Email category for career/college classification."""
    hackathon = "hackathon"
    internship = "internship"
    placement = "placement"
    college = "college"
    exam = "exam"
    scholarship = "scholarship"
    competition = "competition"
    event = "event"
    other = "other"


class Status(str, Enum):
    """Opportunity/email status."""
    opportunity = "opportunity"
    registered = "registered"
    shortlisted = "shortlisted"
    next_round = "next_round"
    assessment = "assessment"
    interview = "interview"
    selected = "selected"
    rejected = "rejected"
    completed = "completed"
    informational = "informational"
    unknown = "unknown"


class Priority(str, Enum):
    """Action priority level."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class EmailAnalysis(BaseModel):
    """Structured extraction result from a single email.

    All Optional fields default to None — the AI must NOT invent values.
    """

    category: Category = Field(
        description="Primary classification of the email."
    )
    title: Optional[str] = Field(
        default=None,
        description="Short title summarizing the opportunity/event."
    )
    organization: Optional[str] = Field(
        default=None,
        description="Company, university, or organizing body. Extract only if stated."
    )
    description: Optional[str] = Field(
        default=None,
        description="Brief 1-2 sentence summary of the email content."
    )
    status: Status = Field(
        default=Status.unknown,
        description="Current status of the opportunity. Use 'unknown' if unclear."
    )
    round_name: Optional[str] = Field(
        default=None,
        description="Name of the round (e.g., 'Round 2', 'Technical Interview'). Only if stated."
    )
    deadline: Optional[str] = Field(
        default=None,
        description="Exact deadline as stated in the email (ISO format or original text). Do NOT invent."
    )
    event_date: Optional[str] = Field(
        default=None,
        description="Date of the event/hackathon/exam. Only if explicitly stated."
    )
    location: Optional[str] = Field(
        default=None,
        description="Physical location or 'online'. Only if stated."
    )
    eligibility: Optional[str] = Field(
        default=None,
        description="Eligibility criteria mentioned in the email."
    )
    action_required: bool = Field(
        default=False,
        description="Whether the recipient needs to take an action."
    )
    action: Optional[str] = Field(
        default=None,
        description="Specific action the recipient needs to take."
    )
    apply_url: Optional[str] = Field(
        default=None,
        description="URL for application/registration. Extract only if present."
    )
    event_url: Optional[str] = Field(
        default=None,
        description="URL for the event page. Extract only if present."
    )
    contact_emails: Optional[list[str]] = Field(
        default=None,
        description="Contact email addresses mentioned in the email."
    )
    priority: Priority = Field(
        default=Priority.medium,
        description="How urgent/important this is for the recipient."
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Model's confidence in the extraction (0.0 to 1.0)."
    )
    important_facts: Optional[list[str]] = Field(
        default=None,
        description="Key facts extracted from the email as a bullet list."
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v):
        if v is None:
            return 0.5
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, v))

    @field_validator("deadline", "event_date", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


class ExtractionResult(BaseModel):
    """Wrapper around EmailAnalysis with processing metadata."""
    analysis: Optional[EmailAnalysis] = None
    raw_response: Optional[str] = Field(
        default=None,
        description="Raw model response for debugging (not logged in production)."
    )
    error: Optional[str] = None
    processing_status: str = Field(
        default="extracted",
        description="One of: extracted, extraction_failed, filtered_out"
    )
    model_used: Optional[str] = None
    latency_ms: Optional[float] = None
    opportunity_id: Optional[int] = None
