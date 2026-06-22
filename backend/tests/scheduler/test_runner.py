"""Tests for the background SchedulerRunner.

These drive the runner's internals directly (rather than the polling loop) for
determinism: reconcile/catch-up logic, the overlap guard, and one real fired run
end-to-end.
"""

import io
from datetime import datetime, timedelta
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
        flow = Flow(name="f", graph_json={})
        db.add(flow)
        await db.flush()
        schedule = Schedule(flow_id=flow.id, cron=cron, timezone=timezone, **kwargs)
        db.add(schedule)
        await db.commit()
        return schedule.id


async def test_reconcile_sets_next_run_when_missing(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    sid = await _make_schedule(factory, next_run_at=None, enabled=True)

    await SchedulerRunner(factory, get_settings())._reconcile_on_startup()

    async with factory() as db:
        schedule = await db.get(Schedule, sid)
        assert schedule is not None
        assert schedule.next_run_at is not None
        assert schedule.next_run_at > datetime.utcnow()


async def test_reconcile_skips_missed_slot_without_catch_up(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    past = datetime.utcnow() - timedelta(hours=2)
    sid = await _make_schedule(factory, next_run_at=past, catch_up=False, enabled=True)

    await SchedulerRunner(factory, get_settings())._reconcile_on_startup()

    async with factory() as db:
        schedule = await db.get(Schedule, sid)
        assert schedule is not None
        # advanced past "now" — the missed slot is dropped, not backfilled
        assert schedule.next_run_at is not None
        assert schedule.next_run_at > datetime.utcnow()


async def test_reconcile_keeps_missed_slot_with_catch_up(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    past = datetime.utcnow() - timedelta(hours=2)
    sid = await _make_schedule(factory, next_run_at=past, catch_up=True, enabled=True)

    await SchedulerRunner(factory, get_settings())._reconcile_on_startup()

    async with factory() as db:
        schedule = await db.get(Schedule, sid)
        assert schedule is not None
        # left in the past so the next tick fires it once (catch-up)
        assert schedule.next_run_at is not None
        assert schedule.next_run_at < datetime.utcnow()


async def test_tick_skips_in_flight_schedule(engine: AsyncEngine) -> None:
    factory = _factory(engine)
    past = datetime.utcnow() - timedelta(minutes=1)
    sid = await _make_schedule(factory, cron="* * * * *", next_run_at=past, enabled=True)

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
async def test_fire_executes_flow_and_records_outcome(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    flow_id = await _flow_with_data(client)
    created = (
        await client.post(
            f"/api/flows/{flow_id}/schedules", json={"cron": "* * * * *"}
        )
    ).json()

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
        assert schedule.next_run_at > datetime.utcnow()

        runs = (
            await db.execute(select(FlowRun).where(FlowRun.schedule_id == created["id"]))
        ).scalars().all()
        assert len(runs) == 1
        assert runs[0].trigger == "schedule"
        assert runs[0].status == "success"
