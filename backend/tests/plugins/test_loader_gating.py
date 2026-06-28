"""The loader gates manifest-bearing plugins by enable/disable + permissions."""

from __future__ import annotations

from app.plugin_api import (
    NodeProvider,
    NodeSpec,
    Permission,
    Plugin,
    PluginManifest,
    PluginMetadata,
    PortSpec,
    ServiceRegistry,
)
from app.plugins.loader import PluginCandidate, load_plugins
from app.plugins.state import PluginStateStore

PLUGIN_ID = "test.gated"


class _Nodes(NodeProvider):
    def nodes(self) -> list[NodeSpec]:
        return [NodeSpec(id="gated.node", label="Gated", category="columns", outputs=(PortSpec(id="out"),))]


class _GatedPlugin(Plugin):
    loaded = False

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(id=PLUGIN_ID, name="Gated", permissions=(Permission.network,))

    def register(self, registry: ServiceRegistry) -> None:
        _GatedPlugin.loaded = True
        registry.register_node_provider(_Nodes())


def _manifest(perms: list[Permission]) -> PluginManifest:
    return PluginManifest(
        id=PLUGIN_ID,
        name="Gated",
        version="1.0.0",
        entrypoint="x:Y",
        permissions=perms,
    )


def _candidate(perms: list[Permission]) -> PluginCandidate:
    _GatedPlugin.loaded = False
    return PluginCandidate(source="dir:gated", load=lambda: _GatedPlugin(), manifest=_manifest(perms))


def _load(perms: list[Permission], state: PluginStateStore):
    registry = ServiceRegistry()
    result = load_plugins(
        registry,
        include_entry_points=False,
        extra=[_candidate(perms)],
        state=state,
        flowframe_version_str="0.1.0",
    )
    return registry, result


def test_plugin_with_ungranted_permission_is_gated_not_loaded(tmp_path):
    state = PluginStateStore(tmp_path / "s.json")
    registry, result = _load([Permission.network], state)
    assert result.loaded == []
    assert len(result.gated) == 1
    gated = result.gated[0]
    assert gated.reason == "needs_permissions"
    assert gated.missing_permissions == [Permission.network]
    # The plugin's code (register) was never run, and no node was registered.
    assert _GatedPlugin.loaded is False
    assert registry.node_spec("gated.node") is None


def test_plugin_loads_once_permission_granted(tmp_path):
    state = PluginStateStore(tmp_path / "s.json")
    state.grant(PLUGIN_ID, [Permission.network])
    registry, result = _load([Permission.network], state)
    assert len(result.loaded) == 1
    assert result.gated == []
    assert _GatedPlugin.loaded is True
    assert registry.node_spec("gated.node") is not None


def test_disabled_plugin_is_gated(tmp_path):
    state = PluginStateStore(tmp_path / "s.json")
    state.set_enabled(PLUGIN_ID, False)
    # Even with no permissions required, a disabled plugin does not load.
    registry, result = _load([], state)
    assert result.loaded == []
    assert result.gated[0].reason == "disabled"
    assert _GatedPlugin.loaded is False


def test_no_permissions_loads_by_default(tmp_path):
    state = PluginStateStore(tmp_path / "s.json")
    _, result = _load([], state)
    assert len(result.loaded) == 1
    assert result.gated == []


def test_discovery_is_recorded_in_state(tmp_path):
    path = tmp_path / "s.json"
    state = PluginStateStore(path)
    _load([Permission.network], state)
    # load_plugins saves the store; first_seen was recorded for the discovered id.
    reread = PluginStateStore(path)
    assert reread.entry(PLUGIN_ID) is not None


def test_manifestless_candidate_is_not_gated(tmp_path):
    # A candidate without a manifest (e.g. an installed entry-point package) loads
    # regardless of state — gating is the drop-in/marketplace path only.
    state = PluginStateStore(tmp_path / "s.json")
    state.set_enabled(PLUGIN_ID, False)
    registry = ServiceRegistry()
    result = load_plugins(
        registry,
        include_entry_points=False,
        extra=[PluginCandidate(source="entry_point:x", load=lambda: _GatedPlugin(), manifest=None)],
        state=state,
        flowframe_version_str="0.1.0",
    )
    assert len(result.loaded) == 1
