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
    assert sched["enabled"] is True
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
    created = (
        await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})
    ).json()

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
    created = (
        await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})
    ).json()

    disabled = await client.patch(
        f"/api/schedules/{created['id']}", json={"enabled": False}
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert disabled.json()["next_run_at"] is None

    enabled = await client.patch(f"/api/schedules/{created['id']}", json={"enabled": True})
    assert enabled.json()["enabled"] is True
    assert enabled.json()["next_run_at"] is not None


async def test_update_invalid_cron_is_400(client: AsyncClient) -> None:
    flow = await _flow(client)
    created = (
        await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})
    ).json()
    r = await client.patch(f"/api/schedules/{created['id']}", json={"cron": "bad"})
    assert r.status_code == 400


async def test_delete_schedule(client: AsyncClient) -> None:
    flow = await _flow(client)
    created = (
        await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})
    ).json()
    r = await client.delete(f"/api/schedules/{created['id']}")
    assert r.status_code == 204
    assert (await client.get(f"/api/schedules/{created['id']}")).status_code == 404


async def test_run_now_executes_flow_as_scheduled_run(client: AsyncClient) -> None:
    flow = await _flow(client)
    created = (
        await client.post(f"/api/flows/{flow['id']}/schedules", json={"cron": "0 9 * * *"})
    ).json()

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
