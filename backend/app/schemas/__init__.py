"""CareerMail AI — API Schemas."""

from app.schemas.common import HealthResponse, PaginatedResponse, ErrorResponse
from app.schemas.account import (
    AccountResponse,
    AccountListResponse,
    OAuthStartResponse,
    SyncResponse,
)
from app.schemas.email import EmailResponse, EmailListResponse, EmailDetailResponse
from app.schemas.opportunity import (
    OpportunityResponse,
    OpportunityDetailResponse,
    StatusHistoryResponse,
    SourceEmailReference,
)

__all__ = [
    "HealthResponse",
    "PaginatedResponse",
    "ErrorResponse",
    "AccountResponse",
    "AccountListResponse",
    "OAuthStartResponse",
    "SyncResponse",
    "EmailResponse",
    "EmailListResponse",
    "EmailDetailResponse",
    "OpportunityResponse",
    "OpportunityDetailResponse",
    "StatusHistoryResponse",
    "SourceEmailReference",
]
