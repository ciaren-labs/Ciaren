"""Plugin loader: discovery, manifest validation, compatibility, error isolation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.plugin_api import (
    DuplicateRegistrationError,
    NodeProvider,
    NodeSpec,
    Plugin,
    PluginManifest,
    PluginMetadata,
    ServiceRegistry,
)
from app.plugins.builtin import BuiltinNodeProvider
from app.plugins.loader import (
    PluginCandidate,
    default_plugin_dirs,
    load_entrypoint,
    load_plugins,
)

# examples/plugins lives at the repo root, two levels above backend/.
REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "examples" / "plugins"


def _node_provider(node_id: str) -> NodeProvider:
    class _P(NodeProvider):
        def nodes(self):
            return [NodeSpec(id=node_id, label=node_id, category="columns", provider="test.plugin")]

    return _P()


def _plugin(plugin_id: str, node_id: str) -> Plugin:
    class _Plugin(Plugin):
        def metadata(self):
            return PluginMetadata(id=plugin_id, name=plugin_id)

        def register(self, registry):
            registry.register_node_provider(_node_provider(node_id))

    return _Plugin()


def _candidate(plugin: Plugin, source: str = "test", manifest: PluginManifest | None = None) -> PluginCandidate:
    return PluginCandidate(source=source, load=lambda: plugin, manifest=manifest)


def test_loads_injected_plugin():
    reg = ServiceRegistry()
    result = load_plugins(reg, include_entry_points=False, extra=[_candidate(_plugin("p1", "n1"))])
    assert [p.metadata.id for p in result.loaded] == ["p1"]
    assert result.errors == []
    assert reg.node_spec("n1") is not None


def test_one_failing_plugin_does_not_block_others():
    reg = ServiceRegistry()

    def _boom() -> Plugin:
        raise RuntimeError("import exploded")

    candidates = [
        PluginCandidate(source="bad", load=_boom),
        _candidate(_plugin("good", "ok"), source="good"),
    ]
    result = load_plugins(reg, include_entry_points=False, extra=candidates)
    assert [p.metadata.id for p in result.loaded] == ["good"]
    assert [e.source for e in result.errors] == ["bad"]
    assert "import exploded" in result.errors[0].error
    assert reg.node_spec("ok") is not None


def test_incompatible_plugin_is_rejected_before_loading():
    reg = ServiceRegistry()
    loaded_flag = {"ran": False}

    def _load() -> Plugin:
        loaded_flag["ran"] = True
        return _plugin("future", "n")

    manifest = PluginManifest(id="future", name="Future", ciaren=">=99.0")
    cand = PluginCandidate(source="dir:future", load=_load, manifest=manifest)
    result = load_plugins(reg, include_entry_points=False, extra=[cand], ciaren_version_str="0.1.0")
    assert result.loaded == []
    assert len(result.errors) == 1
    assert loaded_flag["ran"] is False  # entry point never imported
    assert reg.node_spec("n") is None


def test_api_incompatible_plugin_is_rejected_before_loading():
    reg = ServiceRegistry()
    loaded_flag = {"ran": False}

    def _load() -> Plugin:
        loaded_flag["ran"] = True
        return _plugin("future_api", "n")

    # Plugin built against contract 2.0; backend provides 1.1 (different major).
    manifest = PluginManifest(id="future_api", name="Future API", api_version="2.0")
    cand = PluginCandidate(source="dir:future_api", load=_load, manifest=manifest)
    result = load_plugins(reg, include_entry_points=False, extra=[cand], api_version_str="1.1")
    assert result.loaded == []
    assert len(result.errors) == 1
    assert "plugin-API" in result.errors[0].error
    assert loaded_flag["ran"] is False  # entry point never imported
    assert reg.node_spec("n") is None


def test_api_compatible_older_plugin_still_loads():
    reg = ServiceRegistry()
    manifest = PluginManifest(id="old_api", name="Old API", api_version="1.0")
    cand = _candidate(_plugin("old_api", "n"), source="dir:old_api", manifest=manifest)
    result = load_plugins(reg, include_entry_points=False, extra=[cand], api_version_str="1.1")
    assert [p.metadata.id for p in result.loaded] == ["old_api"]
    assert result.errors == []
    assert reg.node_spec("n") is not None


def test_api_plugin_needing_newer_minor_is_rejected():
    """Same major, but the plugin needs a minor the backend doesn't provide."""
    reg = ServiceRegistry()
    manifest = PluginManifest(id="needs_minor", name="Needs 1.2", api_version="1.2")
    cand = _candidate(_plugin("needs_minor", "n"), source="dir:needs_minor", manifest=manifest)
    result = load_plugins(reg, include_entry_points=False, extra=[cand], api_version_str="1.1")
    assert result.loaded == []
    assert len(result.errors) == 1
    assert "plugin-API 1.2" in result.errors[0].error
    assert "1.1" in result.errors[0].error


