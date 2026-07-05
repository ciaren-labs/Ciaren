"""Tests for the background SchedulerRunner.

These drive the runner's internals directly (rather than the polling loop) for
determinism: reconcile/catch-up logic, the overlap guard, and one real fired run
end-to-end.
"""

import io
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.models.flow import Flow
from app.db.models.run import FlowRun
from app.db.models.schedule import Schedule
from app.scheduler.runner import SchedulerRunner
from app.services.project_service import ProjectService


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def _make_schedule(
    factory: async_sessionmaker[AsyncSession],
    *,
    cron: str = "0 9 * * *",
    timezone: str = "UTC",
    **kwargs: Any,
) -> str:
    async with factory() as db:
        pid = (await ProjectService(db).ensure_default()).id
        flow = Flow(name="f", project_id=pid, graph_json={})
        db.add(flow)
        await db.flush()
        schedule = Schedule(flow_id=flow.id, cron=cron, timezone=timezone, **kwargs)
        db.add(schedule)
        await db.commit()
        return schedule.id


async def test_reconcile_sets_next_run_when_missing(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    sid = await _make_schedule(factory, next_run_at=None, is_enabled=True)

    await SchedulerRunner(factory, get_settings())._reconcile_on_startup()

    async with factory() as db:
        schedule = await db.get(Schedule, sid)
        assert schedule is not None
        assert schedule.next_run_at is not None
        assert schedule.next_run_at > datetime.now(UTC).replace(tzinfo=None)


async def test_reconcile_skips_missed_slot_without_catch_up(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
    sid = await _make_schedule(factory, next_run_at=past, catch_up=False, is_enabled=True)

    await SchedulerRunner(factory, get_settings())._reconcile_on_startup()

    async with factory() as db:
        schedule = await db.get(Schedule, sid)
        assert schedule is not None
        # advanced past "now" — the missed slot is dropped, not backfilled
        assert schedule.next_run_at is not None
        assert schedule.next_run_at > datetime.now(UTC).replace(tzinfo=None)


async def test_reconcile_keeps_missed_slot_with_catch_up(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
    sid = await _make_schedule(factory, next_run_at=past, catch_up=True, is_enabled=True)

    await SchedulerRunner(factory, get_settings())._reconcile_on_startup()

    async with factory() as db:
        schedule = await db.get(Schedule, sid)
        assert schedule is not None
        # left in the past so the next tick fires it once (catch-up)
        assert schedule.next_run_at is not None
        assert schedule.next_run_at < datetime.now(UTC).replace(tzinfo=None)


_MISSING_INPUT_GRAPH = {
    "nodes": [{"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "missing"}}}],
    "edges": [],
}


async def _make_failing_schedule(factory: async_sessionmaker[AsyncSession], **kwargs: Any) -> str:
    """A schedule whose flow references a non-existent dataset, so every run fails
    (at dataset resolution, before any output dir is touched)."""
    async with factory() as db:
        pid = (await ProjectService(db).ensure_default()).id
        flow = Flow(name="f", project_id=pid, graph_json=_MISSING_INPUT_GRAPH)
        db.add(flow)
        await db.flush()
        schedule = Schedule(
            flow_id=flow.id,
            cron="* * * * *",
            timezone="UTC",
            next_run_at=datetime.now(UTC).replace(tzinfo=None),
            **kwargs,
        )
        db.add(schedule)
        await db.commit()
        return schedule.id


def test_backoff_is_exponential_and_capped() -> None:
    assert SchedulerRunner._backoff_seconds(60, 1) == 60
    assert SchedulerRunner._backoff_seconds(60, 2) == 120
    assert SchedulerRunner._backoff_seconds(60, 3) == 240
    assert SchedulerRunner._backoff_seconds(60, 30) == 3600  # capped


async def test_recover_orphaned_runs_marks_running_as_failed(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    async with factory() as db:
        pid = (await ProjectService(db).ensure_default()).id
        flow = Flow(name="f", project_id=pid, graph_json={})
        db.add(flow)
        await db.flush()
        alive = FlowRun(flow_id=flow.id, status="running", started_at=datetime.now(UTC).replace(tzinfo=None))
        done = FlowRun(flow_id=flow.id, status="success", started_at=datetime.now(UTC).replace(tzinfo=None))
        db.add_all([alive, done])
        await db.commit()
        alive_id, done_id = alive.id, done.id

    await SchedulerRunner(factory, get_settings())._recover_orphaned_runs()

    async with factory() as db:
        recovered = await db.get(FlowRun, alive_id)
        untouched = await db.get(FlowRun, done_id)
        assert recovered is not None and recovered.status == "failed"
        assert recovered.error_message == "Run interrupted by a server restart."
        assert recovered.finished_at is not None
        assert untouched is not None and untouched.status == "success"  # left alone


async def test_auto_disable_after_consecutive_failures(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    # Default threshold is 5; start one short so a single failing fire trips it.
    sid = await _make_failing_schedule(factory, consecutive_failures=4)

    await SchedulerRunner(factory, get_settings())._fire(sid)

    async with factory() as db:
        schedule = await db.get(Schedule, sid)
        assert schedule is not None
        assert schedule.consecutive_failures == 5
        assert schedule.is_enabled is False
        assert schedule.next_run_at is None
        assert schedule.disabled_reason is not None
        assert "Auto-disabled" in schedule.disabled_reason


async def test_failure_retries_with_backoff_then_falls_back_to_cron(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    sid = await _make_failing_schedule(factory, max_retries=2, retry_delay_seconds=60)
    runner = SchedulerRunner(factory, get_settings())

    # First two failures consume retries (next_run_at = backoff, in the future).
    for expected_retry in (1, 2):
        await runner._fire(sid)
        async with factory() as db:
            schedule = await db.get(Schedule, sid)
            assert schedule is not None
            assert schedule.is_enabled is True
            assert schedule.retry_count == expected_retry
            assert schedule.next_run_at is not None
            assert schedule.next_run_at > datetime.now(UTC).replace(tzinfo=None)

    # Third failure exhausts retries -> reset counter, advance to next cron slot.
    await runner._fire(sid)
    async with factory() as db:
        schedule = await db.get(Schedule, sid)
        assert schedule is not None
        assert schedule.retry_count == 0
        assert schedule.consecutive_failures == 3
        assert schedule.is_enabled is True


async def test_tick_skips_in_flight_schedule(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
    sid = await _make_schedule(factory, cron="* * * * *", next_run_at=past, is_enabled=True)

    runner = SchedulerRunner(factory, get_settings())
    runner._in_flight.add(sid)  # pretend a previous run is still going
    await runner._tick()

    assert runner._fire_tasks == set()  # nothing dispatched while in flight


# -- End-to-end fire (needs a real flow + dataset via the API) ----------

ROWS: list[dict[str, Any]] = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": None}]


async def _flow_with_data(client: AsyncClient) -> str:
    buf = io.BytesIO()
    pd.DataFrame(ROWS).to_csv(buf, index=False)
    ds = (
        await client.post(
            "/api/datasets/upload",
            files={"file": ("people.csv", buf.getvalue(), "text/csv")},
        )
    ).json()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "out1"},
        ],
    }
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": graph})).json()
    return str(flow["id"])


@pytest.mark.usefixtures("client")
async def test_fire_executes_flow_and_records_outcome(client: AsyncClient, engine: AsyncEngine) -> None:
    flow_id = await _flow_with_data(client)
    created = (await client.post(f"/api/flows/{flow_id}/schedules", json={"cron": "* * * * *"})).json()

    factory = _factory(engine)
    await SchedulerRunner(factory, get_settings())._fire(created["id"])

    # Verify with a fresh session so we read what the runner committed.
    async with factory() as db:
        schedule = await db.get(Schedule, created["id"])
        assert schedule is not None
        assert schedule.last_status == "success"
        assert schedule.last_run_id is not None
        # the fire advanced the cadence to a future slot
        assert schedule.next_run_at is not None
        assert schedule.next_run_at > datetime.now(UTC).replace(tzinfo=None)

        runs = (await db.execute(select(FlowRun).where(FlowRun.schedule_id == created["id"]))).scalars().all()
        assert len(runs) == 1
        assert runs[0].trigger == "schedule"
        assert runs[0].status == "success"


async def test_auto_disable_sends_notification(engine: AsyncEngine, monkeypatch) -> None:
    """When a schedule gives up (auto-disable), the operator hears about it —
    the disable itself is silent in the UI until someone looks."""
    from app.scheduler import runner as runner_module

    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(runner_module, "notify_in_background", lambda event, payload: events.append((event, payload)))
    factory = _factory(engine)
    sid = await _make_failing_schedule(factory, consecutive_failures=4)

    await SchedulerRunner(factory, get_settings())._fire(sid)

    disabled = [payload for event, payload in events if event == "schedule_auto_disabled"]
    assert len(disabled) == 1
    assert disabled[0]["schedule_id"] == sid
    assert "Auto-disabled" in disabled[0]["reason"]
    assert disabled[0]["consecutive_failures"] == 5


async def test_plain_scheduled_failure_does_not_send_disable_event(engine: AsyncEngine, monkeypatch) -> None:
    from app.scheduler import runner as runner_module

    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(runner_module, "notify_in_background", lambda event, payload: events.append((event, payload)))
    factory = _factory(engine)
    sid = await _make_failing_schedule(factory, max_retries=2, retry_delay_seconds=60)

    await SchedulerRunner(factory, get_settings())._fire(sid)

    assert all(event != "schedule_auto_disabled" for event, _ in events)
