"""
Pydantic schemas for the background scheduler and pipeline status.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class SchedulerJobInfo(BaseModel):
    """Safe representation of an APScheduler job."""

    id: str
    name: str
    next_run_time: Optional[datetime] = None
    is_paused: bool = False
    trigger: Optional[str] = None


class SchedulerStatusResponse(BaseModel):
    """Current operational status and metrics of CareerMailScheduler."""

    is_running: bool
    is_paused: bool
    scheduler_enabled: bool
    sync_interval_minutes: int
    daily_digest_time: str
    timezone: str
    jobs: list[SchedulerJobInfo] = Field(default_factory=list)
    last_sync_started_at: Optional[datetime] = None
    last_sync_finished_at: Optional[datetime] = None
    last_sync_success: Optional[bool] = None
    last_sync_result: Optional[dict[str, Any]] = None
    last_digest_started_at: Optional[datetime] = None
    last_digest_finished_at: Optional[datetime] = None
    last_digest_success: Optional[bool] = None


class PipelineTriggerResponse(BaseModel):
    """Response returned when triggering pipeline jobs manually."""

    success: bool
    message: str
    details: Optional[dict[str, Any]] = None


class SchedulerActionResponse(BaseModel):
    """Response returned when pausing, resuming, or configuring the scheduler."""

    success: bool
    message: str
    is_paused: bool