def test_manifestless_plugin_is_not_api_gated():
    """Entry-point plugins ship no manifest; the contract gate only applies to
    manifest-bearing candidates, so they load regardless of the backend contract."""
    reg = ServiceRegistry()
    result = load_plugins(
        reg,
        include_entry_points=False,
        extra=[_candidate(_plugin("ep", "n"))],  # no manifest
        api_version_str="9.9",
    )
    assert [p.metadata.id for p in result.loaded] == ["ep"]
    assert result.errors == []


def test_manifest_default_api_version_loads_on_current_backend():
    """A manifest that omits api_version defaults to 1.0, which must load on the
    real backend contract (so pre-field manifests keep working)."""
    from app.plugin_api import PLUGIN_API_VERSION

    reg = ServiceRegistry()
    manifest = PluginManifest(id="defaulted", name="Defaulted")  # api_version defaults to "1.0"
    cand = _candidate(_plugin("defaulted", "n"), source="dir:defaulted", manifest=manifest)
    result = load_plugins(reg, include_entry_points=False, extra=[cand], api_version_str=PLUGIN_API_VERSION)
    assert [p.metadata.id for p in result.loaded] == ["defaulted"]
    assert result.errors == []


def test_app_incompat_is_reported_before_api_incompat():
    """When a plugin is incompatible on both axes, the app-version check runs first
    so the surfaced error names the Ciaren version mismatch."""
    reg = ServiceRegistry()
    manifest = PluginManifest(id="both_bad", name="Both", ciaren=">=99.0", api_version="2.0")
    cand = _candidate(_plugin("both_bad", "n"), source="dir:both_bad", manifest=manifest)
    result = load_plugins(
        reg,
        include_entry_points=False,
        extra=[cand],
        ciaren_version_str="0.1.0",
        api_version_str="1.1",
    )
    assert result.loaded == []
    assert "requires Ciaren" in result.errors[0].error
    assert "plugin-API" not in result.errors[0].error


def test_plugin_colliding_with_core_node_is_isolated_and_rolled_back():
    reg = ServiceRegistry()
    reg.register_node_provider(BuiltinNodeProvider())
    before = {s.id for s in reg.node_specs()}

    # A plugin that tries to shadow a core node id ("filterRows") plus add its own.
    class _Collider(Plugin):
        def metadata(self):
            return PluginMetadata(id="collider", name="Collider")

        def register(self, registry):
            class _P(NodeProvider):
                def nodes(self):
                    return [
                        NodeSpec(id="plugin.extra", label="Extra", category="columns"),
                        NodeSpec(id="filterRows", label="Hijack", category="columns"),
                    ]

            registry.register_node_provider(_P())

    result = load_plugins(reg, include_entry_points=False, extra=[_candidate(_Collider(), source="collider")])
    assert [e.source for e in result.errors] == ["collider"]
    assert result.loaded == []
    # Rolled back: neither the hijack nor the plugin's other node stuck.
    assert {s.id for s in reg.node_specs()} == before
    assert reg.node_spec("plugin.extra") is None
    assert "collider" not in [p.id for p in reg.plugins()]


def test_duplicate_registration_error_type():
    reg = ServiceRegistry()
    reg.register_node_provider(_node_provider("dup"))
    with pytest.raises(DuplicateRegistrationError):
        reg.register_node_provider(_node_provider("dup"))


