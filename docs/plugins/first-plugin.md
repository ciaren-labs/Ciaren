---
title: Build Your First Plugin (10 minutes)
description: A step-by-step tutorial — create a Ciaren plugin that adds a working node to the canvas, runs end-to-end, and exports to Python.
search: plugin tutorial first plugin getting started node provider runtime hello quickstart build
---

# Build Your First Plugin in 10 Minutes

By the end of this tutorial you'll have a working Ciaren plugin that adds a new
node to the canvas — one that runs in previews and runs, and exports to Python,
exactly like a built-in node. We'll build a small **"Add Greeting"** node that adds
a constant column.

This mirrors the runnable example in the repo at
[`examples/plugins/hello-node-plugin/`](https://github.com/ciaren-labs/Ciaren/tree/main/examples/plugins/hello-node-plugin)
— open it alongside this page if you'd like the finished version.

::: tip What you'll learn
The full path a plugin travels: **`Plugin` → provider → node spec → runtime →
discovery → canvas**. Once you've done it once, every other extension point
(connectors, engines, exporters, …) follows the same shape.
:::

## Prerequisites

- Ciaren installed and runnable (`ciaren serve` works). See
  [Installation](/guide/installation).
- Python 3.12+.
- A plugin depends only on the public plugin API (`app.plugin_api`) and pandas —
  never on Ciaren's internals.

## 1. Create the package

Make a folder with a Python package inside it:

```text
my-greeting-plugin/
├── ciaren_greeting/
│   ├── __init__.py
│   └── plugin.py
├── ciaren-plugin.json
└── pyproject.toml
```

```bash
mkdir -p my-greeting-plugin/ciaren_greeting
cd my-greeting-plugin
touch ciaren_greeting/__init__.py
```

## 2. Implement the plugin

A plugin contributes nodes through a **`NodeProvider`**. To make the node *run*
(not just appear in the catalog), the provider also hands Ciaren a
**`NodeRuntime`** keyed by node id.

Put this in `ciaren_greeting/plugin.py`:

```python
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

PLUGIN_ID = "community.greeting"
NODE_ID = "greeting.add"


class AddGreetingRuntime(NodeRuntime):
    """Adds a constant greeting column to the input frame."""

    def validate_config(self, config: dict[str, Any]) -> None:
        if "column" in config and not str(config["column"]).strip():
            raise ValueError("greeting.add: 'column' must not be empty")

    def execute(self, inputs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        df = inputs["in"].copy()
        column = config.get("column") or "greeting"
        df[column] = f"Hello, {config.get('name') or 'world'}!"
        return {"out": df}

    def to_python_code(self, input_vars, output_vars, config) -> str:
        column = config.get("column") or "greeting"
        greeting = f"Hello, {config.get('name') or 'world'}!"
        return f"{output_vars['out']} = {input_vars['in']}.assign(**{{{column!r}: {greeting!r}}})"


class _GreetingNodeProvider(NodeProvider):
    def nodes(self) -> list[NodeSpec]:
        return [
            NodeSpec(
                id=NODE_ID,
                label="Add Greeting",
                category="columns",
                description="Adds a constant greeting column.",
                provider=PLUGIN_ID,
                version="0.1.0",
                inputs=(PortSpec(id="in"),),
                outputs=(PortSpec(id="out"),),
                default_config={"column": "greeting", "name": "world"},
            )
        ]

    def node_implementations(self) -> dict[str, Any]:
        return {NODE_ID: AddGreetingRuntime()}


class GreetingPlugin(Plugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id=PLUGIN_ID,
            name="Greeting Plugin",
            version="0.1.0",
            publisher="community",
            description="Adds one node that writes a greeting column.",
        )

    def register(self, registry: ServiceRegistry) -> None:
        registry.register_node_provider(_GreetingNodeProvider())
```

That's the whole plugin: a **runtime** (what runs), a **provider** (what's in the
catalog), and a **`Plugin`** that registers the provider.

## 3. Add a manifest

The loader validates a manifest **before importing any plugin code**. Create
`ciaren-plugin.json`:

```json
{
  "id": "community.greeting",
  "name": "Greeting Plugin",
  "version": "0.1.0",
  "publisher": "community",
  "description": "Adds one node that writes a greeting column.",
  "ciaren": ">=0.1",
  "entrypoint": "ciaren_greeting.plugin:GreetingPlugin",
  "permissions": [],
  "capabilities": ["node.greeting"],
  "ui": { "nodes": ["greeting.add"] },
  "trust": "community"
}
```

See the [Plugin Manifest](/specs/plugin-manifest) reference for every field.

## 4. Load it (no install needed)

The fastest loop during development: point Ciaren at the folder that *contains*
your plugin and start the server.

```bash
export CIAREN_PLUGINS_DIR=/path/to   # the directory that holds my-greeting-plugin/
ciaren serve
```

Confirm it loaded:

```bash
ciaren plugin list
# community.greeting should appear
```

`GET /api/plugins` now lists `community.greeting`, and **Add Greeting** appears in
the node palette under the **columns** category.

## 5. Try it on the canvas

1. Open the editor, create a flow, and add a **CSV Input** with any small file.
2. Drag in **Add Greeting** and wire the input into it.
3. **Preview** — you'll see the new `greeting` column.
4. **Export → Python** — the node emits the `assign(...)` line from
   `to_python_code`, so the exported script runs without Ciaren.

You just built a plugin node that runs end-to-end. 🎉

## 6. Package it (optional)

To share it, add a `pyproject.toml` declaring the discovery entry point…

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ciaren-greeting-plugin"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[project.entry-points."ciaren.plugins"]
greeting = "ciaren_greeting.plugin:GreetingPlugin"

[tool.hatch.build.targets.wheel]
packages = ["ciaren_greeting"]
```

…then build a portable, signable `.ciarenplugin` package:

```bash
ciaren plugin keygen                                   # one-time: a signing key
ciaren plugin pack ./my-greeting-plugin ./greeting.ciarenplugin
ciaren plugin sign ./greeting.ciarenplugin
ciaren plugin install ./greeting.ciarenplugin --trusted
```

See [Packaging & Distribution](/plugins/packaging-and-distribution) for the full
publisher workflow and [Plugin Security & Permissions](/security/plugin-security)
for the trust model.

## What next?

- **[Writing a Plugin](/plugins/writing-a-plugin)** — the full contract, events, and rules
- **[Plugin API Reference](/plugins/api-reference)** — every provider, spec, and method
- **[Plugins Overview](/plugins/overview)** — all the extension points

::: tip Built something?
Share it in [Discussions](https://github.com/ciaren-labs/Ciaren/discussions)
— community plugins help everyone.
:::
