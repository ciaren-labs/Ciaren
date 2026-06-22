from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.flow import Flow
from app.db.models.schedule import Schedule
from app.engine.backends import available_engines
from app.scheduler.cron import compute_next_run, is_valid_cron, is_valid_timezone
from app.schemas.run import FlowRunCreate, FlowRunRead
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate
from app.services.execution_service import ExecutionService


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

        schedule = Schedule(
            flow_id=flow_id,
            name=data.name,
            description=data.description,
            cron=data.cron,
            timezone=data.timezone,
            engine=data.engine,
            input_dataset_id=data.input_dataset_id,
            enabled=data.enabled,
            catch_up=data.catch_up,
            next_run_at=(
                compute_next_run(data.cron, datetime.utcnow(), data.timezone)
                if data.enabled
                else None
            ),
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
        return [ScheduleRead.model_validate(s) for s in result.scalars().all()]

    async def get(self, schedule_id: str) -> ScheduleRead:
        return ScheduleRead.model_validate(await self._get_or_raise(schedule_id))

    async def update(self, schedule_id: str, data: ScheduleUpdate) -> ScheduleRead:
        schedule = await self._get_or_raise(schedule_id)
        updates = data.model_dump(exclude_unset=True)

        cron = updates.get("cron", schedule.cron)
        timezone = updates.get("timezone", schedule.timezone)
        engine = updates.get("engine", schedule.engine)
        self._validate(cron, timezone, engine)

        for field, value in updates.items():
            setattr(schedule, field, value)

        # Recompute the next fire time when the cadence changed or the schedule
        # was just (re)enabled; clear it when disabled so the poller ignores it.
        if not schedule.enabled:
            schedule.next_run_at = None
        elif (
            "cron" in updates
            or "timezone" in updates
            or updates.get("enabled") is True
            or schedule.next_run_at is None
        ):
            schedule.next_run_at = compute_next_run(
                schedule.cron, datetime.utcnow(), schedule.timezone
            )
        schedule.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(schedule)
        return ScheduleRead.model_validate(schedule)

    async def delete(self, schedule_id: str) -> None:
        schedule = await self._get_or_raise(schedule_id)
        await self.db.delete(schedule)
        await self.db.commit()

    async def run_now(self, schedule_id: str) -> FlowRunRead:
        schedule = await self._get_or_raise(schedule_id)
        run = await ExecutionService(self.db).run(
            schedule.flow_id,
            FlowRunCreate(input_dataset_id=schedule.input_dataset_id, engine=schedule.engine),
            schedule_id=schedule.id,
            trigger="schedule",
        )
        # Reflect the manual fire on the schedule, but leave next_run_at untouched
        # so an ad-hoc run doesn't shift the recurring cadence.
        schedule.last_fired_at = datetime.utcnow()
        schedule.last_status = run.status
        schedule.last_run_id = run.id
        schedule.consecutive_failures = (
            0 if run.status == "success" else schedule.consecutive_failures + 1
        )
        await self.db.commit()
        return run

    # -- Internals ------------------------------------------------------

    def _validate(self, cron: str, timezone: str, engine: str | None) -> None:
        if not is_valid_cron(cron):
            raise ValidationError(f"Invalid cron expression: '{cron}'.")
        if not is_valid_timezone(timezone):
            raise ValidationError(f"Unknown timezone: '{timezone}'.")
        if engine is not None and engine not in available_engines():
            raise ValidationError(
                f"Unknown engine '{engine}'. Available: {', '.join(available_engines())}."
            )

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
