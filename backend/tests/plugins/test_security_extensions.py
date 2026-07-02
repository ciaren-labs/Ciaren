"""Security posture of the new extension points (connectors + model types).

The existing suites cover package verification (digest/signature/TOFU) and the
approval gate for node contributions; these tests pin the same guarantees onto
connectors and model providers:

- an unapproved plugin's code is never imported, so its connectors/model types
  simply don't exist anywhere in the system;
- approval brings them in live, and disabling removes them live;
- the SSRF host guard runs *before* a plugin connector runtime is invoked.
"""

from __future__ import annotations

import json
import textwrap

import pytest

from app.core.config import get_settings
from app.plugins import get_registry, reset_registry
from app.plugins.connectors import plugin_connector
from app.plugins.runtime import reload_plugins
from app.plugins.state import PluginStateStore

PLUGIN_ID = "community.sec-ext"

PLUGIN_MODULE = """
from typing import Any

from app.plugin_api import (
    ConnectorProvider,
    ConnectorRuntime,
    ConnectorSpec,
    ConnectorTestResult,
    ModelProvider,
    ModelTypeSpec,
    Plugin,
    PluginMetadata,
    ServiceRegistry,
)

#: Import-tracking marker: the loader must never import this module while gated.
import os
os.environ["SEC_EXT_IMPORTED"] = "1"


class _Runtime(ConnectorRuntime):
    def test(self, config):
        return ConnectorTestResult(ok=True, message="reached")

    def read(self, config, options):
        raise ValueError("not needed in these tests")


class _Connectors(ConnectorProvider):
    def connectors(self):
        return [
            ConnectorSpec(
                id="sec-api",
                label="Sec API",
                kind="api",
                provider="community.sec-ext",
                metadata={"needs_host": True},
            )
        ]

    def connector_implementations(self):
        return {"sec-api": _Runtime()}


class _Models(ModelProvider):
    def model_types(self):
        return [
            ModelTypeSpec(id="sec_model", label="Sec Model", task="classification", provider="community.sec-ext")
        ]

    def model_builders(self):
        return {"sec_model": lambda params, seed: object()}


class SecExtPlugin(Plugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(id="community.sec-ext", name="Sec Ext")

    def register(self, registry: ServiceRegistry) -> None:
        registry.register_connector_provider(_Connectors())
        registry.register_model_provider(_Models())
"""

MANIFEST = {
    "id": PLUGIN_ID,
    "name": "Sec Ext",
    "version": "0.1.0",
    "ciaren": ">=0.1",
    "entrypoint": "sec_ext.plugin:SecExtPlugin",
    "permissions": ["network", "credentials"],
}


@pytest.fixture
def plugin_on_disk(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "sec-ext-plugin"
    pkg = plugin_dir / "sec_ext"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "plugin.py").write_text(textwrap.dedent(PLUGIN_MODULE), encoding="utf-8")
    (plugin_dir / "ciaren-plugin.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    monkeypatch.setenv("CIAREN_PLUGINS_DIR", str(tmp_path / "plugins"))
    monkeypatch.delenv("SEC_EXT_IMPORTED", raising=False)
    reset_registry()
    yield
    reset_registry()


def _approve() -> None:
    state = PluginStateStore()
    state.set_approved(PLUGIN_ID, True)
    state.grant(PLUGIN_ID, MANIFEST["permissions"])
    state.save()
    reload_plugins()


def test_unapproved_plugin_contributes_nothing_and_never_imports(plugin_on_disk, monkeypatch):
    registry = get_registry()
    # Gated: discovered but not loaded.
    assert registry.connector_spec("sec-api") is None
    assert registry.model_type_spec("sec_model") is None
    assert plugin_connector("sec-api") is None
    import os

    assert "SEC_EXT_IMPORTED" not in os.environ, "gated plugin code must never be imported"

    from app.ml.models import get_model_spec

    with pytest.raises(ValueError, match="Unknown model_type"):
        get_model_spec("sec_model")


def test_approval_brings_contributions_in_and_disable_removes_them(plugin_on_disk):
    _approve()
    registry = get_registry()
    assert registry.connector_spec("sec-api") is not None
    assert plugin_connector("sec-api") is not None
    from app.ml.models import get_model_spec

    assert get_model_spec("sec_model").task == "classification"

    # Disabling takes everything out again on the live reload.
    state = PluginStateStore()
    state.set_enabled(PLUGIN_ID, False)
    state.save()
    reload_plugins()
    assert get_registry().connector_spec("sec-api") is None
    assert plugin_connector("sec-api") is None
    with pytest.raises(ValueError, match="Unknown model_type"):
        get_model_spec("sec_model")


async def test_ssrf_guard_blocks_private_hosts_before_the_runtime_runs(plugin_on_disk, db_session, monkeypatch):
    _approve()
    monkeypatch.setenv("CIAREN_CONNECTOR_BLOCK_PRIVATE_HOSTS", "true")
    get_settings.cache_clear()
    try:
        from app.schemas.connection import ConnectionCreate
        from app.services.connection_service import ConnectionService

        service = ConnectionService(db_session)
        result = await service.test_config(
            ConnectionCreate(name="internal", provider="sec-api", host="169.254.169.254")
        )
        assert result.ok is False
        assert "blocked" in result.message
    finally:
        get_settings.cache_clear()


async def test_ssrf_guard_off_lets_the_runtime_answer(plugin_on_disk, db_session):
    _approve()
    from app.schemas.connection import ConnectionCreate
    from app.services.connection_service import ConnectionService

    service = ConnectionService(db_session)
    result = await service.test_config(ConnectionCreate(name="local", provider="sec-api", host="127.0.0.1"))
    assert result.ok is True
    assert result.message == "reached"
