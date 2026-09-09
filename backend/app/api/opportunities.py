"""
CareerMail AI — Opportunities API Routes.

GET /opportunities       — Paginated list of opportunities with filtering.
GET /opportunities/{id}  — Detailed opportunity view with source emails and status history.
"""

from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.opportunity import Opportunity
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.opportunity import (
    OpportunityDetailResponse,
    OpportunityResponse,
    SourceEmailReference,
    StatusHistoryResponse,
)
from app.services.opportunities.manager import compute_deadline_state
from app.utils.logging import get_logger

logger = get_logger("api.opportunities")

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _build_opportunity_response(opp: Opportunity) -> OpportunityResponse:
    """Helper to convert an Opportunity ORM model to OpportunityResponse with computed deadline metrics."""
    deadline_state = compute_deadline_state(opp.deadline)

    return OpportunityResponse(
        id=opp.id,
        category=opp.category,
        title=opp.title,
        organization=opp.organization,
        description=opp.description,
        status=opp.status,
        round_name=opp.round_name,
        deadline=opp.deadline,
        event_date=opp.event_date,
        location=opp.location,
        eligibility=opp.eligibility,
        apply_url=opp.apply_url,
        event_url=opp.event_url,
        action_required=getattr(opp, "action_required", False),
        action=getattr(opp, "action", None),
        priority=opp.priority,
        confidence=opp.confidence,
        first_seen_at=opp.first_seen_at,
        last_updated_at=opp.last_updated_at,
        days_remaining=deadline_state["days_remaining"],
        hours_remaining=deadline_state["hours_remaining"],
        is_overdue=deadline_state["is_overdue"],
        is_due_today=deadline_state["is_due_today"],
        is_due_tomorrow=deadline_state["is_due_tomorrow"],
    )


@router.get("", response_model=PaginatedResponse[OpportunityResponse])
def list_opportunities(
    category: Optional[str] = Query(None, description="Filter by category (hackathon, internship, etc.)"),
    status: Optional[str] = Query(None, description="Filter by status (registered, shortlisted, next_round, etc.)"),
    priority: Optional[str] = Query(None, description="Filter by priority (low, medium, high, critical)"),
    search: Optional[str] = Query(None, description="Search term in title or organization"),
    sort_by: str = Query("updated_at", description="Sort field: deadline, created_at, updated_at, priority, title"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List opportunities with filtering, sorting, and pagination."""
    valid_sort_fields = {"deadline", "created_at", "updated_at", "priority", "title"}
    if sort_by not in valid_sort_fields:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sort_by. Allowed: {sorted(valid_sort_fields)}",
        )
    if sort_order not in ("asc", "desc"):
        raise HTTPException(
            status_code=422,
            detail="Invalid sort_order. Allowed: asc, desc",
        )

    query = db.query(Opportunity)

    if category:
        query = query.filter(Opportunity.category == category)
    if status:
        query = query.filter(Opportunity.status == status)
    if priority:
        query = query.filter(Opportunity.priority == priority)
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            (Opportunity.title.ilike(search_pattern))
            | (Opportunity.organization.ilike(search_pattern))
        )

    # Safe column-mapped sorting (no raw SQL injection risk)
    if sort_by == "deadline":
        col = (
            Opportunity.deadline.asc().nulls_last()
            if sort_order == "asc"
            else Opportunity.deadline.desc().nulls_last()
        )
    elif sort_by == "created_at":
        col = Opportunity.created_at.asc() if sort_order == "asc" else Opportunity.created_at.desc()
    elif sort_by == "updated_at":
        col = Opportunity.last_updated_at.asc() if sort_order == "asc" else Opportunity.last_updated_at.desc()
    elif sort_by == "priority":
        priority_order = case(
            {"critical": 4, "high": 3, "medium": 2, "low": 1},
            value=Opportunity.priority,
            else_=0,
        )
        col = priority_order.asc() if sort_order == "asc" else priority_order.desc()
    elif sort_by == "title":
        col = Opportunity.title.asc() if sort_order == "asc" else Opportunity.title.desc()

    total_items = query.count()
    total_pages = max(1, math.ceil(total_items / page_size))

    opportunities = (
        query.order_by(col)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [_build_opportunity_response(opp) for opp in opportunities]

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        ),
    )


@router.get("/{opportunity_id}", response_model=OpportunityDetailResponse)
def get_opportunity_detail(
    opportunity_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve full details of an opportunity including source emails and status history."""
    opp = (
        db.query(Opportunity)
        .options(
            joinedload(Opportunity.emails),
            joinedload(Opportunity.status_history),
        )
        .filter(Opportunity.id == opportunity_id)
        .first()
    )

    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    base = _build_opportunity_response(opp)

    source_emails = [
        SourceEmailReference(
            id=email.id,
            gmail_message_id=email.gmail_message_id,
            subject=email.subject,
            received_at=email.received_at,
            sender=email.sender,
        )
        for email in opp.emails
    ]

    status_history = [
        StatusHistoryResponse(
            id=h.id,
            old_status=h.old_status,
            new_status=h.new_status,
            source_email_id=h.source_email_id,
            changed_at=h.changed_at,
        )
        for h in opp.status_history
    ]

    return OpportunityDetailResponse(
        **base.model_dump(),
        source_emails=source_emails,
        status_history=status_history,
    )
