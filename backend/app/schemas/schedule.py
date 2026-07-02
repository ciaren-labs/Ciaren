# SPDX-License-Identifier: AGPL-3.0-only
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScheduleCreate(BaseModel):
    cron: str = Field(..., min_length=1, max_length=255)
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    timezone: str = Field("UTC", max_length=64)
    # None falls back to the server's DEFAULT_ENGINE when the run fires.
    engine: str | None = None
    is_enabled: bool = True
    catch_up: bool = False
    max_retries: int = Field(0, ge=0, le=10)
    retry_delay_seconds: int = Field(60, ge=1)
    # Per-schedule run timeout (seconds, 0 = no limit). None uses RUN_TIMEOUT_SECONDS.
    run_timeout_seconds: int | None = Field(None, ge=0)
    # Flow-parameter overrides applied to every run this schedule fires.
    parameters: dict[str, Any] | None = None


class ScheduleUpdate(BaseModel):
    cron: str | None = Field(None, min_length=1, max_length=255)
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    timezone: str | None = Field(None, max_length=64)
    engine: str | None = None
    is_enabled: bool | None = None
    catch_up: bool | None = None
    max_retries: int | None = Field(None, ge=0, le=10)
    retry_delay_seconds: int | None = Field(None, ge=1)
    run_timeout_seconds: int | None = Field(None, ge=0)
    parameters: dict[str, Any] | None = None


class ScheduleRunBrief(BaseModel):
    """A minimal run reference for the recent-run history strip on the schedules list."""

    id: str
    status: str
    created_at: datetime


class ScheduleRead(BaseModel):
    id: str
    flow_id: str
    name: str | None
    description: str | None
    cron: str
    timezone: str
    engine: str | None
    is_enabled: bool
    catch_up: bool
    max_retries: int
    retry_delay_seconds: int
    run_timeout_seconds: int | None
    parameters: dict[str, Any] | None = Field(None, validation_alias="parameters_json")
    next_run_at: datetime | None
    last_fired_at: datetime | None
    last_run_id: str | None
    last_status: str | None
    consecutive_failures: int
    retry_count: int
    disabled_reason: str | None
    # Most recent runs this schedule fired (newest first), for the history strip.
    recent_runs: list[ScheduleRunBrief] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}
