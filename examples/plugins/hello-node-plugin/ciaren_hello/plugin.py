"""The Hello plugin: contributes one executable node, ``hello.greeting``.

It demonstrates the full pipeline — discovery → manifest → registry → catalog —
**and** execution: the node ships a :class:`NodeRuntime` so it runs in previews
and runs and exports to code like a built-in. The runtime works on pandas;
Ciaren bridges it to the active engine (polars/pandas). The plugin depends
only on the Ciaren plugin contract (``app.plugin_api``) and pandas.
"""

from __future__ import annotations

from typing import Any

from app.plugin_api import (
    NodeProvider,
    NodeRuntime,
    NodeSpec,
    Plugin,
    PluginMetadata,
    PortSpec,
    ServiceRegistry,
)

PLUGIN_ID = "community.hello"
NODE_ID = "hello.greeting"


def _greeting(config: dict[str, Any]) -> str:
    return f"Hello, {config.get('name') or 'world'}!"


def _column(config: dict[str, Any]) -> str:
    return config.get("column") or "greeting"


class HelloGreetingRuntime(NodeRuntime):
    """Adds a constant greeting column to the input frame."""

    def validate_config(self, config: dict[str, Any]) -> None:
        if "column" in config and not str(config["column"]).strip():
            raise ValueError("hello.greeting: 'column' must not be empty")

    def execute(self, inputs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        df = inputs["in"].copy()
        df[_column(config)] = _greeting(config)
        return {"out": df}

    def to_python_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str:
        return f"{output_vars['out']} = {input_vars['in']}.assign(**{{{_column(config)!r}: {_greeting(config)!r}}})"


class _HelloNodeProvider(NodeProvider):
    def nodes(self) -> list[NodeSpec]:
        return [
            NodeSpec(
                id=NODE_ID,
                label="Add Greeting",
                category="columns",
                description="Example plugin node: adds a greeting column.",
                provider=PLUGIN_ID,
                version="0.1.0-alpha.1",
                inputs=(PortSpec(id="in"),),
                outputs=(PortSpec(id="out"),),
                default_config={"column": "greeting", "name": "world"},
                capabilities=("node.hello",),
            )
        ]

    def node_implementations(self) -> dict[str, Any]:
        return {NODE_ID: HelloGreetingRuntime()}


class HelloPlugin(Plugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id=PLUGIN_ID,
            name="Hello Plugin",
            version="0.1.0-alpha.1",
            publisher="community",
            description="A minimal example plugin that contributes one executable node.",
        )

    def register(self, registry: ServiceRegistry) -> None:
        registry.register_node_provider(_HelloNodeProvider())
