"""
CareerMail AI — Device Management Endpoints.

Handles idempotent FCM device token registration, querying, and deactivation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import DeviceToken
from app.schemas.device import DeviceListResponse, DeviceRegisterRequest, DeviceResponse
from app.utils.logging import get_logger, log_event

logger = get_logger("api.devices")

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post(
    "/register",
    response_model=DeviceResponse,
    status_code=status.HTTP_200_OK,
    summary="Register or reactivate an FCM device token",
)
def register_device(
    payload: DeviceRegisterRequest,
    db: Session = Depends(get_db),
) -> DeviceResponse:
    """Register a new device token or idempotently reactivate an existing token.

    If the token exists:
      • Reactivates (is_active = True)
      • Updates last_seen_at and device metadata
      • Does not insert a duplicate row.
    """
    user_id = 1  # Default single-user MVP
    now = datetime.now(timezone.utc)

    device = (
        db.query(DeviceToken)
        .filter(DeviceToken.fcm_token == payload.fcm_token)
        .first()
    )

    if device:
        # Idempotent reactivation and update
        device.is_active = True
        device.last_seen_at = now
        device.device_type = payload.device_type
        if payload.device_name is not None:
            device.device_name = payload.device_name

        db.commit()
        db.refresh(device)

        log_event(
            logger,
            "DEVICE_REACTIVATED",
            device_id=device.id,
            user_id=device.user_id,
            device_type=device.device_type,
        )
        return DeviceResponse.from_orm_model(device)

    # New registration
    new_device = DeviceToken(
        user_id=user_id,
        fcm_token=payload.fcm_token,
        device_type=payload.device_type,
        device_name=payload.device_name,
        is_active=True,
        created_at=now,
        last_seen_at=now,
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)

    log_event(
        logger,
        "DEVICE_REGISTERED",
        device_id=new_device.id,
        user_id=new_device.user_id,
        device_type=new_device.device_type,
    )
    return DeviceResponse.from_orm_model(new_device)


@router.get(
    "",
    response_model=DeviceListResponse,
    summary="List registered devices",
)
def list_devices(
    db: Session = Depends(get_db),
) -> DeviceListResponse:
    """Retrieve all registered device tokens for the user."""
    user_id = 1
    devices = (
        db.query(DeviceToken)
        .filter(DeviceToken.user_id == user_id)
        .order_by(DeviceToken.last_seen_at.desc())
        .all()
    )

    return DeviceListResponse(
        devices=[DeviceResponse.from_orm_model(d) for d in devices],
        total=len(devices),
    )


@router.delete(
    "/{token}",
    summary="Deactivate a device token",
)
def deactivate_device(
    token: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Deactivate an FCM device token without destroying historical references."""
    user_id = 1
    device = (
        db.query(DeviceToken)
        .filter(DeviceToken.user_id == user_id, DeviceToken.fcm_token == token)
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device token not found.",
        )

    device.is_active = False
    db.commit()

    log_event(
        logger,
        "DEVICE_DEACTIVATED",
        device_id=device.id,
        user_id=user_id,
    )
    return {
        "message": "Device token deactivated successfully.",
        "deactivated": True,
    }
