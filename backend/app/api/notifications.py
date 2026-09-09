"""
CareerMail AI — Notification Endpoints.

Provides APIs to trigger test notifications and query paginated notification history.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.notification import NotificationLog
from app.schemas.notification import (
    NotificationHistoryResponse,
    NotificationLogResponse,
    NotificationSendResult,
    TestNotificationRequest,
)
from app.services.notifications.dispatcher import get_notification_dispatcher
from app.utils.logging import get_logger

logger = get_logger("api.notifications")

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post(
    "/test",
    response_model=NotificationSendResult,
    status_code=status.HTTP_200_OK,
    summary="Send an on-demand test notification",
)
def send_test_notification(
    payload: TestNotificationRequest,
    db: Session = Depends(get_db),
) -> NotificationSendResult:
    """Send a test push notification to all active devices.

    Operates in live FCM mode if credentials are configured,
    or mock/dry-run mode if credentials are not present.
    """
    user_id = 1
    dispatcher = get_notification_dispatcher()

    result, _ = dispatcher.notify_test(
        db=db,
        user_id=user_id,
        title=payload.title,
        body=payload.body,
        opportunity_id=payload.opportunity_id,
    )
    return result


@router.get(
    "/history",
    response_model=NotificationHistoryResponse,
    summary="Get paginated notification history",
)
def get_notification_history(
    page: int = Query(1, ge=1, description="Page number starting at 1"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    notification_type: Optional[str] = Query(None, description="Optional type filter"),
    db: Session = Depends(get_db),
) -> NotificationHistoryResponse:
    """Retrieve paginated notification audit log."""
    user_id = 1
    query = db.query(NotificationLog).filter(NotificationLog.user_id == user_id)

    if notification_type:
        query = query.filter(NotificationLog.notification_type == notification_type)

    total = query.count()
    items = (
        query.order_by(NotificationLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    response_items = [
        NotificationLogResponse(
            id=item.id,
            user_id=item.user_id,
            opportunity_id=item.opportunity_id,
            notification_type=item.notification_type,
            title=item.title,
            body=item.body,
            data_payload=item.data_payload or {},
            status=item.status,
            fcm_message_id=item.fcm_message_id,
            created_at=item.created_at,
        )
        for item in items
    ]

    return NotificationHistoryResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
    )