# -- local directory discovery (the bundled example plugin) -------------------


def test_local_dir_discovery_loads_example_plugin():
    assert EXAMPLES_DIR.is_dir(), f"missing example dir: {EXAMPLES_DIR}"
    reg = ServiceRegistry()
    reg.register_node_provider(BuiltinNodeProvider())
    result = load_plugins(reg, include_entry_points=False, plugin_dirs=[EXAMPLES_DIR])

    ids = [p.metadata.id for p in result.loaded]
    assert "community.hello" in ids, result.errors
    spec = reg.node_spec("hello.greeting")
    assert spec is not None
    assert spec.provider == "community.hello"
    assert spec.category == "columns"


def test_load_entrypoint_resolves_example():
    import sys

    plugin_dir = EXAMPLES_DIR / "hello-node-plugin"
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))
    plugin = load_entrypoint("ciaren_hello.plugin:HelloPlugin")
    assert plugin.metadata().id == "community.hello"


def test_local_plugin_dir_is_appended_not_prepended(tmp_path, monkeypatch):
    """A local plugin dir must go on the *end* of sys.path so a plugin can never
    shadow a stdlib/core module (e.g. its own json.py) for the whole process."""
    import sys

    plugin_dir = tmp_path / "shadowy"
    pkg = plugin_dir / "shadowy_plugin"
    pkg.mkdir(parents=True)
    (plugin_dir / "ciaren-plugin.json").write_text(
        json.dumps(
            {
                "id": "community.shadowy",
                "name": "Shadowy",
                "entrypoint": "shadowy_plugin:ShadowyPlugin",
            }
        ),
        encoding="utf-8",
    )
    (pkg / "__init__.py").write_text(
        "from app.plugin_api import Plugin, PluginMetadata\n"
        "class ShadowyPlugin(Plugin):\n"
        "    def metadata(self):\n"
        "        return PluginMetadata(id='community.shadowy', name='Shadowy')\n"
        "    def register(self, registry):\n"
        "        pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "path", list(sys.path))  # isolate the mutation
    reg = ServiceRegistry()
    result = load_plugins(reg, include_entry_points=False, plugin_dirs=[tmp_path])
    assert "community.shadowy" in [p.metadata.id for p in result.loaded], result.errors
    assert sys.path[-1] == str(plugin_dir)  # appended, not inserted at the front


def test_invalid_manifest_in_dir_is_an_error(tmp_path):
    plugin_dir = tmp_path / "broken"
    plugin_dir.mkdir()
    (plugin_dir / "ciaren-plugin.json").write_text("{ not valid json", encoding="utf-8")
    reg = ServiceRegistry()
    result = load_plugins(reg, include_entry_points=False, plugin_dirs=[tmp_path])
    assert result.loaded == []
    assert [e.source for e in result.errors] == ["dir:broken"]


def test_manifest_without_entrypoint_in_dir_is_an_error(tmp_path):
    plugin_dir = tmp_path / "noentry"
    plugin_dir.mkdir()
    (plugin_dir / "ciaren-plugin.json").write_text(json.dumps({"id": "x", "name": "X"}), encoding="utf-8")
    reg = ServiceRegistry()
    result = load_plugins(reg, include_entry_points=False, plugin_dirs=[tmp_path])
    assert result.loaded == []
    assert len(result.errors) == 1
    assert "entrypoint" in result.errors[0].error


def test_nonexistent_plugin_dir_is_skipped():
    reg = ServiceRegistry()
    result = load_plugins(reg, include_entry_points=False, plugin_dirs=["/no/such/dir/anywhere"])
    assert result.loaded == []
    assert result.errors == []


def test_default_plugin_dirs_respects_env(monkeypatch):
    monkeypatch.setenv("CIAREN_PLUGINS_DIR", "/a/b")
    dirs = default_plugin_dirs()
    assert "/a/b" in dirs
    assert any(d.endswith(".ciaren/plugins") or d.endswith(".ciaren\\plugins") for d in dirs)
