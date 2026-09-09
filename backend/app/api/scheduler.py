"""
CareerMail AI — Scheduler API Endpoints.

Provides operational visibility and manual execution triggers for background
synchronization and daily career briefs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.scheduler import (
    PipelineTriggerResponse,
    SchedulerActionResponse,
    SchedulerStatusResponse,
)
from app.services.scheduler import CareerMailScheduler, get_scheduler
from app.utils.logging import get_logger

logger = get_logger("api.scheduler")

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.get(
    "/status",
    response_model=SchedulerStatusResponse,
    summary="Get background scheduler operational status",
)
def get_scheduler_status(
    scheduler: CareerMailScheduler = Depends(get_scheduler),
) -> SchedulerStatusResponse:
    """Retrieve operational status, registered jobs, next run times, and execution metrics."""
    status_data = scheduler.get_status()
    return SchedulerStatusResponse(**status_data)


@router.post(
    "/trigger/sync",
    response_model=PipelineTriggerResponse,
    summary="Trigger the full sync & extraction pipeline immediately",
)
def trigger_sync_pipeline(
    scheduler: CareerMailScheduler = Depends(get_scheduler),
) -> PipelineTriggerResponse:
    """Manually invoke the centralized Gmail sync, AI extraction, and deadline alert pipeline.

    Idempotent and concurrency-protected against overlapping runs.
    """
    result = scheduler.trigger_sync_job_now()
    return PipelineTriggerResponse(
        success=result.get("success", False),
        message=result.get("message", "Pipeline triggered"),
        details=result.get("details"),
    )


@router.post(
    "/trigger/digest",
    response_model=PipelineTriggerResponse,
    summary="Trigger the daily career brief immediately",
)
def trigger_daily_digest(
    user_id: int = Query(1, description="Target user ID for the daily digest"),
    scheduler: CareerMailScheduler = Depends(get_scheduler),
) -> PipelineTriggerResponse:
    """Manually generate today's daily career digest and dispatch a push notification."""
    result = scheduler.trigger_digest_job_now(user_id=user_id)
    return PipelineTriggerResponse(
        success=result.get("success", False),
        message=result.get("message", "Daily digest triggered"),
        details=result.get("details"),
    )


@router.post(
    "/pause",
    response_model=SchedulerActionResponse,
    summary="Pause scheduled background jobs",
)
def pause_scheduler(
    scheduler: CareerMailScheduler = Depends(get_scheduler),
) -> SchedulerActionResponse:
    """Pause the background scheduler. Jobs will not execute until resumed."""
    if not scheduler.is_running:
        return SchedulerActionResponse(
            success=False,
            message="Scheduler is not running",
            is_paused=scheduler.is_paused,
        )

    scheduler.pause()
    return SchedulerActionResponse(
        success=True,
        message="Background scheduler paused",
        is_paused=scheduler.is_paused,
    )


@router.post(
    "/resume",
    response_model=SchedulerActionResponse,
    summary="Resume scheduled background jobs",
)
def resume_scheduler(
    scheduler: CareerMailScheduler = Depends(get_scheduler),
) -> SchedulerActionResponse:
    """Resume the background scheduler after being paused."""
    if not scheduler.is_running:
        return SchedulerActionResponse(
            success=False,
            message="Scheduler is not running",
            is_paused=scheduler.is_paused,
        )

    scheduler.resume()
    return SchedulerActionResponse(
        success=True,
        message="Background scheduler resumed",
        is_paused=scheduler.is_paused,
    )
