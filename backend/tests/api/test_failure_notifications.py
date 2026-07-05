# SPDX-License-Identifier: AGPL-3.0-only
"""Outbound failure notifications (app/core/notifications.py).

A real local HTTP server captures the POSTs, so these tests prove the wire
format (JSON body, secret header) and the never-breaks-the-run guarantees —
not just that some mock was called.
"""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.notifications import notify, notify_in_background


class _Receiver(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        _Receiver.received.append({"body": body, "secret": self.headers.get("X-Ciaren-Secret")})
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args: object) -> None:  # silence per-request stderr noise
        pass


@pytest.fixture()
def webhook_server(monkeypatch):
    _Receiver.received = []
    server = HTTPServer(("127.0.0.1", 0), _Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/hook"
    settings = get_settings()
    monkeypatch.setattr(settings, "NOTIFY_WEBHOOK_URL", url)
    monkeypatch.setattr(settings, "NOTIFY_WEBHOOK_SECRET", "s3cret")
    yield _Receiver.received
    server.shutdown()
    server.server_close()


async def _wait_for(predicate, timeout: float = 5.0) -> None:
    async def _poll() -> None:
        while not predicate():
            await asyncio.sleep(0.02)

    await asyncio.wait_for(_poll(), timeout)


# -- unit ---------------------------------------------------------------------


async def test_notify_posts_json_with_secret(webhook_server) -> None:
    ok = await notify("run_failed", {"run_id": "r1", "error": "boom"})
    assert ok is True
    assert len(webhook_server) == 1
    delivery = webhook_server[0]
    assert delivery["secret"] == "s3cret"
    assert delivery["body"]["event"] == "run_failed"
    assert delivery["body"]["run_id"] == "r1"
    assert "timestamp" in delivery["body"]


async def test_notify_is_noop_without_url(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "NOTIFY_WEBHOOK_URL", "")
    assert await notify("run_failed", {}) is False


async def test_notify_never_raises_on_unreachable_host(monkeypatch) -> None:
    # Nothing listens on this port; delivery must fail quietly, not raise.
    monkeypatch.setattr(get_settings(), "NOTIFY_WEBHOOK_URL", "http://127.0.0.1:1/hook")
    assert await notify("run_failed", {"run_id": "r1"}) is False


async def test_notify_rejects_non_http_urls(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "NOTIFY_WEBHOOK_URL", "file:///etc/passwd")
    assert await notify("run_failed", {}) is False


async def test_notify_in_background_is_cheap_noop_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "NOTIFY_WEBHOOK_URL", "")
    notify_in_background("run_failed", {})  # must not need a running task to await


# -- wired: a failed run notifies ----------------------------------------------


async def test_failed_run_sends_run_failed_notification(client: AsyncClient, webhook_server) -> None:
    import io

    import pandas as pd

    buf = io.BytesIO()
    pd.DataFrame({"a": [1, 2]}).to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": ("n.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 201
    ds_id = r.json()["id"]

    # A filter on a missing column fails at execution time (config validation
    # can't know the columns).
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": ds_id}}},
            {
                "id": "f",
                "type": "filterRows",
                "data": {"config": {"column": "missing_col", "operator": ">", "value": 1}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "f"},
            {"id": "e2", "source": "f", "target": "out"},
        ],
    }
    r = await client.post("/api/flows", json={"name": "failing", "graph_json": graph})
    assert r.status_code == 201, r.text
    r = await client.post(f"/api/flows/{r.json()['id']}/runs", json={})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "failed"

    await _wait_for(lambda: len(webhook_server) >= 1)
    body = webhook_server[0]["body"]
    assert body["event"] == "run_failed"
    assert body["run_id"] == run["id"]
    assert body["trigger"] == "manual"
    assert body["error"]


async def test_successful_run_sends_nothing(client: AsyncClient, webhook_server) -> None:
    import io

    import pandas as pd

    buf = io.BytesIO()
    pd.DataFrame({"a": [1, 2]}).to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": ("ok.csv", buf.getvalue(), "text/csv")})
    ds_id = r.json()["id"]
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": ds_id}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [{"id": "e1", "source": "in", "target": "out"}],
    }
    r = await client.post("/api/flows", json={"name": "fine", "graph_json": graph})
    r = await client.post(f"/api/flows/{r.json()['id']}/runs", json={})
    assert r.json()["status"] == "success"
    await asyncio.sleep(0.2)  # give a wrong implementation time to post
    assert webhook_server == []
