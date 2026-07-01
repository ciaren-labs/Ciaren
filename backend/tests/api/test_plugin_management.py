"""API tests for plugin enable/disable + permission approval, end-to-end.

A drop-in plugin that declares a permission starts *pending* (its code is never
imported) and only loads once the permission is granted via the API; disabling it
takes it back out of the catalog. All changes apply live (registry rebuild).
"""

from __future__ import annotations

import json
import textwrap

import pytest

from app.plugins import reset_registry

PLUGIN_ID = "test.mgmt"
NODE_ID = "mgmt.node"

_MODULE = textwrap.dedent(
    """
    from app.plugin_api import (
        NodeProvider, NodeSpec, Plugin, PluginMetadata, PortSpec, ServiceRegistry, Permission,
    )

    class _Nodes(NodeProvider):
        def nodes(self):
            return [NodeSpec(id="mgmt.node", label="Mgmt Node", category="columns",
                             inputs=(PortSpec(id="in"),), outputs=(PortSpec(id="out"),))]

    class MgmtPlugin(Plugin):
        def metadata(self):
            return PluginMetadata(id="test.mgmt", name="Mgmt Plugin", version="1.0.0",
                                  permissions=(Permission.network,))
        def register(self, registry: ServiceRegistry) -> None:
            registry.register_node_provider(_Nodes())
    """
)

_MANIFEST = {
    "id": PLUGIN_ID,
    "name": "Mgmt Plugin",
    "version": "1.0.0",
    "entrypoint": "mgmt_plugin:MgmtPlugin",
    "permissions": ["network"],
    "capabilities": ["node.mgmt"],
    "ui": {"nodes": [NODE_ID], "nodeCategories": {NODE_ID: "quality"}},
}


@pytest.fixture(autouse=True)
def _plugin_dir(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("CIAREN_PLUGIN_STATE_FILE", str(tmp_path / "plugin_state.json"))
    plugin = tmp_path / "mgmt-plugin"
    plugin.mkdir()
    (plugin / "mgmt_plugin.py").write_text(_MODULE, encoding="utf-8")
    (plugin / "ciaren-plugin.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")
    monkeypatch.setenv("CIAREN_PLUGINS_DIR", str(tmp_path))
    reset_registry()
    yield
    reset_registry()


async def _catalog_ids(client) -> set[str]:
    resp = await client.get("/api/catalog/nodes")
    return {n["id"] for n in resp.json()}


async def test_pending_then_grant_then_revoke_lifecycle(client):
    # 1. Discovered but pending: declares `network`, not granted -> not loaded.
    listing = (await client.get("/api/plugins")).json()
    entry = next(p for p in listing if p["id"] == PLUGIN_ID)
    assert entry["status"] == "needs_permissions"
    assert entry["missing_permissions"] == ["network"]
    assert entry["nodes"] == [NODE_ID]
    assert entry["node_categories"] == {NODE_ID: "quality"}
    assert NODE_ID not in await _catalog_ids(client)

    # 2. Grant (empty body -> grant all requested) -> loads, node appears live.
    granted = (await client.post(f"/api/plugins/{PLUGIN_ID}/grant", json={})).json()
    assert granted["status"] == "loaded"
    assert "network" in granted["granted_permissions"]
    assert NODE_ID in await _catalog_ids(client)

    # 3. Revoke -> back to pending, node disappears.
    revoked = (await client.post(f"/api/plugins/{PLUGIN_ID}/revoke", json={"permissions": ["network"]})).json()
    assert revoked["status"] == "needs_permissions"
    assert NODE_ID not in await _catalog_ids(client)


async def test_disable_and_enable(client):
    # Grant first so it's loaded, then disable.
    await client.post(f"/api/plugins/{PLUGIN_ID}/grant", json={})
    assert NODE_ID in await _catalog_ids(client)

    disabled = (await client.post(f"/api/plugins/{PLUGIN_ID}/disable", json={})).json()
    assert disabled["status"] == "disabled"
    assert NODE_ID not in await _catalog_ids(client)

    enabled = (await client.post(f"/api/plugins/{PLUGIN_ID}/enable", json={})).json()
    # Re-enabled and permission still granted -> loaded again.
    assert enabled["status"] == "loaded"
    assert NODE_ID in await _catalog_ids(client)


async def test_grant_specific_permission_only(client):
    resp = await client.post(f"/api/plugins/{PLUGIN_ID}/grant", json={"permissions": ["network"]})
    assert resp.json()["status"] == "loaded"


async def test_manage_unknown_plugin_404(client):
    resp = await client.post("/api/plugins/does.not.exist/enable", json={})
    assert resp.status_code == 404
