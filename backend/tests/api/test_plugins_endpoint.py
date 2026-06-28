"""API tests for /api/plugins and the dynamic catalog picking up a plugin node.

These reset the process-wide registry so discovery re-runs against the bundled
example plugin, and reset again afterwards so other tests see a clean catalog.
"""

from pathlib import Path

import pytest

from app.plugins import reset_registry

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "examples" / "plugins"


@pytest.fixture(autouse=True)
def _isolate_registry():
    reset_registry()
    yield
    reset_registry()


async def test_plugins_empty_by_default(client):
    resp = await client.get("/api/plugins")
    assert resp.status_code == 200
    # No external plugins installed/configured in the default test environment.
    assert resp.json() == []


async def test_plugin_discovered_from_dir_shows_in_endpoints(client, monkeypatch):
    monkeypatch.setenv("FLOWFRAME_PLUGINS_DIR", str(EXAMPLES_DIR))
    reset_registry()  # rebuild with the env now set

    listing = await client.get("/api/plugins")
    ids = {p["id"] for p in listing.json()}
    assert "community.hello" in ids

    # The plugin's node appears in the dynamic catalog without a frontend change.
    catalog = await client.get("/api/catalog/nodes")
    node_ids = {n["id"] for n in catalog.json()}
    assert "hello.greeting" in node_ids


async def test_diagnostics_reports_invalid_plugin(client, monkeypatch, tmp_path):
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "flowframe-plugin.json").write_text("{ bad json", encoding="utf-8")
    monkeypatch.setenv("FLOWFRAME_PLUGINS_DIR", str(tmp_path))
    reset_registry()

    resp = await client.get("/api/plugins/diagnostics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["loaded"] == []
    assert any(e["source"] == "dir:broken" for e in body["errors"])
