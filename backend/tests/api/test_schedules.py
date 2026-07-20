"""Schedule endpoint tests.

POST   /api/flows/{flow_id}/schedules
GET    /api/flows/{flow_id}/schedules
GET    /api/schedules, /api/schedules/{id}
PATCH  /api/schedules/{id}
DELETE /api/schedules/{id}
POST   /api/schedules/{id}/run-now
"""

import io
from typing import Any

import pandas as pd
from httpx import AsyncClient

ROWS: list[dict[str, Any]] = [
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": None},
]


async def _upload(client: AsyncClient) -> dict:
    buf = io.BytesIO()
    pd.DataFrame(ROWS).to_csv(buf, index=False)
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("people.csv", buf.getvalue(), "text/csv")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _full_graph(dataset_id: str) -> dict:
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


async def _flow(client: AsyncClient) -> dict:
    ds = await _upload(client)
    r = await client.post("/api/flows", json={"name": "f", "graph_json": _full_graph(ds["id"])})
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_schedule_sets_next_run(client: AsyncClient) -> None:
    flow = await _flow(client)
    r = await client.post(
        f"/api/flows/{flow['id']}/schedules",
        json={"cron": "0 9 * * *", "name": "daily", "timezone": "UTC"},
    )
    assert r.status_code == 201, r.text
    sched = r.json()
    assert sched["cron"] == "0 9 * * *"
    assert sched["is_enabled"] is True
    assert sched["catch_up"] is False
    assert sched["next_run_at"] is not None
    assert sched["engine"] is None


async def test_create_schedule_invalid_cron_is_400(client: AsyncClient) -> None:
    flow = await _flow(client)
    r = await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "nope"})
    assert r.status_code == 400


async def test_create_schedule_bad_timezone_is_400(client: AsyncClient) -> None:
    flow = await _flow(client)
    r = await client.post(
        f"/api/flows/{flow['id']}/schedules",
        json={"cron": "0 9 * * *", "timezone": "Mars/Phobos"},
    )
    assert r.status_code == 400


async def test_create_schedule_unknown_engine_is_400(client: AsyncClient) -> None:
    flow = await _flow(client)
    r = await client.post(
        f"/api/flows/{flow['id']}/schedules",
        json={"cron": "0 9 * * *", "engine": "spark"},
    )
    assert r.status_code == 400


async def test_create_schedule_missing_flow_is_404(client: AsyncClient) -> None:
    r = await client.post("/api/flows/ghost/schedules", json={"cron": "0 9 * * *"})
    assert r.status_code == 404


async def test_list_and_get_schedule(client: AsyncClient) -> None:
    flow = await _flow(client)
    created = (await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})).json()

    by_flow = await client.get(f"/api/flows/{flow['id']}/schedules")
    assert by_flow.status_code == 200
    assert [s["id"] for s in by_flow.json()] == [created["id"]]

    all_list = await client.get("/api/schedules")
    assert created["id"] in [s["id"] for s in all_list.json()]

    one = await client.get(f"/api/schedules/{created['id']}")
    assert one.status_code == 200
    assert one.json()["id"] == created["id"]


async def test_disable_clears_next_run_then_reenable_restores(client: AsyncClient) -> None:
    flow = await _flow(client)
    created = (await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})).json()

    disabled = await client.patch(f"/api/schedules/{created['id']}", json={"is_enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["is_enabled"] is False
    assert disabled.json()["next_run_at"] is None

    enabled = await client.patch(f"/api/schedules/{created['id']}", json={"is_enabled": True})
    assert enabled.json()["is_enabled"] is True
    assert enabled.json()["next_run_at"] is not None


async def test_update_invalid_cron_is_400(client: AsyncClient) -> None:
    flow = await _flow(client)
    created = (await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})).json()
    r = await client.patch(f"/api/schedules/{created['id']}", json={"cron": "bad"})
    assert r.status_code == 400


async def test_create_schedule_cron_that_never_fires_is_400(client: AsyncClient) -> None:
    # "0 0 30 2 *" is syntactically valid but 30 February never exists, so
    # compute_next_run raises — the client must get a clean 400, not a 500.
    flow = await _flow(client)
    r = await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 0 30 2 *"})
    assert r.status_code == 400, r.text
    assert "never resolves" in r.json()["detail"]


