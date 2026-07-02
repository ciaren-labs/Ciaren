"""Generating a plugin manifest from the plugin's own code (single source of truth)."""

from __future__ import annotations

import json
from pathlib import Path

from app.plugin_api import (
    NodeProvider,
    NodeSpec,
    Permission,
    Plugin,
    PluginMetadata,
    PortSpec,
    ServiceRegistry,
    validate_manifest,
)
from app.plugins.authoring import manifest_from_plugin, manifest_json_from_plugin

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_MANIFEST = REPO_ROOT / "examples" / "plugins" / "hello-node-plugin" / "ciaren-plugin.json"


def _hello_plugin() -> Plugin:
    # Import the committed example the same way the loader would.
    import sys

    plugin_dir = EXAMPLE_MANIFEST.parent
    if str(plugin_dir) not in sys.path:
        sys.path.append(str(plugin_dir))
    from ciaren_hello.plugin import HelloPlugin

    return HelloPlugin()


def test_generated_manifest_matches_committed_example():
    """The hand-committed example manifest must equal what the generator derives
    from the plugin's code — this both validates the generator and permanently
    guards the example against manifest/code drift."""
    generated = manifest_from_plugin(_hello_plugin(), entrypoint="ciaren_hello.plugin:HelloPlugin")
    committed = validate_manifest(json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8")))
    assert generated == committed


def test_generator_unions_node_permissions_and_capabilities():
    """Permissions/capabilities declared on a plugin's *nodes* (not just its
    metadata) are surfaced in the manifest, so the gating UI sees everything the
    plugin can do."""

    class _Provider(NodeProvider):
        def nodes(self) -> list[NodeSpec]:
            return [
                NodeSpec(
                    id="x.reader",
                    label="Reader",
                    category="input",
                    provider="community.x",
                    permissions=(Permission.filesystem_read,),
                    capabilities=("cap.read",),
                    inputs=(),
                    outputs=(PortSpec(id="out"),),
                )
            ]

    class _Plugin(Plugin):
        def metadata(self) -> PluginMetadata:
            return PluginMetadata(
                id="community.x",
                name="X",
                permissions=(Permission.network,),
                capabilities=("cap.meta",),
            )

        def register(self, registry: ServiceRegistry) -> None:
            registry.register_node_provider(_Provider())

    manifest = manifest_from_plugin(_Plugin(), entrypoint="x:Plugin")
    assert set(manifest.permissions) == {Permission.network, Permission.filesystem_read}
    assert set(manifest.capabilities) == {"cap.meta", "cap.read"}
    assert manifest.ui.nodes == ["x.reader"]
    assert manifest.ui.node_categories == {"x.reader": "input"}


def test_manifest_json_is_valid_and_reparses():
    rendered = manifest_json_from_plugin(_hello_plugin(), entrypoint="ciaren_hello.plugin:HelloPlugin")
    data = json.loads(rendered)
    assert data["id"] == "community.hello"
    assert data["ui"]["nodeCategories"] == {"hello.greeting": "columns"}  # camelCase alias
    # Round-trips back through the loader's validator.
    assert validate_manifest(data).id == "community.hello"
