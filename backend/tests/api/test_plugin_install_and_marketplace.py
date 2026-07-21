"""API tests for installing a plugin from the UI (upload) and the "Explore"
marketplace catalog (configured local index + one-click install)."""

import json
from pathlib import Path

import pytest

from app.plugins import package, reset_registry
from app.plugins.marketplace import add_to_index_file

REPO_ROOT = Path(__file__).resolve().parents[3]
HELLO_SRC = REPO_ROOT / "examples" / "plugins" / "hello-node-plugin"


@pytest.fixture
def hello_ciarenplugin(tmp_path):
    """A freshly packed (unsigned) Hello .ciarenplugin to install in tests."""
    return package.pack_directory(HELLO_SRC, tmp_path / "community.hello-0.1.0.ciarenplugin")


def _point_plugin_dirs_at(monkeypatch, install_dir: Path) -> None:
    """Install into, and discover from, the same temp dir; rebuild the registry."""
    from app.core.config import get_settings

    install_dir.mkdir(parents=True, exist_ok=True)
    home = install_dir.parent / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("CIAREN_PLUGIN_INSTALL_DIR", str(install_dir))
    monkeypatch.setenv("CIAREN_PLUGINS_DIR", str(install_dir))
    monkeypatch.setenv("CIAREN_PLUGIN_STATE_FILE", str(install_dir.parent / "plugin_state.json"))
    get_settings.cache_clear()
    reset_registry()


async def test_install_plugin_via_upload(client, monkeypatch, tmp_path, hello_ciarenplugin):
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")

    resp = await client.post(
        "/api/plugins/install",
        files={
            "file": (
                "community.hello-0.1.0.ciarenplugin",
                hello_ciarenplugin.read_bytes(),
                "application/octet-stream",
            )
        },
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


async def test_uninstall_plugin_via_api(client, monkeypatch, tmp_path, hello_ciarenplugin):
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")

    await client.post(
        "/api/plugins/install",
        files={
            "file": (
                "community.hello-0.1.0.ciarenplugin",
                hello_ciarenplugin.read_bytes(),
                "application/octet-stream",
            )
        },
    )
    # A managed install is flagged uninstallable so the UI can offer "Uninstall".
    listing = await client.get("/api/plugins")
    hello = next(p for p in listing.json() if p["id"] == "community.hello")
    assert hello["uninstallable"] is True
    await client.post("/api/plugins/community.hello/enable")
    assert "hello.greeting" in {n["id"] for n in (await client.get("/api/catalog/nodes")).json()}

    # DELETE removes the files and the plugin leaves the listing + catalog live.
    resp = await client.delete("/api/plugins/community.hello")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"plugin_id": "community.hello", "removed": True}
    assert "community.hello" not in {p["id"] for p in (await client.get("/api/plugins")).json()}
    assert "hello.greeting" not in {n["id"] for n in (await client.get("/api/catalog/nodes")).json()}


async def test_uninstall_unknown_plugin_404(client, monkeypatch, tmp_path):
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    resp = await client.delete("/api/plugins/does.not.exist")
    assert resp.status_code == 404


async def test_install_records_signature_outcome(client, monkeypatch, tmp_path, hello_ciarenplugin):
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    await client.post(
        "/api/plugins/install",
        files={
            "file": (
                "community.hello-0.1.0.ciarenplugin",
                hello_ciarenplugin.read_bytes(),
                "application/octet-stream",
            )
        },
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
        files={"file": ("bogus.ciarenplugin", b"not a zip", "application/octet-stream")},
    )
    assert resp.status_code == 400


