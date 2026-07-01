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
        with Ciaren(BASE) as ff:
            flows = ff.list_flows()
    assert flows == [MOCK_FLOW]


def test_sync_get_flow():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/flows/{FLOW_ID}").mock(return_value=httpx.Response(200, json=MOCK_FLOW))
        with Ciaren(BASE) as ff:
            flow = ff.get_flow(FLOW_ID)
    assert flow["id"] == FLOW_ID


def test_sync_list_runs():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/runs").mock(return_value=httpx.Response(200, json=MOCK_RUNS))
        with Ciaren(BASE) as ff:
            runs = ff.list_runs()
    assert runs == MOCK_RUNS


def test_sync_get_run():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/runs/{RUN_ID}").mock(return_value=httpx.Response(200, json=MOCK_RUN))
        with Ciaren(BASE) as ff:
            run = ff.get_run(RUN_ID)
    assert run["id"] == RUN_ID


def test_sync_trigger_sends_secret_header():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(200, json=MOCK_RUN)
        )
        with Ciaren(BASE, webhook_secret=SECRET) as ff:
            run = ff.trigger(FLOW_ID)
    assert run["status"] == "success"
    assert route.calls[0].request.headers["x-ciaren-secret"] == SECRET


def test_sync_trigger_raises_without_secret():
    with Ciaren(BASE) as ff:
        with pytest.raises(ValueError, match="webhook_secret"):
            ff.trigger(FLOW_ID)


def test_sync_trigger_with_engine():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(200, json=MOCK_RUN)
        )
        with Ciaren(BASE, webhook_secret=SECRET) as ff:
            ff.trigger(FLOW_ID, engine="pandas")
    body = json.loads(route.calls[0].request.content)
    assert body["engine"] == "pandas"


def test_sync_trigger_http_error_raises():
    with respx.mock(base_url=BASE) as mock:
        mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(403, json={"detail": "Invalid secret"})
        )
        with Ciaren(BASE, webhook_secret=SECRET) as ff:
            with pytest.raises(httpx.HTTPStatusError):
                ff.trigger(FLOW_ID)


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
        with Ciaren(BASE) as ff:
            entries = list(ff.stream_logs(RUN_ID))
    assert entries == [{"level": "info", "message": "done"}]


# ---------------------------------------------------------------------------
# Async — AsyncCiaren
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_list_flows():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/flows").mock(return_value=httpx.Response(200, json=[MOCK_FLOW]))
        async with AsyncCiaren(BASE) as ff:
            flows = await ff.list_flows()
    assert flows == [MOCK_FLOW]


@pytest.mark.asyncio
async def test_async_get_flow():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/flows/{FLOW_ID}").mock(return_value=httpx.Response(200, json=MOCK_FLOW))
        async with AsyncCiaren(BASE) as ff:
            flow = await ff.get_flow(FLOW_ID)
    assert flow["id"] == FLOW_ID


@pytest.mark.asyncio
async def test_async_list_runs():
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/runs").mock(return_value=httpx.Response(200, json=MOCK_RUNS))
        async with AsyncCiaren(BASE) as ff:
            runs = await ff.list_runs()
    assert runs == MOCK_RUNS


@pytest.mark.asyncio
async def test_async_get_run():
    with respx.mock(base_url=BASE) as mock:
        mock.get(f"/api/runs/{RUN_ID}").mock(return_value=httpx.Response(200, json=MOCK_RUN))
        async with AsyncCiaren(BASE) as ff:
            run = await ff.get_run(RUN_ID)
    assert run["id"] == RUN_ID


@pytest.mark.asyncio
async def test_async_trigger_sends_secret_header():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(200, json=MOCK_RUN)
        )
        async with AsyncCiaren(BASE, webhook_secret=SECRET) as ff:
            run = await ff.trigger(FLOW_ID)
    assert run["status"] == "success"
    assert route.calls[0].request.headers["x-ciaren-secret"] == SECRET


@pytest.mark.asyncio
async def test_async_trigger_raises_without_secret():
    async with AsyncCiaren(BASE) as ff:
        with pytest.raises(ValueError, match="webhook_secret"):
            await ff.trigger(FLOW_ID)


@pytest.mark.asyncio
async def test_async_trigger_with_parameters():
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(f"/api/flows/{FLOW_ID}/trigger").mock(
            return_value=httpx.Response(200, json=MOCK_RUN)
        )
        async with AsyncCiaren(BASE, webhook_secret=SECRET) as ff:
            await ff.trigger(FLOW_ID, parameters={"env": "prod"})
    body = json.loads(route.calls[0].request.content)
    assert body["parameters"] == {"env": "prod"}


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
        async with AsyncCiaren(BASE) as ff:
            entries = [entry async for entry in ff.stream_logs(RUN_ID)]
    assert entries == [
        {"level": "info", "message": "step 1"},
        {"level": "info", "message": "step 2"},
    ]
