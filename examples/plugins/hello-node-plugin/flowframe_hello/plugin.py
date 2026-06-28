"""The Hello plugin: contributes a single catalog node.

In Phase 1 a plugin node appears in the catalog/palette (so the UI can show it)
via its :class:`NodeSpec`. Wiring a plugin-supplied node into the execution
engine is a later phase, so this provider returns no implementation — the spec
alone proves the discovery → manifest → registry → catalog pipeline end to end.
"""

from __future__ import annotations

from app.plugin_api import (
    NodeProvider,
    NodeSpec,
    Plugin,
    PluginMetadata,
    PortSpec,
    ServiceRegistry,
)

PLUGIN_ID = "community.hello"


class _HelloNodeProvider(NodeProvider):
    def nodes(self) -> list[NodeSpec]:
        return [
            NodeSpec(
                id="hello.greeting",
                label="Add Greeting",
                category="columns",
                description="Example plugin node: adds a greeting column.",
                provider=PLUGIN_ID,
                version="0.1.0",
                inputs=(PortSpec(id="in"),),
                outputs=(PortSpec(id="out"),),
                default_config={"column": "greeting", "name": "world"},
                capabilities=("node.hello",),
            )
        ]


class HelloPlugin(Plugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id=PLUGIN_ID,
            name="Hello Plugin",
            version="0.1.0",
            publisher="community",
            description="A minimal example plugin that contributes one catalog node.",
        )

    def register(self, registry: ServiceRegistry) -> None:
        registry.register_node_provider(_HelloNodeProvider())