async def test_marketplace_can_be_disabled(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", "none")
    get_settings.cache_clear()
    resp = await client.get("/api/marketplace")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert body["plugins"] == []


async def test_bundled_marketplace_lists_installs_and_loads_hello(client, monkeypatch, tmp_path):
    from app.core.config import get_settings

    monkeypatch.delenv("CIAREN_MARKETPLACE_INDEX", raising=False)
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


async def test_marketplace_lists_and_installs(client, monkeypatch, tmp_path, hello_ciarenplugin):
    from app.core.config import get_settings

    # Build a local index that points at the packed artifact (relative download url).
    market = tmp_path / "market"
    market.mkdir()
    artifact = market / "community.hello-0.1.0.ciarenplugin"
    artifact.write_bytes(hello_ciarenplugin.read_bytes())
    index_path = market / "index.json"
    add_to_index_file(index_path, artifact)

    monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", str(index_path))
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
    monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", str(market / "index.json"))
    get_settings.cache_clear()

    resp = await client.post("/api/marketplace/does.not.exist/install")
    assert resp.status_code == 404


async def test_install_rejects_oversized_upload(client, monkeypatch, tmp_path, hello_ciarenplugin):
    """An upload larger than MAX_UPLOAD_SIZE_MB is rejected with 413, and is not
    buffered whole before the check (it is streamed and aborted early)."""
    from app.core.config import get_settings

    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    monkeypatch.setenv("CIAREN_MAX_UPLOAD_SIZE_MB", "1")  # 1 MiB cap
    get_settings.cache_clear()
    try:
        big = b"\x00" * (2 * 1024 * 1024)  # 2 MiB, over the cap
        resp = await client.post(
            "/api/plugins/install",
            files={"file": ("big.ciarenplugin", big, "application/octet-stream")},
        )
        assert resp.status_code == 413, resp.text
        assert "maximum upload size" in resp.text
    finally:
        get_settings.cache_clear()


async def test_marketplace_install_requires_digest(client, monkeypatch, tmp_path, hello_ciarenplugin):
    """An index entry without a digest is unverifiable — refuse, don't skip."""
    import json as _json

    from app.core.config import get_settings

    market = tmp_path / "market"
    market.mkdir()
    artifact = market / "community.hello-0.1.0.ciarenplugin"
    artifact.write_bytes(hello_ciarenplugin.read_bytes())
    index_path = market / "index.json"
    add_to_index_file(index_path, artifact)
    raw = _json.loads(index_path.read_text(encoding="utf-8"))
    raw["plugins"][0]["digest"] = ""
    index_path.write_text(_json.dumps(raw), encoding="utf-8")

    monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", str(index_path))
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    get_settings.cache_clear()

    resp = await client.post("/api/marketplace/community.hello/install")
    assert resp.status_code == 400, resp.text
    assert "digest" in resp.json()["detail"]


async def test_marketplace_trust_is_derived_not_echoed(client, monkeypatch, tmp_path, hello_ciarenplugin):
    """A self-declared "trusted" claim in the index must not surface as the trust
    badge: the artifact is unsigned, so the API reports community."""
    import json as _json

    from app.core.config import get_settings

    market = tmp_path / "market"
    market.mkdir()
    artifact = market / "community.hello-0.1.0.ciarenplugin"
    artifact.write_bytes(hello_ciarenplugin.read_bytes())
    index_path = market / "index.json"
    add_to_index_file(index_path, artifact)
    raw = _json.loads(index_path.read_text(encoding="utf-8"))
    raw["plugins"][0]["trust"] = "trusted"  # publisher-controlled claim
    index_path.write_text(_json.dumps(raw), encoding="utf-8")

    monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", str(index_path))
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    get_settings.cache_clear()

    listing = await client.get("/api/marketplace")
    entry = next(e for e in listing.json()["plugins"] if e["id"] == "community.hello")
    assert entry["trust"] == "community"


async def test_untrusted_index_cannot_point_install_at_arbitrary_local_files(
    client, monkeypatch, tmp_path, hello_ciarenplugin
):
    """A hosted (untrusted) index whose downloadUrl escapes its own directory —
    ``..``, an absolute path, or ``file://`` — must not resolve: the entry reads
    as not installable and install is a clean 400 (never a local file read),
    even when the index-supplied digest matches the targeted file."""
    import json as _json

    from app.core.config import get_settings
    from app.plugins import marketplace as marketplace_mod

    market = tmp_path / "market"
    market.mkdir()
    victim = tmp_path / "victim.ciarenplugin"  # a real package OUTSIDE the index dir
    victim.write_bytes(hello_ciarenplugin.read_bytes())
    index_path = market / "index.json"
    # Digest is computed from the victim bytes, so only path confinement blocks it.
    add_to_index_file(index_path, victim, download_url="../victim.ciarenplugin")

    monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", str(index_path))
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    get_settings.cache_clear()

    # Sanity: as a trusted local index the same URL resolves (today's contract).
    listing = await client.get("/api/marketplace")
    entry = next(e for e in listing.json()["plugins"] if e["id"] == "community.hello")
    assert entry["installable"] is True

    # Simulate the planned hosted index: identical content, untrusted source.
    monkeypatch.setattr(marketplace_mod, "configured_index_is_trusted", lambda: False)

    listing = await client.get("/api/marketplace")
    entry = next(e for e in listing.json()["plugins"] if e["id"] == "community.hello")
    assert entry["installable"] is False
    assert entry["trust"] == "community"

    for url in ("../victim.ciarenplugin", str(victim), f"file://{victim.as_posix()}"):
        raw = _json.loads(index_path.read_text(encoding="utf-8"))
        raw["plugins"][0]["downloadUrl"] = url
        index_path.write_text(_json.dumps(raw), encoding="utf-8")
        resp = await client.post("/api/marketplace/community.hello/install")
        assert resp.status_code == 400, (url, resp.text)
        assert "artifact" in resp.json()["detail"]
    # Nothing was installed by any of the attempts.
    assert "community.hello" not in {p["id"] for p in (await client.get("/api/plugins")).json()}


async def test_trusted_local_index_still_installs_absolute_path_artifacts(
    client, monkeypatch, tmp_path, hello_ciarenplugin
):
    """The operator-controlled local index keeps its contract: an artifact
    outside the index directory (recorded as an absolute downloadUrl by
    ``ciaren plugin index add``) still lists as installable and installs."""
    from app.core.config import get_settings

    market = tmp_path / "market"
    market.mkdir()
    artifact = tmp_path / "elsewhere" / "community.hello-0.1.0.ciarenplugin"
    artifact.parent.mkdir()
    artifact.write_bytes(hello_ciarenplugin.read_bytes())
    index_path = market / "index.json"
    add_to_index_file(index_path, artifact)  # records the absolute path

    monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", str(index_path))
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    get_settings.cache_clear()

    listing = await client.get("/api/marketplace")
    entry = next(e for e in listing.json()["plugins"] if e["id"] == "community.hello")
    assert entry["installable"] is True

    resp = await client.post("/api/marketplace/community.hello/install")
    assert resp.status_code == 200, resp.text
    assert resp.json()["plugin"]["id"] == "community.hello"


def _pack_hello_variant(tmp_path: Path, *, version: str | None = None, license_required: bool | None = None) -> Path:
    """A copy of the hello plugin with manifest tweaks, packed to a .ciarenplugin."""
    import json as _json
    import shutil

    src = tmp_path / f"hello-src-{version or 'same'}-{license_required}"
    shutil.copytree(HELLO_SRC, src)
    manifest = _json.loads((src / "ciaren-plugin.json").read_text(encoding="utf-8"))
    if version is not None:
        manifest["version"] = version
    if license_required is not None:
        manifest["licenseRequired" if "licenseRequired" in manifest else "license_required"] = license_required
    (src / "ciaren-plugin.json").write_text(_json.dumps(manifest), encoding="utf-8")
    return package.pack_directory(src, tmp_path / f"community.hello-{version or 'same'}.ciarenplugin")


def _signed_token(private_hex: str, plugin_id: str = "community.hello", *, days: int = 30) -> dict:
    """A marketplace-issued license token (wire format), signed by the issuer."""
    from datetime import UTC, datetime, timedelta

    from app.plugin_api import signing as _signing
    from app.plugins.licensing import LicenseToken

    now = datetime.now(UTC)
    token = LicenseToken(
        userId="u1",
        pluginId=plugin_id,
        licenseType="pro",
        expiresAt=(now + timedelta(days=days)).isoformat(),
        offlineGraceUntil=(now + timedelta(days=days + 14)).isoformat(),
    )
    token.signature = _signing.sign(private_hex, token.signing_payload())
    return json.loads(token.model_dump_json(by_alias=True))


async def test_premium_plugin_license_activation_end_to_end(client, monkeypatch, tmp_path):
    """The full paid-plugin path: install → approve → needs_license → activate a
    signed token → loaded. Then removing the license gates it again."""
    from app.core.config import get_settings
    from app.plugin_api import signing

    if not signing.signing_available():
        pytest.skip("cryptography not installed")

    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    priv, pub = signing.generate_keypair()
    monkeypatch.setenv("CIAREN_MARKETPLACE_LICENSE_ISSUER_KEYS", json.dumps([pub]))
    monkeypatch.setenv("CIAREN_LICENSE_DIR", str(tmp_path / "licenses"))
    get_settings.cache_clear()
    reset_registry()

    premium = _pack_hello_variant(tmp_path, license_required=True)
    resp = await client.post(
        "/api/plugins/install",
        files={"file": ("premium.ciarenplugin", premium.read_bytes(), "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plugin"]["status"] == "needs_permissions"

    # Approving satisfies the permission gate; the license gate now holds it.
    approved = await client.post("/api/plugins/community.hello/enable")
    assert approved.json()["status"] == "needs_license"
    assert "license" in approved.json()["status_detail"]

    # Activating a token signed by the trusted issuer loads it immediately.
    activated = await client.post("/api/plugins/community.hello/license", json=_signed_token(priv))
    assert activated.status_code == 200, activated.text
    assert activated.json()["valid"] is True
    listing = await client.get("/api/plugins")
    hello = next(p for p in listing.json() if p["id"] == "community.hello")
    assert hello["status"] == "loaded"

    # Removing the license drops it back to needs_license on reload.
    removed = await client.delete("/api/plugins/community.hello/license")
    assert removed.status_code == 200
    assert removed.json()["valid"] is False
    listing = await client.get("/api/plugins")
    hello = next(p for p in listing.json() if p["id"] == "community.hello")
    assert hello["status"] == "needs_license"


async def test_activate_license_rejects_wrong_plugin_and_forged_token(client, monkeypatch, tmp_path):
    from app.core.config import get_settings
    from app.plugin_api import signing

    if not signing.signing_available():
        pytest.skip("cryptography not installed")

    priv, pub = signing.generate_keypair()
    forger_priv, _ = signing.generate_keypair()
    monkeypatch.setenv("CIAREN_MARKETPLACE_LICENSE_ISSUER_KEYS", json.dumps([pub]))
    monkeypatch.setenv("CIAREN_LICENSE_DIR", str(tmp_path / "licenses"))
    get_settings.cache_clear()
    reset_registry()
    try:
        # Token/path plugin id mismatch → refused before any verification.
        resp = await client.post("/api/plugins/other.plugin/license", json=_signed_token(priv))
        assert resp.status_code == 400
        assert "other.plugin" in resp.json()["detail"]

        # A token not signed by a trusted issuer is refused and never cached.
        resp = await client.post("/api/plugins/community.hello/license", json=_signed_token(forger_priv))
        assert resp.status_code == 400
        assert "rejected" in resp.json()["detail"]
        status = await client.get("/api/plugins/community.hello/license")
        assert status.json()["valid"] is False

        # Nothing cached → removing 404s.
        resp = await client.delete("/api/plugins/community.hello/license")
        assert resp.status_code == 404
    finally:
        get_settings.cache_clear()


async def test_activate_license_refused_when_nothing_can_validate(client, monkeypatch, tmp_path):
    """With no issuer keys and no registered provider, activation must be a clean
    400 — not a saved token plus a success-looking 'no license provider' status."""
    from datetime import UTC, datetime, timedelta

    from app.core.config import get_settings

    monkeypatch.delenv("CIAREN_MARKETPLACE_LICENSE_ISSUER_KEYS", raising=False)
    monkeypatch.setenv("CIAREN_LICENSE_DIR", str(tmp_path / "licenses"))
    get_settings.cache_clear()
    reset_registry()
    try:
        now = datetime.now(UTC)
        token = {
            "userId": "u1",
            "pluginId": "premium.tool",
            "licenseType": "pro",
            "expiresAt": (now + timedelta(days=30)).isoformat(),
            "offlineGraceUntil": (now + timedelta(days=44)).isoformat(),
            "signature": "abcd",
        }
        resp = await client.post("/api/plugins/premium.tool/license", json=token)
        assert resp.status_code == 400
        assert "CIAREN_MARKETPLACE_LICENSE_ISSUER_KEYS" in resp.json()["detail"]
        # Nothing was cached: removing finds no token.
        resp = await client.delete("/api/plugins/premium.tool/license")
        assert resp.status_code == 404
    finally:
        get_settings.cache_clear()


async def test_bad_paste_never_clobbers_working_license(client, monkeypatch, tmp_path):
    """An invalid paste is rejected before saving, so the working cached token
    keeps validating afterwards."""
    from app.core.config import get_settings
    from app.plugin_api import signing

    if not signing.signing_available():
        pytest.skip("cryptography not installed")

    priv, pub = signing.generate_keypair()
    forger_priv, _ = signing.generate_keypair()
    monkeypatch.setenv("CIAREN_MARKETPLACE_LICENSE_ISSUER_KEYS", json.dumps([pub]))
    monkeypatch.setenv("CIAREN_LICENSE_DIR", str(tmp_path / "licenses"))
    get_settings.cache_clear()
    reset_registry()
    try:
        ok = await client.post("/api/plugins/premium.tool/license", json=_signed_token(priv, "premium.tool"))
        assert ok.status_code == 200 and ok.json()["valid"] is True

        bad = await client.post("/api/plugins/premium.tool/license", json=_signed_token(forger_priv, "premium.tool"))
        assert bad.status_code == 400

        status = await client.get("/api/plugins/premium.tool/license")
        assert status.json()["valid"] is True
    finally:
        get_settings.cache_clear()


_VENDOR_PROVIDER_MODULE = """
import os

from app.plugin_api import Plugin, PluginMetadata
from app.plugins.licensing import TokenLicenseProvider


class VendorLicensingPlugin(Plugin):
    def metadata(self):
        return PluginMetadata(id="vendor.licensing", name="Vendor Licensing", version="1.0.0")

    def register(self, registry):
        registry.register_license_provider(TokenLicenseProvider(os.environ["TEST_VENDOR_LICENSE_PUB"]))


PLUGIN = VendorLicensingPlugin()
"""


async def test_vendor_provider_vets_paste_and_rolls_back_bad_token(client, monkeypatch, tmp_path):
    """With no issuer keys but a plugin-registered provider, activation asks that
    provider (post-save) and rolls the cache back when it rejects the paste —
    the vendor-licensing path can't be tricked into a false success either."""
    from app.plugin_api import signing

    if not signing.signing_available():
        pytest.skip("cryptography not installed")

    monkeypatch.delenv("CIAREN_MARKETPLACE_LICENSE_ISSUER_KEYS", raising=False)
    monkeypatch.setenv("CIAREN_LICENSE_DIR", str(tmp_path / "licenses"))
    vendor_priv, vendor_pub = signing.generate_keypair()
    forger_priv, _ = signing.generate_keypair()
    monkeypatch.setenv("TEST_VENDOR_LICENSE_PUB", vendor_pub)

    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    plug = tmp_path / "installed" / "vendor-licensing"
    plug.mkdir(parents=True)
    (plug / "ciaren-plugin.json").write_text(
        json.dumps(
            {
                "id": "vendor.licensing",
                "name": "Vendor Licensing",
                "version": "1.0.0",
                "publisher": "vendor",
                "ciaren": ">=0.1",
                "entrypoint": "vendor_license_plugin:PLUGIN",
            }
        ),
        encoding="utf-8",
    )
    (plug / "vendor_license_plugin.py").write_text(_VENDOR_PROVIDER_MODULE, encoding="utf-8")
    reset_registry()

    # Approve the vendor plugin so its provider registers.
    resp = await client.post("/api/plugins/vendor.licensing/enable")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "loaded"

    # A vendor-signed token activates: the provider validates it after saving.
    ok = await client.post("/api/plugins/premium.tool/license", json=_signed_token(vendor_priv, "premium.tool"))
    assert ok.status_code == 200, ok.text
    assert ok.json()["valid"] is True

    # A forged paste is rejected and the working token is restored, not clobbered.
    bad = await client.post("/api/plugins/premium.tool/license", json=_signed_token(forger_priv, "premium.tool"))
    assert bad.status_code == 400
    assert "rejected" in bad.json()["detail"]
    status = await client.get("/api/plugins/premium.tool/license")
    assert status.json()["valid"] is True


async def test_marketplace_reports_update_available(client, monkeypatch, tmp_path, hello_ciarenplugin):
    from app.core.config import get_settings

    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")

    # Install the current hello, then advertise a newer build in the catalog.
    await client.post(
        "/api/plugins/install",
        files={"file": ("hello.ciarenplugin", hello_ciarenplugin.read_bytes(), "application/octet-stream")},
    )
    market = tmp_path / "market"
    market.mkdir()
    newer = _pack_hello_variant(tmp_path, version="0.2.0")
    artifact = market / newer.name
    artifact.write_bytes(newer.read_bytes())
    add_to_index_file(market / "index.json", artifact)
    monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", str(market / "index.json"))
    get_settings.cache_clear()

    listing = await client.get("/api/marketplace")
    entry = next(e for e in listing.json()["plugins"] if e["id"] == "community.hello")
    assert entry["installed"] is True
    assert entry["installed_version"] == "0.1.0-alpha.1"
    assert entry["update_available"] is True

    # "Update" is a forced reinstall through the same verified path.
    updated = await client.post("/api/marketplace/community.hello/install")
    assert updated.status_code == 200, updated.text
    assert updated.json()["plugin"]["version"] == "0.2.0"

    relisting = await client.get("/api/marketplace")
    entry2 = next(e for e in relisting.json()["plugins"] if e["id"] == "community.hello")
    assert entry2["update_available"] is False


async def test_marketplace_revoked_blocks_install_and_flags_installed(
    client, monkeypatch, tmp_path, hello_ciarenplugin
):
    import json as _json

    from app.core.config import get_settings

    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    await client.post(
        "/api/plugins/install",
        files={"file": ("hello.ciarenplugin", hello_ciarenplugin.read_bytes(), "application/octet-stream")},
    )

    market = tmp_path / "market"
    market.mkdir()
    artifact = market / "community.hello-0.1.0.ciarenplugin"
    artifact.write_bytes(hello_ciarenplugin.read_bytes())
    index_path = market / "index.json"
    add_to_index_file(index_path, artifact)
    raw = _json.loads(index_path.read_text(encoding="utf-8"))
    raw["revoked"] = ["community.hello"]
    index_path.write_text(_json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", str(index_path))
    get_settings.cache_clear()

    listing = await client.get("/api/marketplace")
    body = listing.json()
    assert body["revoked_installed"] == ["community.hello"]
    entry = next(e for e in body["plugins"] if e["id"] == "community.hello")
    assert entry["revoked"] is True

    resp = await client.post("/api/marketplace/community.hello/install")
    assert resp.status_code == 400
    assert "revoked" in resp.json()["detail"]


async def test_marketplace_unusable_index_is_a_clean_400(client, monkeypatch, tmp_path):
    from app.core.config import get_settings

    market = tmp_path / "market"
    market.mkdir()
    (market / "index.json").write_text('{"schemaVersion": "9.0.0", "plugins": []}', encoding="utf-8")
    monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", str(market / "index.json"))
    get_settings.cache_clear()

    resp = await client.get("/api/marketplace")
    assert resp.status_code == 400
    assert "schemaVersion" in resp.json()["detail"]


async def test_marketplace_trust_shows_trusted_for_verified_artifact(client, monkeypatch, tmp_path, hello_ciarenplugin):
    """Conversely, a valid signature from a trusted key earns the trusted badge."""
    import json as _json

    from app.core.config import get_settings
    from app.plugin_api import signing

    if not signing.signing_available():
        pytest.skip("cryptography not installed")

    market = tmp_path / "market"
    market.mkdir()
    artifact = market / "community.hello-0.1.0.ciarenplugin"
    artifact.write_bytes(hello_ciarenplugin.read_bytes())
    priv, pub = signing.generate_keypair()
    package.sign_package(artifact, priv, key_id="kid-test")
    index_path = market / "index.json"
    add_to_index_file(index_path, artifact)

    monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", str(index_path))
    monkeypatch.setenv("CIAREN_TRUSTED_PLUGIN_KEYS", _json.dumps({"kid-test": pub}))
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    get_settings.cache_clear()

    listing = await client.get("/api/marketplace")
    entry = next(e for e in listing.json()["plugins"] if e["id"] == "community.hello")
    assert entry["trust"] == "trusted"


async def test_official_badge_derives_from_pinned_publisher_key(client, monkeypatch, tmp_path, hello_ciarenplugin):
    """A package signed by a key pinned into the app (OFFICIAL_PUBLISHER_KEYS)
    surfaces as official — in the catalog trust tier and on the installed plugin —
    while a user-added trusted key stays plain trusted."""
    from app.core.config import get_settings
    from app.plugin_api import signing

    if not signing.signing_available():
        pytest.skip("cryptography not installed")

    market = tmp_path / "market"
    market.mkdir()
    artifact = market / "community.hello-0.1.0.ciarenplugin"
    artifact.write_bytes(hello_ciarenplugin.read_bytes())
    priv, pub = signing.generate_keypair()
    package.sign_package(artifact, priv, key_id="ciaren-official-test")
    monkeypatch.setitem(package.OFFICIAL_PUBLISHER_KEYS, "ciaren-official-test", pub)
    index_path = market / "index.json"
    add_to_index_file(index_path, artifact)

    monkeypatch.setenv("CIAREN_MARKETPLACE_INDEX", str(index_path))
    _point_plugin_dirs_at(monkeypatch, tmp_path / "installed")
    get_settings.cache_clear()

    # Catalog: official, not merely trusted (no user-configured keys involved —
    # pinned official keys are always part of the trusted set).
    listing = await client.get("/api/marketplace")
    entry = next(e for e in listing.json()["plugins"] if e["id"] == "community.hello")
    assert entry["trust"] == "official"

    # Installed plugin: signature outcome stays "trusted" (policy-compatible),
    # with the first-party flag alongside it.
    installed = await client.post("/api/marketplace/community.hello/install")
    assert installed.status_code == 200, installed.text
    assert installed.json()["plugin"]["signature"] == "trusted"
    assert installed.json()["plugin"]["official"] is True


def test_verify_result_official_property(tmp_path, monkeypatch, hello_ciarenplugin):
    from app.plugin_api import signing

    if not signing.signing_available():
        pytest.skip("cryptography not installed")

    priv, pub = signing.generate_keypair()
    package.sign_package(hello_ciarenplugin, priv, key_id="some-key")
    # Trusted via explicit keys, but not pinned → not official.
    result = package.verify_package(hello_ciarenplugin, {"some-key": pub})
    assert result.outcome == "trusted" and result.official is False
    # Same signature with the key pinned as official → official.
    monkeypatch.setitem(package.OFFICIAL_PUBLISHER_KEYS, "some-key", pub)
    result = package.verify_package(hello_ciarenplugin, {"some-key": pub})
    assert result.official is True
