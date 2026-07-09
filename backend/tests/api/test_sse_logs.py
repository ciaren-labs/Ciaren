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


# ---------------------------------------------------------------------------
# Wait-and-fetch contract: while the run is still running the stream only sends
# keepalives; the log batch is delivered once, at completion. Driven at the
# generator level because a real run finishes before the stream is opened.
# ---------------------------------------------------------------------------


class _Row:
    def __init__(self, status: str, logs_json) -> None:
        self.status = status
        self.logs_json = logs_json


class _FakeResult:
    def __init__(self, row) -> None:
        self._row = row

    def one_or_none(self):
        return self._row


class _FakeDB:
    """Returns a scripted sequence of rows across successive execute() calls,
    holding the last one thereafter."""

    def __init__(self, rows: list) -> None:
        self._rows = rows
        self.calls = 0

    async def execute(self, _stmt):
        row = self._rows[min(self.calls, len(self._rows) - 1)]
        self.calls += 1
        return _FakeResult(row)


class _FakeService:
    def __init__(self, db) -> None:
        self.db = db


async def test_stream_waits_with_keepalives_then_delivers_batch() -> None:
    from app.api.routes.runs import _sse_log_stream

    logs = [{"level": "info", "message": "all done"}]
    # running twice (→ two keepalives), then success with the log batch.
    rows = [_Row("running", None), _Row("running", None), _Row("success", logs)]
    service = _FakeService(_FakeDB(rows))

    frames = [f async for f in _sse_log_stream(service, "run-1", poll_interval=0.0)]  # type: ignore[arg-type]
    text = "".join(frames)

    # While running: only keepalive comments, never a data/log frame.
    assert text.count(": keepalive\n\n") == 2
    events = _parse_sse(text)
    data_events = [e for e in events if "event" not in e]
    assert len(data_events) == 1
    assert data_events[0]["data"] == logs[0]
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["status"] == "success"


async def test_stream_run_deleted_midwait_closes_cleanly() -> None:
    from app.api.routes.runs import _sse_log_stream

    # running, then the row disappears (run purged) → stream ends with no done frame.
    rows = [_Row("running", None), None]
    service = _FakeService(_FakeDB(rows))

    frames = [f async for f in _sse_log_stream(service, "run-2", poll_interval=0.0)]  # type: ignore[arg-type]
    text = "".join(frames)
    assert ": keepalive\n\n" in text
    assert "event: done" not in text


async def test_stream_times_out_with_error_frame() -> None:
    from app.api.routes.runs import _sse_log_stream

    service = _FakeService(_FakeDB([_Row("running", None)]))  # never terminal
    frames = [
        f
        async for f in _sse_log_stream(service, "run-3", poll_interval=0.0, max_wait_seconds=0.0)  # type: ignore[arg-type]
    ]
    events = _parse_sse("".join(frames))
    assert events[-1]["event"] == "error"
    assert "Timed out" in events[-1]["data"]["detail"]
