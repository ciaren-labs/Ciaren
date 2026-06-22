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
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.models.schedule import Schedule
from app.scheduler.cron import compute_next_run
from app.schemas.run import FlowRunCreate
from app.services.execution_service import ExecutionService

logger = logging.getLogger("flowframe.scheduler")


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
        await self._reconcile_on_startup()
        self._task = asyncio.create_task(self._loop(), name="flowframe-scheduler")
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
        interval = max(1, self._settings.SCHEDULER_POLL_INTERVAL_SECONDS)
        while not self._stopped.is_set():
            try:
                await self._tick()
            except Exception:  # noqa: BLE001 - the loop must never die
                logger.exception("Scheduler tick failed")
            try:
                # Sleep until the next poll, but wake immediately on shutdown.
                await asyncio.wait_for(self._stopped.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def _tick(self) -> None:
        now = datetime.utcnow()
        async with self._session_factory() as db:
            result = await db.execute(
                select(Schedule).where(
                    Schedule.enabled.is_(True),
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
                if schedule is None or not schedule.enabled:
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
                FlowRunCreate(input_dataset_id=schedule.input_dataset_id, engine=schedule.engine),
                schedule_id=schedule.id,
                trigger="schedule",
            )
            status, run_id = run.status, run.id
        except Exception:  # noqa: BLE001 - record on the schedule, then re-raise nothing
            logger.exception("Run failed for schedule %s (flow %s)", schedule.id, schedule.flow_id)
        finally:
            schedule.last_fired_at = datetime.utcnow()
            schedule.last_status = status
            schedule.last_run_id = run_id
            schedule.consecutive_failures = (
                0 if status == "success" else schedule.consecutive_failures + 1
            )
            # Advance to the next future slot regardless of outcome.
            schedule.next_run_at = compute_next_run(
                schedule.cron, datetime.utcnow(), schedule.timezone
            )
            await db.commit()

    async def _reconcile_on_startup(self) -> None:
        """Set ``next_run_at`` for new schedules and apply the catch-up policy for
        slots missed while the server was down.

        * ``next_run_at is None`` (just created, or never scheduled): schedule it.
        * missed slot and ``catch_up`` is False: skip to the next future slot.
        * missed slot and ``catch_up`` is True: leave it — the first tick fires it
          once, then advances to the next future slot.
        """
        now = datetime.utcnow()
        async with self._session_factory() as db:
            result = await db.execute(select(Schedule).where(Schedule.enabled.is_(True)))
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
