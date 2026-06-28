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
    monkeypatch.setenv("FLOWFRAME_PLUGIN_INSTALL_DIR", str(install_dir))
    monkeypatch.setenv("FLOWFRAME_PLUGINS_DIR", str(install_dir))
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
    # Hello declares no permissions, so it loads straight away.
    assert body["plugin"]["status"] == "loaded"

    # It now shows up in the installed-plugins listing.
    listing = await client.get("/api/plugins")
    assert "community.hello" in {p["id"] for p in listing.json()}


async def test_install_rejects_non_package(client, monkeypatch, tmp_path):
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    resp = await client.post(
        "/api/plugins/install",
        files={"file": ("bogus.ffplugin", b"not a zip", "application/octet-stream")},
    )
    assert resp.status_code == 400


async def test_marketplace_not_configured(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.delenv("FLOWFRAME_MARKETPLACE_INDEX", raising=False)
    get_settings.cache_clear()
    resp = await client.get("/api/marketplace")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert body["plugins"] == []


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
