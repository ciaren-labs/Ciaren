# SPDX-License-Identifier: AGPL-3.0-only
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Schedule(Base):
    """A cron schedule that runs a flow automatically.

    The scheduler is a single in-process background loop that polls this table;
    ``next_run_at`` (naive UTC) is the single source of truth for when a schedule
    fires next, so schedules survive process restarts without a separate jobstore.
    """

    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("flows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Standard 5-field cron expression, interpreted in ``timezone``.
    cron: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    # Dataframe engine for fired runs; NULL falls back to settings.DEFAULT_ENGINE.
    engine: Mapped[str | None] = mapped_column(String(20), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # When True, a slot missed while the server was down fires once on startup;
    # when False, the scheduler skips straight to the next future slot.
    catch_up: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Retry policy: on a failed run, retry up to ``max_retries`` times before
    # falling back to the next cron slot, with exponential backoff seeded by
    # ``retry_delay_seconds``.
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    # Per-schedule run timeout override (seconds). NULL falls back to the global
    # RUN_TIMEOUT_SECONDS. ML retraining can far outlast typical ETL runs, so a
    # schedule can grant its runs more (or less) time without changing the default.
    run_timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Flow-parameter overrides applied to every run this schedule fires (name ->
    # value). NULL means "use each parameter's declared default". Lets one flow
    # back several schedules that differ only by parameter values.
    parameters_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # -- Runtime / observability state ---------------------------------
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Retries already used within the current cron slot (reset on success or when
    # the slot is exhausted and we advance to the next cron time).
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Set when the scheduler auto-disables a chronically failing schedule.
    disabled_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
