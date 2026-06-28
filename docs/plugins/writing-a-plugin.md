# Writing a FlowFrame plugin

A plugin can contribute to the catalog (nodes/connectors/engines/exporters/
validators), declare capabilities and permissions, ship **executable** nodes that
run end-to-end (via `NodeRuntime`), and subscribe to lifecycle/execution
**events**.

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

### Make the node executable (`NodeRuntime`)

A `NodeSpec` only *describes* a node. To make it run, ship a `NodeRuntime` and
return it from the provider's `node_implementations()`, keyed by node id. The
runtime works on **pandas** frames; FlowFrame bridges to the active engine
(pandas/polars) automatically, so a single runtime runs on both.

```python
from app.plugin_api import NodeRuntime

class GreetingRuntime(NodeRuntime):
    def execute(self, inputs, config):
        df = inputs["in"].copy()
        df[config["column"]] = f"Hello, {config.get('name', 'world')}!"
        return {"out": df}

    # Optional: makes "Export Python" work for this node.
    def to_python_code(self, input_vars, output_vars, config):
        col, name = config["column"], config.get("name", "world")
        return f"{output_vars['out']} = {input_vars['in']}.assign(**{{{col!r}: {f'Hello, {name}!'!r}}})"

class _MyNodes(NodeProvider):
    def nodes(self): ...
    def node_implementations(self):
        return {"acme.greeting": GreetingRuntime()}
```

Once registered the node executes in runs and previews, passes graph validation,
and (if `to_python_code` is implemented) appears in both the pandas and polars
exports — exactly like a built-in.

#### Node categories

`NodeSpec.category` controls where the node lands in the editor palette. Use a
built-in category (`input`, `clean`, `columns`, `reshape`, `analytics`,
`quality`, `ml`, `output`) to slot it into that section. Any other value is fine
too: the palette renders an extra section for the custom category (title-cased,
with a neutral plugin theme) after the built-in ones, and the node still renders
and runs normally on the canvas.

### React to events

A plugin can subscribe to lifecycle and execution hooks via `registry.events`
inside `register()`. Subscribers are error-isolated (a raising hook is logged and
skipped) and run synchronously in registration order.

```python
from app.plugin_api import Hook

class AuditPlugin(Plugin):
    def metadata(self): ...
    def register(self, registry):
        registry.events.subscribe(Hook.after_graph_execute, self._log_run)

    def _log_run(self, *, flow_id, run_id, status, **_):
        print(f"[audit] flow {flow_id} run {run_id}: {status}")
```

**Emitted today** (`app.plugin_api.Hook`): `plugin_enabled`, `plugin_disabled`,
`before_graph_execute`, `after_graph_execute`, `before_node_execute`,
`after_node_execute`, and `export_requested`. Graph-level and export hooks fire
for every run/export; **node-level** hooks fire in the in-process (`thread`)
execution path — in `process` mode a worker can't reach parent subscribers, so
prefer graph-level hooks for cross-mode behaviour.

**Reserved** (defined for a stable namespace but **not emitted yet** — don't rely
on them firing): `plugin_installed` (install runs in the CLI, a separate process),
`project_created` / `project_opened` / `project_saved`, `graph_loaded`, and
`graph_validated`.

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
