# SPDX-License-Identifier: AGPL-3.0-only
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.models.flow import Flow
from app.db.models.run import FlowRun
from app.db.models.schedule import Schedule
from app.engine.backends import available_engines
from app.scheduler import inflight
from app.scheduler.cron import compute_next_run, is_valid_cron, is_valid_timezone
from app.schemas.run import FlowRunCreate, FlowRunRead
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleRunBrief, ScheduleUpdate
from app.services.execution_service import ExecutionService

# How many of a schedule's most recent runs ride along on ScheduleRead, so the
# schedules list can show a run-history strip without a per-row request.
RECENT_RUNS_COUNT = 5


class ScheduleService:
    """CRUD for cron schedules plus manual ("run now") triggering.

    The background :class:`~app.scheduler.runner.SchedulerRunner` owns automatic
    firing; this service only manages the schedule rows and validates them.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    # -- Public API -----------------------------------------------------

    async def create(self, flow_id: str, data: ScheduleCreate) -> ScheduleRead:
        await self._get_flow(flow_id)
        self._validate(data.cron, data.timezone, data.engine)

        now = datetime.now(UTC).replace(tzinfo=None)
        schedule = Schedule(
            flow_id=flow_id,
            name=data.name,
            description=data.description,
            cron=data.cron,
            timezone=data.timezone,
            engine=data.engine,
            is_enabled=data.is_enabled,
            catch_up=data.catch_up,
            max_retries=data.max_retries,
            retry_delay_seconds=data.retry_delay_seconds,
            run_timeout_seconds=data.run_timeout_seconds,
            parameters_json=data.parameters,
            next_run_at=(compute_next_run(data.cron, now, data.timezone) if data.is_enabled else None),
        )
        self.db.add(schedule)
        await self.db.commit()
        await self.db.refresh(schedule)
        return ScheduleRead.model_validate(schedule)

    async def list_schedules(self, flow_id: str | None = None) -> list[ScheduleRead]:
        stmt = select(Schedule).order_by(Schedule.created_at.asc())
        if flow_id is not None:
            stmt = stmt.where(Schedule.flow_id == flow_id)
        result = await self.db.execute(stmt)
        schedules = result.scalars().all()
        recent = await self._recent_runs([s.id for s in schedules])
        return [self._to_read(s, recent) for s in schedules]

    async def get(self, schedule_id: str) -> ScheduleRead:
        schedule = await self._get_or_raise(schedule_id)
        return self._to_read(schedule, await self._recent_runs([schedule.id]))

    async def update(self, schedule_id: str, data: ScheduleUpdate) -> ScheduleRead:
        schedule = await self._get_or_raise(schedule_id)
        updates = data.model_dump(exclude_unset=True)

        cron = updates.get("cron", schedule.cron)
        timezone = updates.get("timezone", schedule.timezone)
        engine = updates.get("engine", schedule.engine)
        self._validate(cron, timezone, engine)

        # The request field `parameters` maps to the `parameters_json` column.
        if "parameters" in updates:
            schedule.parameters_json = updates.pop("parameters")

        for field, value in updates.items():
            setattr(schedule, field, value)

        # Re-enabling clears the failure streak so an auto-disabled schedule gets
        # a clean slate instead of tripping the threshold again immediately.
        if updates.get("is_enabled") is True:
            schedule.consecutive_failures = 0
            schedule.retry_count = 0
            schedule.disabled_reason = None

        # Recompute the next fire time when the cadence changed or the schedule
        # was just (re)enabled; clear it when disabled so the poller ignores it.
        if not schedule.is_enabled:
            schedule.next_run_at = None
        elif (
            "cron" in updates
            or "timezone" in updates
            or updates.get("is_enabled") is True
            or schedule.next_run_at is None
        ):
            now = datetime.now(UTC).replace(tzinfo=None)
            schedule.next_run_at = compute_next_run(schedule.cron, now, schedule.timezone)
        schedule.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.commit()
        await self.db.refresh(schedule)
        return self._to_read(schedule, await self._recent_runs([schedule.id]))

    async def delete(self, schedule_id: str) -> None:
        schedule = await self._get_or_raise(schedule_id)
        await self.db.delete(schedule)
        await self.db.commit()

    async def run_now(self, schedule_id: str) -> FlowRunRead:
        schedule = await self._get_or_raise(schedule_id)
        # Respect the same overlap guard the background scheduler uses: refuse to
        # start a manual run while this flow already has a scheduler-owned run in
        # flight, so "Run now" during an in-flight scheduled run can't double-run
        # the flow (which would duplicate writes to external SQL/storage sinks).
        if not inflight.try_acquire(schedule.flow_id):
            raise ConflictError("This flow already has a run in progress; wait for it to finish before running now.")
        try:
            run = await ExecutionService(self.db).run(
                schedule.flow_id,
                FlowRunCreate(engine=schedule.engine, parameters=schedule.parameters_json),
                schedule_id=schedule.id,
                trigger="schedule",
            )
            # Reflect the manual fire on the schedule, but leave next_run_at untouched
            # so an ad-hoc run doesn't shift the recurring cadence. A manual run stays
            # out of the auto-disable/retry machinery: a success clears the failure
            # streak (a good "it's fixed now" signal), but a failure never counts
            # toward auto-disabling — only the scheduler's own runs do.
            schedule.last_fired_at = datetime.now(UTC).replace(tzinfo=None)
            schedule.last_status = run.status
            schedule.last_run_id = run.id
            if run.status == "success":
                schedule.consecutive_failures = 0
                schedule.retry_count = 0
                schedule.disabled_reason = None
            await self.db.commit()
            return run
        finally:
            inflight.release(schedule.flow_id)

    # -- Internals ------------------------------------------------------

    def _to_read(self, schedule: Schedule, recent: dict[str, list[ScheduleRunBrief]]) -> ScheduleRead:
        read = ScheduleRead.model_validate(schedule)
        read.recent_runs = recent.get(schedule.id, [])
        return read

    async def _recent_runs(self, schedule_ids: list[str]) -> dict[str, list[ScheduleRunBrief]]:
        """The last RECENT_RUNS_COUNT runs per schedule (newest first), in one query."""
        if not schedule_ids:
            return {}
        rank = (
            func.row_number()
            .over(partition_by=FlowRun.schedule_id, order_by=(FlowRun.created_at.desc(), FlowRun.id.desc()))
            .label("rank")
        )
        ranked = (
            select(FlowRun.id, FlowRun.schedule_id, FlowRun.status, FlowRun.created_at, rank)
            .where(FlowRun.schedule_id.in_(schedule_ids))
            .subquery()
        )
        stmt = select(ranked).where(ranked.c.rank <= RECENT_RUNS_COUNT).order_by(ranked.c.schedule_id, ranked.c.rank)
        result = await self.db.execute(stmt)
        recent: dict[str, list[ScheduleRunBrief]] = {}
        for row in result.all():
            recent.setdefault(row.schedule_id, []).append(
                ScheduleRunBrief(id=row.id, status=row.status, created_at=row.created_at)
            )
        return recent

    def _validate(self, cron: str, timezone: str, engine: str | None) -> None:
        if not is_valid_cron(cron):
            raise ValidationError(f"Invalid cron expression: '{cron}'.")
        if not is_valid_timezone(timezone):
            raise ValidationError(f"Unknown timezone: '{timezone}'.")
        if engine is not None and engine not in available_engines():
            raise ValidationError(f"Unknown engine '{engine}'. Available: {', '.join(available_engines())}.")
        # ``is_valid_cron`` accepts syntactically-valid expressions that never
        # resolve to a real date (e.g. "0 0 30 2 *" — 30 February). Probe an
        # actual next-run computation so those surface as a clean 400 here rather
        # than an uncaught 500 from ``compute_next_run`` at the call sites below.
        now = datetime.now(UTC).replace(tzinfo=None)
        try:
            compute_next_run(cron, now, timezone)
        except ValueError as exc:
            raise ValidationError(f"Cron expression '{cron}' never resolves to a real date.") from exc

    async def _get_flow(self, flow_id: str) -> Flow:
        result = await self.db.execute(select(Flow).where(Flow.id == flow_id))
        flow = result.scalar_one_or_none()
        if flow is None:
            raise NotFoundError("Flow", flow_id)
        return flow

    async def _get_or_raise(self, schedule_id: str) -> Schedule:
        result = await self.db.execute(select(Schedule).where(Schedule.id == schedule_id))
        schedule = result.scalar_one_or_none()
        if schedule is None:
            raise NotFoundError("Schedule", schedule_id)
        return schedule
