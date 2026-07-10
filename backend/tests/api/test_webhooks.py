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
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
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
    r = await client.post("/api/flows/any-id/trigger", headers={"X-Ciaren-Secret": SECRET})
    assert r.status_code == 404
    assert "not configured" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/flows/{id}/trigger — secret validation
# ---------------------------------------------------------------------------


async def test_trigger_missing_secret_header(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        r = await client.post("/api/flows/any-id/trigger")
        assert r.status_code == 403
        assert "x-ciaren-secret" in r.json()["detail"].lower()
    finally:
        get_settings.cache_clear()


async def test_trigger_wrong_secret(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        r = await client.post("/api/flows/any-id/trigger", headers={"X-Ciaren-Secret": "wrong"})
        assert r.status_code == 403
    finally:
        get_settings.cache_clear()


async def test_trigger_empty_secret(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        r = await client.post("/api/flows/any-id/trigger", headers={"X-Ciaren-Secret": ""})
        assert r.status_code == 403
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# POST /api/flows/{id}/trigger — valid secret, flow not found
# ---------------------------------------------------------------------------


async def test_trigger_flow_not_found(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        r = await client.post(
            "/api/flows/nonexistent-id/trigger",
            headers={"X-Ciaren-Secret": SECRET},
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
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow = await _create_flow(client, ds["id"])

        r = await client.post(
            f"/api/flows/{flow['id']}/trigger",
            headers={"X-Ciaren-Secret": SECRET},
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
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow = await _create_flow(client, ds["id"])

        r = await client.post(
            f"/api/flows/{flow['id']}/trigger",
            headers={"X-Ciaren-Secret": SECRET},
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
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow = await _create_flow(client, ds["id"])

        r = await client.post(
            f"/api/flows/{flow['id']}/trigger",
            json={"engine": "pandas"},
            headers={"X-Ciaren-Secret": SECRET},
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
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow = await _create_flow(client, ds["id"])

        r = await client.post(
            f"/api/flows/{flow['id']}/trigger?wait=false",
            headers={"X-Ciaren-Secret": SECRET},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "success"
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# GET /api/settings/webhook — secret is never leaked
# ---------------------------------------------------------------------------


async def test_trigger_retry_with_same_idempotency_key_returns_original_run(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller that times out waiting for the blocking response and retries
    with the same Idempotency-Key must get the original run back, not start a
    second one."""
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow = await _create_flow(client, ds["id"])
        headers = {"X-Ciaren-Secret": SECRET, "Idempotency-Key": "retry-key-1"}

        first = await client.post(f"/api/flows/{flow['id']}/trigger", headers=headers)
        assert first.status_code == 200, first.text

        second = await client.post(f"/api/flows/{flow['id']}/trigger", headers=headers)
        assert second.status_code == 200, second.text
        assert second.json()["id"] == first.json()["id"]

        runs = await client.get("/api/runs", params={"flow_id": flow["id"]})
        assert len(runs.json()) == 1  # only one run actually executed
    finally:
        get_settings.cache_clear()


async def test_trigger_without_idempotency_key_always_starts_a_new_run(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow = await _create_flow(client, ds["id"])
        headers = {"X-Ciaren-Secret": SECRET}

        first = await client.post(f"/api/flows/{flow['id']}/trigger", headers=headers)
        second = await client.post(f"/api/flows/{flow['id']}/trigger", headers=headers)
        assert first.json()["id"] != second.json()["id"]

        runs = await client.get("/api/runs", params={"flow_id": flow["id"]})
        assert len(runs.json()) == 2
    finally:
        get_settings.cache_clear()


async def test_trigger_same_idempotency_key_on_different_flows_does_not_collide(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unique constraint is scoped to (flow_id, key) — the same key reused
    across unrelated flows (a plausible client bug, or a shared constant) must
    not make the second flow's trigger silently return the first flow's run."""
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow_a = await _create_flow(client, ds["id"])
        flow_b = await _create_flow(client, ds["id"])
        headers = {"X-Ciaren-Secret": SECRET, "Idempotency-Key": "shared-key"}

        run_a = await client.post(f"/api/flows/{flow_a['id']}/trigger", headers=headers)
        run_b = await client.post(f"/api/flows/{flow_b['id']}/trigger", headers=headers)
        assert run_a.status_code == 200, run_a.text
        assert run_b.status_code == 200, run_b.text
        assert run_a.json()["id"] != run_b.json()["id"]
        assert run_a.json()["flow_id"] == flow_a["id"]
        assert run_b.json()["flow_id"] == flow_b["id"]
    finally:
        get_settings.cache_clear()


async def test_trigger_concurrent_duplicate_delivery_returns_the_winners_run(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forces the true race window (not just the ordinary pre-check path):
    the pre-check is made to miss an already-committed run once — standing in
    for a concurrent request whose insert lands between our own pre-check and
    our own insert — so the trigger must hit the unique constraint at
    db.flush() and recover via the except IntegrityError branch, returning
    the winner's run instead of a raw 500."""
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow = await _create_flow(client, ds["id"])
        headers = {"X-Ciaren-Secret": SECRET, "Idempotency-Key": "race-key"}

        winner = await client.post(f"/api/flows/{flow['id']}/trigger", headers=headers)
        assert winner.status_code == 200, winner.text

        from app.services.execution_service import ExecutionService

        original = ExecutionService.find_by_webhook_idempotency_key
        calls = 0

        async def flaky_precheck(self: ExecutionService, flow_id: str, key: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return None  # the pre-check races ahead of the winner's commit
            return await original(self, flow_id, key)

        monkeypatch.setattr(ExecutionService, "find_by_webhook_idempotency_key", flaky_precheck)

        retry = await client.post(f"/api/flows/{flow['id']}/trigger", headers=headers)
        assert retry.status_code == 200, retry.text
        assert retry.json()["id"] == winner.json()["id"]
        assert calls == 2  # pre-check missed it, the IntegrityError recovery found it
    finally:
        get_settings.cache_clear()


async def test_webhook_status_never_returns_secret(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CIAREN_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        r = await client.get("/api/settings/webhook")
        body = r.text
        assert SECRET not in body
    finally:
        get_settings.cache_clear()
