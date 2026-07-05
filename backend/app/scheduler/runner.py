# SPDX-License-Identifier: AGPL-3.0-only
"""In-process cron scheduler.

A single background asyncio task polls the ``schedules`` table and fires due
schedules. Design goals (per the project's "light and simple, but robust"
brief):

* **Single source of truth** — schedule state lives in our own DB table, so the
  scheduler survives restarts with no separate jobstore to keep in sync.
* **Isolation** — one failing schedule (or a crash mid-tick) never kills the
  loop; every fire is wrapped and logged.
* **No event-loop starvation** — the actual dataframe compute runs in a worker
  thread (see ``ExecutionService.run``); here we only orchestrate.
* **No overlap / no stampede** — a schedule whose previous run is still in
  flight is skipped, and a semaphore caps concurrent runs.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.notifications import notify_in_background
from app.db.models.run import FlowRun
from app.db.models.schedule import Schedule
from app.scheduler.cron import compute_next_run
from app.schemas.run import FlowRunCreate
from app.services.execution_service import ExecutionService

logger = logging.getLogger("ciaren.scheduler")

# Upper bound on exponential backoff so a long-failing schedule still retries
# roughly hourly rather than drifting to absurd delays.
_MAX_BACKOFF_SECONDS = 3600


class SchedulerRunner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._stopped = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._sem = asyncio.Semaphore(max(1, settings.SCHEDULER_MAX_CONCURRENT_RUNS))
        # Overlap guard: schedule ids whose run is currently in flight.
        self._in_flight: set[str] = set()
        # Keep strong refs to fire tasks so they aren't garbage-collected.
        self._fire_tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        await self._recover_orphaned_runs()
        await self._reconcile_on_startup()
        self._task = asyncio.create_task(self._loop(), name="ciaren-scheduler")
        logger.info(
            "Scheduler started (poll=%ss, max_concurrent=%s)",
            self._settings.SCHEDULER_POLL_INTERVAL_SECONDS,
            self._settings.SCHEDULER_MAX_CONCURRENT_RUNS,
        )

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        if self._fire_tasks:
            await asyncio.gather(*self._fire_tasks, return_exceptions=True)
        logger.info("Scheduler stopped")

    # -- Internals ------------------------------------------------------

    async def _loop(self) -> None:
        while not self._stopped.is_set():
            try:
                await self._tick()
            except Exception:  # noqa: BLE001 - the loop must never die
                logger.exception("Scheduler tick failed")
            # Read the interval each iteration so a runtime override from the
            # Settings page takes effect on the next tick, not after a restart.
            interval = max(1, self._settings.SCHEDULER_POLL_INTERVAL_SECONDS)
            try:
                # Sleep until the next poll, but wake immediately on shutdown.
                await asyncio.wait_for(self._stopped.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def _tick(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        async with self._session_factory() as db:
            result = await db.execute(
                select(Schedule).where(
                    Schedule.is_enabled.is_(True),
                    Schedule.next_run_at.is_not(None),
                    Schedule.next_run_at <= now,
                )
            )
            due = list(result.scalars().all())

        for schedule in due:
            if schedule.id in self._in_flight:
                continue  # previous run still in flight — skip this slot
            self._in_flight.add(schedule.id)
            task = asyncio.create_task(self._fire(schedule.id))
            self._fire_tasks.add(task)
            task.add_done_callback(self._fire_tasks.discard)

    async def _fire(self, schedule_id: str) -> None:
        try:
            async with self._sem, self._session_factory() as db:
                schedule = await db.get(Schedule, schedule_id)
                if schedule is None or not schedule.is_enabled:
                    return
                await self._execute(db, schedule)
        except Exception:  # noqa: BLE001 - never let a fire crash the scheduler
            logger.exception("Scheduled fire failed for schedule %s", schedule_id)
        finally:
            self._in_flight.discard(schedule_id)

    async def _execute(self, db: AsyncSession, schedule: Schedule) -> None:
        status = "failed"
        run_id: str | None = None
        try:
            run = await ExecutionService(db).run(
                schedule.flow_id,
                FlowRunCreate(engine=schedule.engine, parameters=schedule.parameters_json),
                schedule_id=schedule.id,
                trigger="schedule",
            )
            status, run_id = run.status, run.id
        except Exception:  # noqa: BLE001 - record on the schedule, then re-raise nothing
            logger.exception("Run failed for schedule %s (flow %s)", schedule.id, schedule.flow_id)
        finally:
            schedule.last_fired_at = datetime.now(UTC).replace(tzinfo=None)
            schedule.last_status = status
            schedule.last_run_id = run_id
            if status == "success":
                self._on_success(schedule)
            elif status == "cancelled":
                # A user stopping a run is not a flow failure: don't count it
                # toward auto-disable — just advance to the next cron slot.
                now = datetime.now(UTC).replace(tzinfo=None)
                schedule.next_run_at = compute_next_run(schedule.cron, now, schedule.timezone)
            else:
                self._on_failure(schedule)
            await db.commit()
            if status not in ("success", "cancelled") and not schedule.is_enabled and schedule.disabled_reason:
                # The failed run itself already notified (run_failed); this is
                # the louder signal that the schedule gave up entirely.
                notify_in_background(
                    "schedule_auto_disabled",
                    {
                        "schedule_id": schedule.id,
                        "flow_id": schedule.flow_id,
                        "reason": schedule.disabled_reason,
                        "consecutive_failures": schedule.consecutive_failures,
                        "last_run_id": run_id,
                    },
                )

    def _on_success(self, schedule: Schedule) -> None:
        schedule.consecutive_failures = 0
        schedule.retry_count = 0
        schedule.disabled_reason = None
        now = datetime.now(UTC).replace(tzinfo=None)
        schedule.next_run_at = compute_next_run(schedule.cron, now, schedule.timezone)

    def _on_failure(self, schedule: Schedule) -> None:
        """Decide what happens after a failed run: auto-disable (wins), retry with
        backoff, or fall back to the next cron slot once retries are exhausted."""
        schedule.consecutive_failures += 1
        threshold = self._settings.SCHEDULER_MAX_CONSECUTIVE_FAILURES

        if threshold > 0 and schedule.consecutive_failures >= threshold:
            schedule.is_enabled = False
            schedule.next_run_at = None
            schedule.retry_count = 0
            schedule.disabled_reason = f"Auto-disabled after {schedule.consecutive_failures} consecutive failures"
            logger.warning(
                "Schedule %s auto-disabled after %s consecutive failures",
                schedule.id,
                schedule.consecutive_failures,
            )
        elif schedule.retry_count < schedule.max_retries:
            schedule.retry_count += 1
            delay = self._backoff_seconds(schedule.retry_delay_seconds, schedule.retry_count)
            schedule.next_run_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=delay)
        else:
            schedule.retry_count = 0
            now = datetime.now(UTC).replace(tzinfo=None)
            schedule.next_run_at = compute_next_run(schedule.cron, now, schedule.timezone)

    @staticmethod
    def _backoff_seconds(base: int, attempt: int) -> int:
        """Exponential backoff: base * 2**(attempt-1), capped."""
        return min(base * (1 << (attempt - 1)), _MAX_BACKOFF_SECONDS)

    async def _recover_orphaned_runs(self) -> None:
        """Mark runs still ``running`` at startup as failed.

        The app is single-process, so any run left in ``running`` was interrupted
        by a crash/restart — it can never complete. Clearing them keeps the run
        history honest and frees the (in-memory) overlap state implicitly.
        """
        now = datetime.now(UTC).replace(tzinfo=None)
        async with self._session_factory() as db:
            result = cast(
                CursorResult[Any],
                await db.execute(
                    update(FlowRun)
                    .where(FlowRun.status == "running")
                    .values(
                        status="failed",
                        error_message="Run interrupted by a server restart.",
                        finished_at=now,
                    )
                ),
            )
            if result.rowcount:
                logger.warning("Recovered %s orphaned run(s) after restart", result.rowcount)
            await db.commit()

    async def _reconcile_on_startup(self) -> None:
        """Set ``next_run_at`` for new schedules and apply the catch-up policy for
        slots missed while the server was down.

        * ``next_run_at is None`` (just created, or never scheduled): schedule it.
        * missed slot and ``catch_up`` is False: skip to the next future slot.
        * missed slot and ``catch_up`` is True: leave it — the first tick fires it
          once, then advances to the next future slot.
        """
        now = datetime.now(UTC).replace(tzinfo=None)
        async with self._session_factory() as db:
            result = await db.execute(select(Schedule).where(Schedule.is_enabled.is_(True)))
            changed = False
            for schedule in result.scalars().all():
                if schedule.next_run_at is None:
                    schedule.next_run_at = compute_next_run(schedule.cron, now, schedule.timezone)
                    changed = True
                elif schedule.next_run_at <= now and not schedule.catch_up:
                    schedule.next_run_at = compute_next_run(schedule.cron, now, schedule.timezone)
                    changed = True
            if changed:
                await db.commit()