async def test_update_schedule_cron_that_never_fires_is_400(client: AsyncClient) -> None:
    flow = await _flow(client)
    created = (await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})).json()
    r = await client.patch(f"/api/schedules/{created['id']}", json={"cron": "0 0 30 2 *"})
    assert r.status_code == 400, r.text
    assert "never resolves" in r.json()["detail"]


async def test_delete_schedule(client: AsyncClient) -> None:
    flow = await _flow(client)
    created = (await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})).json()
    r = await client.delete(f"/api/schedules/{created['id']}")
    assert r.status_code == 204
    assert (await client.get(f"/api/schedules/{created['id']}")).status_code == 404


async def test_run_now_executes_flow_as_scheduled_run(client: AsyncClient) -> None:
    flow = await _flow(client)
    created = (await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})).json()

    r = await client.post(f"/api/schedules/{created['id']}/run-now")
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "success"
    assert run["trigger"] == "schedule"
    assert run["schedule_id"] == created["id"]
    # default engine flows through to the scheduled run
    assert run["engine"] == "polars"

    # The schedule records the outcome but its cadence (next_run_at) is untouched.
    sched = (await client.get(f"/api/schedules/{created['id']}")).json()
    assert sched["last_status"] == "success"
    assert sched["last_run_id"] == run["id"]
    assert sched["next_run_at"] == created["next_run_at"]


async def test_schedule_run_history_is_filterable(client: AsyncClient) -> None:
    flow = await _flow(client)
    created = (await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})).json()

    # Two scheduled runs (via run-now) and one ad-hoc manual run on the same flow.
    sched_run_ids = {(await client.post(f"/api/schedules/{created['id']}/run-now")).json()["id"] for _ in range(2)}
    manual_run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()

    # /api/runs?schedule_id= returns only this schedule's runs.
    by_query = (await client.get(f"/api/runs?schedule_id={created['id']}")).json()
    assert {r["id"] for r in by_query} == sched_run_ids
    assert manual_run["id"] not in {r["id"] for r in by_query}
    assert all(r["trigger"] == "schedule" for r in by_query)

    # The nested convenience endpoint returns the same set.
    nested = (await client.get(f"/api/schedules/{created['id']}/runs")).json()
    assert {r["id"] for r in nested} == sched_run_ids


async def test_recent_runs_ride_along_on_schedule_reads(client: AsyncClient) -> None:
    flow = await _flow(client)
    created = (await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})).json()
    assert created["recent_runs"] == []  # a brand-new schedule has no history

    other = (await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 10 * * *"})).json()
    other_run = (await client.post(f"/api/schedules/{other['id']}/run-now")).json()

    # Six runs: recent_runs keeps only the newest five, newest first.
    run_ids = [(await client.post(f"/api/schedules/{created['id']}/run-now")).json()["id"] for _ in range(6)]

    sched = (await client.get(f"/api/schedules/{created['id']}")).json()
    recent = sched["recent_runs"]
    assert [r["id"] for r in recent] == list(reversed(run_ids))[:5]
    assert all(r["status"] == "success" for r in recent)
    assert all(r["created_at"] for r in recent)
    assert other_run["id"] not in {r["id"] for r in recent}  # no bleed across schedules

    # The list endpoints carry the same history per schedule.
    listed = {s["id"]: s for s in (await client.get("/api/schedules")).json()}
    assert [r["id"] for r in listed[created["id"]]["recent_runs"]] == [r["id"] for r in recent]
    assert [r["id"] for r in listed[other["id"]]["recent_runs"]] == [other_run["id"]]


async def test_schedule_runs_unknown_schedule_is_404(client: AsyncClient) -> None:
    assert (await client.get("/api/schedules/ghost/runs")).status_code == 404


async def test_reenabling_clears_failure_state(client: AsyncClient) -> None:
    flow = await _flow(client)
    created = (await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})).json()
    assert created["max_retries"] == 0
    assert created["consecutive_failures"] == 0

    disabled = (await client.patch(f"/api/schedules/{created['id']}", json={"is_enabled": False})).json()
    assert disabled["is_enabled"] is False

    reenabled = (await client.patch(f"/api/schedules/{created['id']}", json={"is_enabled": True})).json()
    assert reenabled["is_enabled"] is True
    assert reenabled["consecutive_failures"] == 0
    assert reenabled["disabled_reason"] is None
