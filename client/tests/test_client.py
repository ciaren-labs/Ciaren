"""Unit tests for the Ciaren Python client.

Uses respx to mock HTTP calls — no running server required.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from ciaren_client import AsyncCiaren, Ciaren

BASE = "http://localhost:8055"
SECRET = "test-secret"
FLOW_ID = "flow-abc"
RUN_ID = "run-xyz"

MOCK_FLOW = {"id": FLOW_ID, "name": "My Flow"}
MOCK_RUN = {"id": RUN_ID, "flow_id": FLOW_ID, "status": "success", "trigger": "webhook"}
MOCK_RUNS = [MOCK_RUN]


# ---------------------------------------------------------------------------
# Sync — Ciaren
# ---------------------------------------------------------------------------


def test_sync_list_flows():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/flows").mock(return_value=httpx.Response(200, json=[MOCK_FLOW]))
        with Ciaren(BASE) as client:
            flows = client.list_flows()
    assert flows == [MOCK_FLOW]


def test_sync_get_flow():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/flows/{FLOW_ID}").mock(return_value=httpx.Response(200, json=MOCK_FLOW))
        with Ciaren(BASE) as client:
            flow = client.get_flow(FLOW_ID)
    assert flow["id"] == FLOW_ID


def test_sync_list_runs():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/runs").mock(return_value=httpx.Response(200, json=MOCK_RUNS))
        with Ciaren(BASE) as client:
            runs = client.list_runs()
    assert runs == MOCK_RUNS


def test_sync_get_run():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/runs/{RUN_ID}").mock(return_value=httpx.Response(200, json=MOCK_RUN))
        with Ciaren(BASE) as client:
            run = client.get_run(RUN_ID)
    assert run["id"] == RUN_ID


def test_sync_trigger_sends_secret_header():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(200, json=MOCK_RUN)
        )
        with Ciaren(BASE, webhook_secret=SECRET) as client:
            run = client.trigger(FLOW_ID)
    assert run["status"] == "success"
    assert route.calls[0].request.headers["x-ciaren-secret"] == SECRET


def test_sync_trigger_raises_without_secret():
    with Ciaren(BASE) as client:
        with pytest.raises(ValueError, match="webhook_secret"):
            client.trigger(FLOW_ID)


def test_sync_trigger_with_engine():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(200, json=MOCK_RUN)
        )
        with Ciaren(BASE, webhook_secret=SECRET) as client:
            client.trigger(FLOW_ID, engine="pandas")
    body = json.loads(route.calls[0].request.content)
    assert body["engine"] == "pandas"


def test_sync_trigger_http_error_raises():
    with respx.mock(base_url=BASE) as mock:
        mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(403, json={"detail": "Invalid secret"})
        )
        with Ciaren(BASE, webhook_secret=SECRET) as client:
            with pytest.raises(httpx.HTTPStatusError):
                client.trigger(FLOW_ID)


def test_sync_api_token_sends_bearer_header():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/api/flows").mock(return_value=httpx.Response(200, json=[MOCK_FLOW]))
        with Ciaren(BASE, api_token="tok-123") as client:
            client.list_flows()
    assert route.calls[0].request.headers["authorization"] == "Bearer tok-123"


def test_sync_list_runs_with_filters_and_pagination():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/api/runs").mock(return_value=httpx.Response(200, json=MOCK_RUNS))
        with Ciaren(BASE) as client:
            client.list_runs(
                project_id="proj-1",
                dataset_id="ds-1",
                schedule_id="sched-1",
                status="failed",
                started_after="2026-06-01T00:00:00",
                sort_by="status",
                sort_order="asc",
                offset=50,
            )
    params = route.calls[0].request.url.params
    assert params["project_id"] == "proj-1"
    assert params["dataset_id"] == "ds-1"
    assert params["schedule_id"] == "sched-1"
    assert params["status"] == "failed"
    assert params["started_after"] == "2026-06-01T00:00:00"
    assert params["sort_by"] == "status"
    assert params["sort_order"] == "asc"
    assert params["offset"] == "50"


def test_sync_retry_run():
    with respx.mock(base_url=BASE) as mock:
        mock.post(f"/api/runs/{RUN_ID}/retry").mock(return_value=httpx.Response(201, json=MOCK_RUN))
        with Ciaren(BASE) as client:
            run = client.retry_run(RUN_ID)
    assert run == MOCK_RUN


def test_sync_stream_logs():
    sse_body = (
        'data: {"level": "info", "message": "done"}\n\n'
        "event: done\n"
        'data: {"status": "success", "run_id": "run-xyz"}\n\n'
    )
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/runs/{RUN_ID}/logs/stream").mock(
            return_value=httpx.Response(200, text=sse_body, headers={"content-type": "text/event-stream"})
        )
        with Ciaren(BASE) as client:
            entries = list(client.stream_logs(RUN_ID))
    assert entries == [{"level": "info", "message": "done"}]


# ---------------------------------------------------------------------------
# Async — AsyncCiaren
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_list_flows():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/flows").mock(return_value=httpx.Response(200, json=[MOCK_FLOW]))
        async with AsyncCiaren(BASE) as client:
            flows = await client.list_flows()
    assert flows == [MOCK_FLOW]


@pytest.mark.asyncio
async def test_async_get_flow():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/flows/{FLOW_ID}").mock(return_value=httpx.Response(200, json=MOCK_FLOW))
        async with AsyncCiaren(BASE) as client:
            flow = await client.get_flow(FLOW_ID)
    assert flow["id"] == FLOW_ID


@pytest.mark.asyncio
async def test_async_list_runs():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/runs").mock(return_value=httpx.Response(200, json=MOCK_RUNS))
        async with AsyncCiaren(BASE) as client:
            runs = await client.list_runs()
    assert runs == MOCK_RUNS


@pytest.mark.asyncio
async def test_async_get_run():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/runs/{RUN_ID}").mock(return_value=httpx.Response(200, json=MOCK_RUN))
        async with AsyncCiaren(BASE) as client:
            run = await client.get_run(RUN_ID)
    assert run["id"] == RUN_ID


@pytest.mark.asyncio
async def test_async_trigger_sends_secret_header():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(200, json=MOCK_RUN)
        )
        async with AsyncCiaren(BASE, webhook_secret=SECRET) as client:
            run = await client.trigger(FLOW_ID)
    assert run["status"] == "success"
    assert route.calls[0].request.headers["x-ciaren-secret"] == SECRET


@pytest.mark.asyncio
async def test_async_trigger_raises_without_secret():
    async with AsyncCiaren(BASE) as client:
        with pytest.raises(ValueError, match="webhook_secret"):
            await client.trigger(FLOW_ID)


@pytest.mark.asyncio
async def test_async_trigger_with_parameters():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(200, json=MOCK_RUN)
        )
        async with AsyncCiaren(BASE, webhook_secret=SECRET) as client:
            await client.trigger(FLOW_ID, parameters={"env": "prod"})
    body = json.loads(route.calls[0].request.content)
    assert body["parameters"] == {"env": "prod"}


@pytest.mark.asyncio
async def test_async_api_token_sends_bearer_header():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/api/flows").mock(return_value=httpx.Response(200, json=[MOCK_FLOW]))
        async with AsyncCiaren(BASE, api_token="tok-123") as client:
            await client.list_flows()
    assert route.calls[0].request.headers["authorization"] == "Bearer tok-123"


@pytest.mark.asyncio
async def test_async_list_runs_with_filters_and_pagination():
    with respx.mock(base_url=BASE) as mock:
        route = mock.get("/api/runs").mock(return_value=httpx.Response(200, json=MOCK_RUNS))
        async with AsyncCiaren(BASE) as client:
            await client.list_runs(schedule_id="sched-1", status="success", offset=10)
    params = route.calls[0].request.url.params
    assert params["schedule_id"] == "sched-1"
    assert params["status"] == "success"
    assert params["offset"] == "10"


@pytest.mark.asyncio
async def test_async_retry_run():
    with respx.mock(base_url=BASE) as mock:
        mock.post(f"/api/runs/{RUN_ID}/retry").mock(return_value=httpx.Response(201, json=MOCK_RUN))
        async with AsyncCiaren(BASE) as client:
            run = await client.retry_run(RUN_ID)
    assert run == MOCK_RUN


@pytest.mark.asyncio
async def test_async_stream_logs():
    sse_body = (
        'data: {"level": "info", "message": "step 1"}\n\n'
        'data: {"level": "info", "message": "step 2"}\n\n'
        "event: done\n"
        'data: {"status": "success", "run_id": "run-xyz"}\n\n'
    )
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/runs/{RUN_ID}/logs/stream").mock(
            return_value=httpx.Response(200, text=sse_body, headers={"content-type": "text/event-stream"})
        )
        async with AsyncCiaren(BASE) as client:
            entries = [entry async for entry in client.stream_logs(RUN_ID)]
    assert entries == [
        {"level": "info", "message": "step 1"},
        {"level": "info", "message": "step 2"},
    ]
