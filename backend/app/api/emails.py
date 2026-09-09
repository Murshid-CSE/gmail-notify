"""
CareerMail AI — Email API routes.

GET /emails       → Paginated list of stored emails.
GET /emails/{id}  → Full email detail (includes body).
"""

from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.email_message import EmailMessage
from app.schemas.email import EmailDetailResponse, EmailListResponse, EmailResponse
from app.utils.logging import get_logger

logger = get_logger("api.emails")

router = APIRouter(prefix="/emails", tags=["Emails"])


@router.get(
    "",
    response_model=EmailListResponse,
    summary="List stored emails",
)
def list_emails(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    account_id: Optional[int] = Query(default=None, description="Filter by account"),
    processing_status: Optional[str] = Query(default=None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """Return paginated list of stored emails.

    Supports filtering by account_id and processing_status.
    Ordered by received_at descending (newest first).
    """
    query = db.query(EmailMessage)

    if account_id is not None:
        query = query.filter(EmailMessage.account_id == account_id)
    if processing_status is not None:
        query = query.filter(EmailMessage.processing_status == processing_status)

    total_items = query.count()
    total_pages = max(1, math.ceil(total_items / page_size))

    items = (
        query.order_by(EmailMessage.received_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return EmailListResponse(
        items=[EmailResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@router.get(
    "/{email_id}",
    response_model=EmailDetailResponse,
    summary="Get email detail",
)
def get_email(email_id: int, db: Session = Depends(get_db)):
    """Return full email detail including body text."""
    email = db.query(EmailMessage).filter(EmailMessage.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found.")

    return EmailDetailResponse.model_validate(email)
