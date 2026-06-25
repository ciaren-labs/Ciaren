"""graph_snapshot_json capture + run-timeout precedence (per-run > schedule > global)."""

import io

import pandas as pd
from httpx import AsyncClient

from app.schemas.run import FlowRunCreate
from app.services.execution_service import ExecutionService


async def _upload(client: AsyncClient) -> dict:
    buf = io.BytesIO()
    pd.DataFrame({"a": [1, 2, None]}).to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": ("d.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


def _graph(dataset_id: str) -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "out1"},
        ],
    }


# -- graph snapshot ---------------------------------------------------------


async def test_run_captures_graph_snapshot(client: AsyncClient) -> None:
    ds = await _upload(client)
    graph = _graph(ds["id"])
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": graph})).json()
    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()

    fetched = (await client.get(f"/api/runs/{run['id']}")).json()
    assert fetched["graph_snapshot"] is not None
    # snapshot matches the graph at trigger time
    assert {n["id"] for n in fetched["graph_snapshot"]["nodes"]} == {"in1", "drop", "out1"}


async def test_snapshot_survives_flow_edit(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": _graph(ds["id"])})).json()
    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    # Edit the flow after the run: the snapshot must not change.
    await client.put(f"/api/flows/{flow['id']}", json={"name": "f", "graph_json": {"nodes": [], "edges": []}})
    snap = (await client.get(f"/api/runs/{run['id']}")).json()["graph_snapshot"]
    assert len(snap["nodes"]) == 3


# -- schedule run_timeout_seconds round-trip --------------------------------


async def test_schedule_run_timeout_round_trips(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": _graph(ds["id"])})).json()
    created = await client.post(
        f"/api/flows/{flow['id']}/schedules",
        json={"cron": "0 * * * *", "run_timeout_seconds": 7200},
    )
    assert created.status_code == 201, created.text
    assert created.json()["run_timeout_seconds"] == 7200
    # update clears it back to the global default
    updated = await client.patch(f"/api/schedules/{created.json()['id']}", json={"run_timeout_seconds": None})
    assert updated.json()["run_timeout_seconds"] is None


# -- timeout precedence (unit) ----------------------------------------------


async def test_effective_timeout_precedence(db_session, monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("FLOWFRAME_RUN_TIMEOUT_SECONDS", "30")
    get_settings.cache_clear()
    try:
        service = ExecutionService(db_session)

        # global default when nothing overrides
        assert await service._effective_timeout(FlowRunCreate(), None) == 30
        # explicit per-run override wins
        assert await service._effective_timeout(FlowRunCreate(timeout_seconds=5), None) == 5

        # schedule override applies when no per-run value
        from app.db.models.flow import Flow
        from app.db.models.schedule import Schedule
        from app.services.project_service import ProjectService

        pid = (await ProjectService(db_session).ensure_default()).id
        flow = Flow(name="f", project_id=pid, graph_json={"nodes": [], "edges": []})
        db_session.add(flow)
        await db_session.flush()
        sched = Schedule(flow_id=flow.id, cron="0 * * * *", run_timeout_seconds=120)
        db_session.add(sched)
        await db_session.flush()

        assert await service._effective_timeout(FlowRunCreate(), sched.id) == 120
        # per-run override beats the schedule
        assert await service._effective_timeout(FlowRunCreate(timeout_seconds=7), sched.id) == 7

        # schedule with no override falls back to global
        sched2 = Schedule(flow_id=flow.id, cron="0 * * * *", run_timeout_seconds=None)
        db_session.add(sched2)
        await db_session.flush()
        assert await service._effective_timeout(FlowRunCreate(), sched2.id) == 30
    finally:
        get_settings.cache_clear()


async def test_run_create_rejects_negative_timeout(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": _graph(ds["id"])})).json()
    r = await client.post(f"/api/flows/{flow['id']}/runs", json={"timeout_seconds": -1})
    assert r.status_code == 422
