# Writing a FlowFrame plugin

> Status: **draft** (Phase 1). A plugin can currently contribute to the catalog
> (nodes/connectors/engines/exporters/validators) and declare capabilities.
> Wiring a plugin-supplied node into the execution engine is a later phase.

A plugin is a small Python package that implements the `Plugin` contract and
registers one or more providers. It depends **only** on the FlowFrame plugin API
(`app.plugin_api`, which will publish separately as `flowframe-plugin-api`) — never
on FlowFrame's private internals.

See a complete, runnable example in
[`examples/plugins/hello-node-plugin/`](../../examples/plugins/hello-node-plugin/).

## 1. Implement `Plugin`

```python
from app.plugin_api import (
    NodeProvider, NodeSpec, Plugin, PluginMetadata, PortSpec, ServiceRegistry,
)

class _MyNodes(NodeProvider):
    def nodes(self) -> list[NodeSpec]:
        return [
            NodeSpec(
                id="acme.greeting",
                label="Add Greeting",
                category="columns",
                description="Adds a greeting column.",
                provider="acme.hello",
                inputs=(PortSpec(id="in"),),
                outputs=(PortSpec(id="out"),),
                default_config={"name": "world"},
                capabilities=("node.greeting",),
            )
        ]

class AcmePlugin(Plugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(id="acme.hello", name="Acme Hello", version="0.1.0")

    def register(self, registry: ServiceRegistry) -> None:
        registry.register_node_provider(_MyNodes())
```

Other provider interfaces you can register: `ConnectorProvider`,
`StorageProvider`, `ExecutionProvider`, `ExporterProvider`, `ValidatorProvider`,
`AIProvider`, `AuthProvider`, `LicenseProvider`.

## 2. Add a manifest

`flowframe-plugin.json` at the plugin directory root — see
[plugin-manifest.md](../specs/plugin-manifest.md). The loader validates it and
checks `flowframe` compatibility before importing your code.

## 3. Make it discoverable

**Installed package** — declare an entry point in `pyproject.toml`:

```toml
[project.entry-points."flowframe.plugins"]
acme = "acme_hello.plugin:AcmePlugin"
```

**Local directory (no install)** — drop the plugin directory under a path on
`FLOWFRAME_PLUGINS_DIR` (or `~/.flowframe/plugins`), with its `flowframe-plugin.json`
declaring an `entrypoint`.

## 4. Verify

```bash
flowframe serve
curl localhost:8055/api/plugins
curl localhost:8055/api/plugins/diagnostics   # shows isolated load errors
curl localhost:8055/api/catalog/nodes          # your node appears here
```

## Rules

- Depend only on `app.plugin_api`; never import FlowFrame internals.
- Ids must be unique. A plugin cannot shadow a core node id — the registry rejects
  the collision and rolls the whole plugin back.
- A failing or incompatible plugin is isolated: it shows up under
  `/api/plugins/diagnostics`, it does not crash the app.
