# SPDX-License-Identifier: AGPL-3.0-only
"""Run cancellation: cooperative stop between nodes (thread mode), the
cancel endpoint's state rules, and the run record's final shape.
"""

import asyncio
import io
import threading

import pandas as pd
from httpx import AsyncClient

from app.engine.cancellation import register_run, request_cancel, unregister_run
from app.engine.executor import FlowExecutor

# -- registry -------------------------------------------------------------------


def test_request_cancel_unknown_run_returns_false() -> None:
    assert request_cancel("nope") is False


def test_register_cancel_unregister_roundtrip() -> None:
    event = register_run("r1")
    try:
        assert request_cancel("r1") is True
        assert event.is_set()
    finally:
        unregister_run("r1")
    assert request_cancel("r1") is False


# -- executor: cooperative stop ---------------------------------------------------


def _linear_graph() -> dict:
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "ds"}}},
            {"id": "d1", "type": "dropNulls", "data": {"config": {}}},
            {"id": "d2", "type": "removeDuplicates", "data": {"config": {}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "d1"},
            {"id": "e2", "source": "d1", "target": "d2"},
            {"id": "e3", "source": "d2", "target": "out"},
        ],
    }


def test_executor_stops_at_next_node_boundary(tmp_path) -> None:
    (tmp_path / "in.csv").write_text("a\n1\n2\n")
    event = threading.Event()
    executor = FlowExecutor()

    # Set the cancel event from inside the first node's execution: everything
    # after it must be skipped, proving the check runs BETWEEN nodes.
    original = executor._node_outputs
    calls = {"n": 0}

    def tripping(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # after the input node, during dropNulls
            event.set()
        return original(*args, **kwargs)

    executor._node_outputs = tripping  # type: ignore[method-assign]
    result = executor.run_with_results(
        _linear_graph(),
        {"ds:latest": tmp_path / "in.csv"},
        tmp_path,
        cancel_event=event,
    )
    assert result.cancelled is True
    assert result.error == "Cancelled by user."
    statuses = {r.node_id: r.status for r in result.node_results}
    assert statuses["in"] == "success"
    assert statuses["d1"] == "success"  # the node that was mid-flight finishes
    assert statuses["d2"] == "skipped"
    assert statuses["out"] == "skipped"
    assert result.output_paths == {}  # no outputs written for a cancelled run


def test_executor_pre_cancelled_run_skips_everything(tmp_path) -> None:
    (tmp_path / "in.csv").write_text("a\n1\n")
    event = threading.Event()
    event.set()
    result = FlowExecutor().run_with_results(
        _linear_graph(),
        {"ds:latest": tmp_path / "in.csv"},
        tmp_path,
        cancel_event=event,
    )
    assert result.cancelled is True
    assert all(r.status == "skipped" for r in result.node_results)


# -- API ---------------------------------------------------------------------------


async def _upload_csv(client: AsyncClient, name: str, rows: int = 3) -> str:
    buf = io.BytesIO()
    pd.DataFrame({"a": range(rows)}).to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": (name, buf.getvalue(), "text/csv")})
    assert r.status_code == 201
    return r.json()["id"]


async def test_cancel_running_run_via_api(client: AsyncClient) -> None:
    ds_id = await _upload_csv(client, "cancelme.csv")
    # A pythonTransform that sleeps per node gives us a window to cancel in.
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": ds_id}}},
            {
                "id": "slow1",
                "type": "pythonTransform",
                "data": {"config": {"script": "import time\ntime.sleep(0.6)\nreturn df"}},
            },
            {
                "id": "slow2",
                "type": "pythonTransform",
                "data": {"config": {"script": "import time\ntime.sleep(0.6)\nreturn df"}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "slow1"},
            {"id": "e2", "source": "slow1", "target": "slow2"},
            {"id": "e3", "source": "slow2", "target": "out"},
        ],
    }
    r = await client.post("/api/flows", json={"name": "slowflow", "graph_json": graph})
    assert r.status_code == 201, r.text
    flow_id = r.json()["id"]

    run_task = asyncio.create_task(client.post(f"/api/flows/{flow_id}/runs", json={}))

    # Wait until the run row exists and is running, then cancel it.
    run_id: str | None = None
    for _ in range(200):
        await asyncio.sleep(0.02)
        listing = await client.get("/api/runs", params={"flow_id": flow_id})
        rows = listing.json()
        if rows and rows[0]["status"] == "running":
            run_id = rows[0]["id"]
            break
    assert run_id, "run never reached 'running'"

    cancel = await client.post(f"/api/runs/{run_id}/cancel")
    assert cancel.status_code == 202, cancel.text
    assert cancel.json()["status"] == "cancelling"

    finished = (await run_task).json()
    assert finished["status"] == "cancelled"
    assert finished["error_message"] == "Cancelled by user."
    statuses = {n["node_id"]: n["status"] for n in finished["node_results"]}
    assert statuses["out"] == "skipped"

    # Cancelling a finished run is a clear 400, not a no-op.
    again = await client.post(f"/api/runs/{run_id}/cancel")
    assert again.status_code == 400
    assert "cancelled" in again.json()["detail"]


async def test_cancel_unknown_run_is_404(client: AsyncClient) -> None:
    r = await client.post("/api/runs/does-not-exist/cancel")
    assert r.status_code == 404


async def test_cancel_finished_run_is_400(client: AsyncClient) -> None:
    ds_id = await _upload_csv(client, "quick.csv")
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": ds_id}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [{"id": "e1", "source": "in", "target": "out"}],
    }
    r = await client.post("/api/flows", json={"name": "quick", "graph_json": graph})
    r = await client.post(f"/api/flows/{r.json()['id']}/runs", json={})
    run = r.json()
    assert run["status"] == "success"
    r = await client.post(f"/api/runs/{run['id']}/cancel")
    assert r.status_code == 400
    assert "success" in r.json()["detail"]


async def test_cancelled_run_does_not_notify(client: AsyncClient, monkeypatch) -> None:
    """A user stopping a run is not an alert-worthy failure."""
    events: list[str] = []
    from app.services import execution_service as es

    monkeypatch.setattr(es, "notify_in_background", lambda event, payload: events.append(event))

    ds_id = await _upload_csv(client, "cancelnotify.csv")
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": ds_id}}},
            {
                "id": "slow",
                "type": "pythonTransform",
                "data": {"config": {"script": "import time\ntime.sleep(0.6)\nreturn df"}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "slow"},
            {"id": "e2", "source": "slow", "target": "out"},
        ],
    }
    r = await client.post("/api/flows", json={"name": "cancelnotify", "graph_json": graph})
    flow_id = r.json()["id"]
    run_task = asyncio.create_task(client.post(f"/api/flows/{flow_id}/runs", json={}))
    run_id = None
    for _ in range(200):
        await asyncio.sleep(0.02)
        listing = await client.get("/api/runs", params={"flow_id": flow_id})
        rows = listing.json()
        if rows and rows[0]["status"] == "running":
            run_id = rows[0]["id"]
            break
    assert run_id
    await client.post(f"/api/runs/{run_id}/cancel")
    finished = (await run_task).json()
    assert finished["status"] == "cancelled"
    assert events == []
