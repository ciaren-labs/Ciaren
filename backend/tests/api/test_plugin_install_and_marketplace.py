"""API tests for installing a plugin from the UI (upload) and the "Explore"
marketplace catalog (configured local index + one-click install)."""

from pathlib import Path

import pytest

from app.plugins import package, reset_registry
from app.plugins.marketplace import add_to_index_file

REPO_ROOT = Path(__file__).resolve().parents[3]
HELLO_SRC = REPO_ROOT / "examples" / "plugins" / "hello-node-plugin"


@pytest.fixture
def hello_ffplugin(tmp_path):
    """A freshly packed (unsigned) Hello .ffplugin to install in tests."""
    return package.pack_directory(HELLO_SRC, tmp_path / "community.hello-0.1.0.ffplugin")


def _point_plugin_dirs_at(monkeypatch, install_dir: Path) -> None:
    """Install into, and discover from, the same temp dir; rebuild the registry."""
    from app.core.config import get_settings

    install_dir.mkdir(parents=True, exist_ok=True)
    home = install_dir.parent / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("FLOWFRAME_PLUGIN_INSTALL_DIR", str(install_dir))
    monkeypatch.setenv("FLOWFRAME_PLUGINS_DIR", str(install_dir))
    monkeypatch.setenv("FLOWFRAME_PLUGIN_STATE_FILE", str(install_dir.parent / "plugin_state.json"))
    get_settings.cache_clear()
    reset_registry()


async def test_install_plugin_via_upload(client, monkeypatch, tmp_path, hello_ffplugin):
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")

    resp = await client.post(
        "/api/plugins/install",
        files={"file": ("community.hello-0.1.0.ffplugin", hello_ffplugin.read_bytes(), "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["outcome"] == "unsigned"
    assert body["plugin"]["id"] == "community.hello"
    # Even with no declared permissions, a freshly installed plugin stays pending
    # until the user approves running its code — it does NOT auto-load.
    assert body["plugin"]["status"] == "needs_permissions"

    # It shows up in the installed-plugins listing (gated, not loaded).
    listing = await client.get("/api/plugins")
    assert "community.hello" in {p["id"] for p in listing.json()}

    # Approving (enable) opts the code in and the plugin loads.
    approved = await client.post("/api/plugins/community.hello/enable")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "loaded"


async def test_install_records_signature_outcome(client, monkeypatch, tmp_path, hello_ffplugin):
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    await client.post(
        "/api/plugins/install",
        files={"file": ("community.hello-0.1.0.ffplugin", hello_ffplugin.read_bytes(), "application/octet-stream")},
    )
    listing = await client.get("/api/plugins")
    hello = next(p for p in listing.json() if p["id"] == "community.hello")
    # An unsigned package surfaces its trust outcome for a UI badge.
    assert hello["signature"] == "unsigned"


async def test_license_endpoint_defaults_to_licensed(client):
    # The endpoint is informational for non-required licenses. Manifest plugins
    # with license_required=True are enforced by the loader before import.
    resp = await client.get("/api/plugins/anything/license")
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["plugin_id"] == "anything"


async def test_install_rejects_non_package(client, monkeypatch, tmp_path):
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    resp = await client.post(
        "/api/plugins/install",
        files={"file": ("bogus.ffplugin", b"not a zip", "application/octet-stream")},
    )
    assert resp.status_code == 400


async def test_marketplace_can_be_disabled(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("FLOWFRAME_MARKETPLACE_INDEX", "none")
    get_settings.cache_clear()
    resp = await client.get("/api/marketplace")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert body["plugins"] == []


async def test_bundled_marketplace_lists_installs_and_loads_hello(client, monkeypatch, tmp_path):
    from app.core.config import get_settings

    monkeypatch.delenv("FLOWFRAME_MARKETPLACE_INDEX", raising=False)
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    get_settings.cache_clear()

    listing = await client.get("/api/marketplace")
    assert listing.status_code == 200, listing.text
    cat = listing.json()
    assert cat["configured"] is True
    entry = next(e for e in cat["plugins"] if e["id"] == "community.hello")
    assert entry["installable"] is True
    assert entry["installed"] is False
    assert entry["nodes"] == ["hello.greeting"]
    assert entry["node_categories"] == {"hello.greeting": "columns"}

    installed = await client.post("/api/marketplace/community.hello/install")
    assert installed.status_code == 200, installed.text
    body = installed.json()
    assert body["plugin"]["id"] == "community.hello"
    assert body["plugin"]["status"] == "needs_permissions"
    assert body["plugin"]["nodes"] == ["hello.greeting"]
    assert body["plugin"]["node_categories"] == {"hello.greeting": "columns"}

    approved = await client.post("/api/plugins/community.hello/enable")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "loaded"

    relisting = await client.get("/api/marketplace")
    entry2 = next(e for e in relisting.json()["plugins"] if e["id"] == "community.hello")
    assert entry2["installed"] is True


async def test_marketplace_lists_and_installs(client, monkeypatch, tmp_path, hello_ffplugin):
    from app.core.config import get_settings

    # Build a local index that points at the packed artifact (relative download url).
    market = tmp_path / "market"
    market.mkdir()
    artifact = market / "community.hello-0.1.0.ffplugin"
    artifact.write_bytes(hello_ffplugin.read_bytes())
    index_path = market / "index.json"
    add_to_index_file(index_path, artifact)

    monkeypatch.setenv("FLOWFRAME_MARKETPLACE_INDEX", str(index_path))
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    get_settings.cache_clear()

    # The catalog lists the entry, marked installable (local artifact) and not yet installed.
    listing = await client.get("/api/marketplace")
    assert listing.status_code == 200, listing.text
    cat = listing.json()
    assert cat["configured"] is True
    entry = next(e for e in cat["plugins"] if e["id"] == "community.hello")
    assert entry["installable"] is True
    assert entry["installed"] is False

    # One-click install from the catalog.
    installed = await client.post("/api/marketplace/community.hello/install")
    assert installed.status_code == 200, installed.text
    assert installed.json()["plugin"]["id"] == "community.hello"

    # Re-listing now marks it installed.
    relisting = await client.get("/api/marketplace")
    entry2 = next(e for e in relisting.json()["plugins"] if e["id"] == "community.hello")
    assert entry2["installed"] is True


async def test_marketplace_install_unknown_404(client, monkeypatch, tmp_path):
    from app.core.config import get_settings

    market = tmp_path / "market"
    market.mkdir()
    (market / "index.json").write_text('{"schemaVersion": "1.0.0", "plugins": []}', encoding="utf-8")
    monkeypatch.setenv("FLOWFRAME_MARKETPLACE_INDEX", str(market / "index.json"))
    get_settings.cache_clear()

    resp = await client.post("/api/marketplace/does.not.exist/install")
    assert resp.status_code == 404


async def test_install_rejects_oversized_upload(client, monkeypatch, tmp_path, hello_ffplugin):
    """An upload larger than MAX_UPLOAD_SIZE_MB is rejected with 413, and is not
    buffered whole before the check (it is streamed and aborted early)."""
    from app.core.config import get_settings

    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    monkeypatch.setenv("FLOWFRAME_MAX_UPLOAD_SIZE_MB", "1")  # 1 MiB cap
    get_settings.cache_clear()
    try:
        big = b"\x00" * (2 * 1024 * 1024)  # 2 MiB, over the cap
        resp = await client.post(
            "/api/plugins/install",
            files={"file": ("big.ffplugin", big, "application/octet-stream")},
        )
        assert resp.status_code == 413, resp.text
        assert "maximum upload size" in resp.text
    finally:
        get_settings.cache_clear()
