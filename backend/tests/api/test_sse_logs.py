"""Tests for the SSE run log streaming endpoint.

GET /api/runs/{run_id}/logs/stream
"""

import io
import json

import pandas as pd
from httpx import AsyncClient

ROWS = [{"a": 1}, {"a": 2}]


async def _upload(client: AsyncClient) -> dict:
    buf = io.BytesIO()
    pd.DataFrame(ROWS).to_csv(buf, index=False)
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("data.csv", buf.getvalue(), "text/csv")},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_and_run_flow(client: AsyncClient) -> dict:
    ds = await _upload(client)
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }
    flow_r = await client.post("/api/flows", json={"name": "sse-flow", "graph_json": graph})
    assert flow_r.status_code == 201, flow_r.text
    run_r = await client.post(f"/api/flows/{flow_r.json()['id']}/runs", json={})
    assert run_r.status_code == 201, run_r.text
    return run_r.json()


def _parse_sse(body: str) -> list[dict]:
    """Parse SSE body text into a list of event dicts with keys 'event' and 'data'."""
    events = []
    current: dict = {}
    for line in body.splitlines():
        if line.startswith("event:"):
            current["event"] = line[len("event:") :].strip()
        elif line.startswith("data:"):
            raw = line[len("data:") :].strip()
            try:
                current["data"] = json.loads(raw)
            except json.JSONDecodeError:
                current["data"] = raw
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


# ---------------------------------------------------------------------------
# 404 for unknown run
# ---------------------------------------------------------------------------


async def test_stream_unknown_run_returns_404(client: AsyncClient) -> None:
    r = await client.get("/api/runs/nonexistent-id/logs/stream")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Successful run — logs streamed then done event
# ---------------------------------------------------------------------------


async def test_stream_logs_success_run(client: AsyncClient) -> None:
    run = await _create_and_run_flow(client)
    assert run["status"] == "success"

    r = await client.get(f"/api/runs/{run['id']}/logs/stream")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]

    events = _parse_sse(r.text)
    assert events, "expected at least one SSE event"

    # Last event must be the 'done' frame
    done = events[-1]
    assert done.get("event") == "done"
    assert done["data"]["status"] == "success"
    assert done["data"]["run_id"] == run["id"]


async def test_stream_logs_data_events_present(client: AsyncClient) -> None:
    run = await _create_and_run_flow(client)

    r = await client.get(f"/api/runs/{run['id']}/logs/stream")
    events = _parse_sse(r.text)

    # Data events (no 'event' key) carry the actual log entries
    data_events = [e for e in events if "event" not in e]
    assert data_events, "expected data events with log entries"
    for e in data_events:
        assert isinstance(e["data"], dict)
        assert "level" in e["data"]
        assert "message" in e["data"]


async def test_stream_logs_done_event_is_last(client: AsyncClient) -> None:
    run = await _create_and_run_flow(client)

    r = await client.get(f"/api/runs/{run['id']}/logs/stream")
    events = _parse_sse(r.text)

    done_indices = [i for i, e in enumerate(events) if e.get("event") == "done"]
    assert len(done_indices) == 1
    assert done_indices[0] == len(events) - 1, "done event must be the last event"


# ---------------------------------------------------------------------------
# Failed run — error log + done with status=failed
# ---------------------------------------------------------------------------


async def test_stream_logs_failed_run(client: AsyncClient) -> None:
    # A structurally valid flow that fails while executing (the graph itself
    # must pass validation — an invalid graph is refused with a 400 up front
    # and never produces a run to stream).
    ds = await _upload(client)
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "drop", "type": "dropColumns", "data": {"config": {"columns": ["ghost"]}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "out1"},
        ],
    }
    flow_r = await client.post("/api/flows", json={"name": "bad", "graph_json": graph})
    assert flow_r.status_code == 201
    run_r = await client.post(f"/api/flows/{flow_r.json()['id']}/runs", json={})
    assert run_r.status_code == 201
    run = run_r.json()
    assert run["status"] == "failed"

    r = await client.get(f"/api/runs/{run['id']}/logs/stream")
    assert r.status_code == 200

    events = _parse_sse(r.text)
    done = events[-1]
    assert done.get("event") == "done"
    assert done["data"]["status"] == "failed"


# ---------------------------------------------------------------------------
# Response headers
# ---------------------------------------------------------------------------


async def test_stream_logs_response_headers(client: AsyncClient) -> None:
    run = await _create_and_run_flow(client)

    r = await client.get(f"/api/runs/{run['id']}/logs/stream")
    assert r.headers.get("cache-control") == "no-cache"
    assert r.headers.get("x-accel-buffering") == "no"
