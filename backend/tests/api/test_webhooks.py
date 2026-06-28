"""Tests for the webhook trigger endpoints.

GET  /api/settings/webhook
POST /api/flows/{flow_id}/trigger
"""

import io
from typing import Any

import pandas as pd
import pytest
from httpx import AsyncClient

from app.core.config import get_settings

SECRET = "test-secret-abc123"

ROWS: list[dict[str, Any]] = [
    {"x": 1},
    {"x": 2},
    {"x": 3},
]


async def _upload(client: AsyncClient) -> dict:
    buf = io.BytesIO()
    pd.DataFrame(ROWS).to_csv(buf, index=False)
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("data.csv", buf.getvalue(), "text/csv")},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_flow(client: AsyncClient, dataset_id: str) -> dict:
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }
    r = await client.post("/api/flows", json={"name": "webhook-flow", "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# GET /api/settings/webhook
# ---------------------------------------------------------------------------


async def test_webhook_status_unconfigured(client: AsyncClient) -> None:
    r = await client.get("/api/settings/webhook")
    assert r.status_code == 200
    assert r.json() == {"configured": False}


async def test_webhook_status_configured(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOWFRAME_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        r = await client.get("/api/settings/webhook")
        assert r.status_code == 200
        assert r.json() == {"configured": True}
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# POST /api/flows/{id}/trigger — disabled when secret not configured
# ---------------------------------------------------------------------------


async def test_trigger_disabled_when_no_secret(client: AsyncClient) -> None:
    r = await client.post("/api/flows/any-id/trigger", headers={"X-FlowFrame-Secret": SECRET})
    assert r.status_code == 404
    assert "not configured" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/flows/{id}/trigger — secret validation
# ---------------------------------------------------------------------------


async def test_trigger_missing_secret_header(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOWFRAME_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        r = await client.post("/api/flows/any-id/trigger")
        assert r.status_code == 403
        assert "x-flowframe-secret" in r.json()["detail"].lower()
    finally:
        get_settings.cache_clear()


async def test_trigger_wrong_secret(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOWFRAME_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        r = await client.post("/api/flows/any-id/trigger", headers={"X-FlowFrame-Secret": "wrong"})
        assert r.status_code == 403
    finally:
        get_settings.cache_clear()


async def test_trigger_empty_secret(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOWFRAME_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        r = await client.post("/api/flows/any-id/trigger", headers={"X-FlowFrame-Secret": ""})
        assert r.status_code == 403
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# POST /api/flows/{id}/trigger — valid secret, flow not found
# ---------------------------------------------------------------------------


async def test_trigger_flow_not_found(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOWFRAME_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        r = await client.post(
            "/api/flows/nonexistent-id/trigger",
            headers={"X-FlowFrame-Secret": SECRET},
        )
        assert r.status_code == 404
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# POST /api/flows/{id}/trigger — successful run
# ---------------------------------------------------------------------------


async def test_trigger_runs_flow_and_returns_result(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLOWFRAME_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow = await _create_flow(client, ds["id"])

        r = await client.post(
            f"/api/flows/{flow['id']}/trigger",
            headers={"X-FlowFrame-Secret": SECRET},
        )
        assert r.status_code == 200, r.text
        run = r.json()
        assert run["status"] == "success"
        assert run["flow_id"] == flow["id"]
        assert run["trigger"] == "webhook"
        assert run["started_at"] is not None
        assert run["finished_at"] is not None
    finally:
        get_settings.cache_clear()


async def test_trigger_with_empty_body(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLOWFRAME_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow = await _create_flow(client, ds["id"])

        r = await client.post(
            f"/api/flows/{flow['id']}/trigger",
            headers={"X-FlowFrame-Secret": SECRET},
            content=b"",
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "success"
    finally:
        get_settings.cache_clear()


async def test_trigger_accepts_engine_override(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLOWFRAME_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow = await _create_flow(client, ds["id"])

        r = await client.post(
            f"/api/flows/{flow['id']}/trigger",
            json={"engine": "pandas"},
            headers={"X-FlowFrame-Secret": SECRET},
        )
        assert r.status_code == 200, r.text
        assert r.json()["engine"] == "pandas"
    finally:
        get_settings.cache_clear()


async def test_trigger_wait_false_still_succeeds(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """wait=false is accepted; Phase 1 always blocks and returns the result."""
    monkeypatch.setenv("FLOWFRAME_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow = await _create_flow(client, ds["id"])

        r = await client.post(
            f"/api/flows/{flow['id']}/trigger?wait=false",
            headers={"X-FlowFrame-Secret": SECRET},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "success"
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# GET /api/settings/webhook — secret is never leaked
# ---------------------------------------------------------------------------


async def test_webhook_status_never_returns_secret(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLOWFRAME_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        r = await client.get("/api/settings/webhook")
        body = r.text
        assert SECRET not in body
    finally:
        get_settings.cache_clear()
