"""The NodeContext the host assembles for a plugin's runtimes — in particular
that a plugin's own signed license token is threaded through so a thin-client
paid node can authenticate to its vendor server for server-side execution."""

from __future__ import annotations

import json

from app.plugins.licensing import LicenseCache, LicenseToken
from app.plugins.runtime import _node_context_for
from app.plugins.state import PluginStateStore


def _token(plugin_id: str) -> LicenseToken:
    return LicenseToken(
        userId="u1",
        pluginId=plugin_id,
        expiresAt="2030-01-01T00:00:00Z",
        offlineGraceUntil="2030-02-01T00:00:00Z",
    )


def test_context_has_no_token_without_a_license(monkeypatch, tmp_path):
    monkeypatch.setenv("CIAREN_LICENSE_DIR", str(tmp_path / "lic"))
    monkeypatch.setenv("CIAREN_PLUGIN_STATE_FILE", str(tmp_path / "state.json"))
    ctx = _node_context_for("acme.premium", PluginStateStore())
    assert ctx.license_token == ""


def test_context_carries_the_plugins_own_license_token(monkeypatch, tmp_path):
    monkeypatch.setenv("CIAREN_LICENSE_DIR", str(tmp_path / "lic"))
    monkeypatch.setenv("CIAREN_PLUGIN_STATE_FILE", str(tmp_path / "state.json"))
    LicenseCache().save(_token("acme.premium"))

    ctx = _node_context_for("acme.premium", PluginStateStore())
    assert ctx.license_token, "the plugin's own token should be forwarded to its runtime"
    assert json.loads(ctx.license_token)["pluginId"] == "acme.premium"


def test_context_never_leaks_another_plugins_token(monkeypatch, tmp_path):
    monkeypatch.setenv("CIAREN_LICENSE_DIR", str(tmp_path / "lic"))
    monkeypatch.setenv("CIAREN_PLUGIN_STATE_FILE", str(tmp_path / "state.json"))
    LicenseCache().save(_token("acme.premium"))

    # A different plugin's context must not receive acme.premium's token.
    ctx = _node_context_for("other.plugin", PluginStateStore())
    assert ctx.license_token == ""
