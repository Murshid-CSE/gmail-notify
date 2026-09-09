"""
CareerMail AI — Daily Digest API Route.

GET /digest/today — Personalized daily briefing aggregating new opportunities,
status transitions, deadlines, and urgent action items.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.digest import DailyDigestResponse
from app.services.digest import build_daily_digest
from app.utils.logging import get_logger

logger = get_logger("api.digest")

router = APIRouter(prefix="/digest", tags=["digest"])


@router.get("/today", response_model=DailyDigestResponse)
def get_daily_digest(
    tz: Optional[str] = Query(None, description="Timezone name (e.g. Asia/Kolkata, America/New_York)"),
    db: Session = Depends(get_db),
):
    """Retrieve today's career digest briefing for the user.

    Aggregates new opportunities, status transitions, deadlines, and urgent actions.
    """
    return build_daily_digest(db, user_id=1, tz_name=tz)
