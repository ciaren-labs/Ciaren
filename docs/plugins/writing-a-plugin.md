---
title: Writing a Plugin
description: "How to write a Ciaren plugin: implement Plugin and NodeRuntime, add a config_schema form, use NodeContext, react to events, and add a manifest."
---

# Writing a Ciaren plugin

**Guide** for plugin authors who have built the
[first plugin](/plugins/first-plugin). **You get:** how the parts of a plugin fit
together and the rules the loader enforces, beyond the tutorial's single node.

A plugin is a small Python package that implements the `Plugin` contract and
registers one or more providers. It depends **only** on the Ciaren plugin API
(`app.plugin_api`, which will publish separately as `ciaren-plugin-api`) — never
on Ciaren's private internals. Besides describing nodes, connectors, and model
types for the catalog, it can make them **executable** (via `NodeRuntime`,
`ConnectorRuntime`, and `ModelProvider` builders) and subscribe to
lifecycle/execution **events**.

Exact signatures and fields are in the [Plugin API Reference](/plugins/api-reference).
A complete, runnable example is
[`examples/plugins/hello-node-plugin/`](https://github.com/ciaren-labs/Ciaren/tree/main/examples/plugins/hello-node-plugin).

## 1. Implement `Plugin`

A plugin module has three parts; step 2 of the
[tutorial](/plugins/first-plugin) shows all three in one file:

- a **`Plugin`** subclass whose `metadata()` returns the plugin's identity and
  whose `register(registry)` registers each provider;
- one or more **providers**, such as a `NodeProvider` whose `nodes()` returns the
  `NodeSpec` descriptions shown in the catalog;
- **runtimes** that make those nodes run (next section).

Other provider interfaces you can register: `ConnectorProvider`
([executable connectors →](/plugins/connector-plugins)), `ModelProvider`
([ML model types →](/plugins/ml-model-plugins)), `StorageProvider`,
`ExecutionProvider`, `ExporterProvider`, `ValidatorProvider`, `AIProvider`,
`AuthProvider`, `LicenseProvider`.

### Make the node executable (`NodeRuntime`)

A `NodeSpec` only *describes* a node. To make it run, ship a `NodeRuntime` and
return it from the provider's `node_implementations()`, keyed by node id. The
runtime works on **pandas** frames; Ciaren bridges to the active engine
(pandas/polars) automatically, so a single runtime runs on both. Implement
`execute(inputs, config)` for the work and, optionally,
`to_python_code(input_vars, output_vars, config)` so **Export Python** works for
the node.

Once registered the node executes in runs and previews, passes graph validation,
and (if `to_python_code` is implemented) appears in both the pandas and polars
exports — exactly like a built-in.

#### Give the node a real sidebar form (`config_schema`)

Declare the node's form on its spec and the editor renders it — labeled inputs,
selects, checkboxes, column pickers — no frontend code:

```python
NodeSpec(
    id="acme.greeting",
    ...,
    config_schema={"fields": [
        {"key": "column", "label": "New column", "type": "string", "required": True},
        {"key": "name", "label": "Greet who", "type": "string", "default": "world"},
        {"key": "shout", "label": "Uppercase", "type": "boolean", "default": False},
    ]},
)
```

The field types and options are listed in the `ConfigFieldSpec` section of the
[Plugin API Reference](/plugins/api-reference).
Without a schema, the editor falls back to fields inferred from
`default_config`, so every plugin node stays configurable.

#### Host services in the runtime (`NodeContext`)

Ciaren actually invokes `execute_with_context(inputs, config, context)`; the
default implementation delegates to `execute`, so simple runtimes never notice.
Override it when the node needs host services: the preview flag (skip training
on sampled preview data), the MLflow-backed **ModelStore** for train-style nodes
(see [ML Model Plugins](/plugins/ml-model-plugins)), the permissions the user
actually granted, or the plugin's license token for
[thin-client plugins](/plugins/api-reference#thin-client-plugins). The fields
are listed under [`NodeContext`](/plugins/api-reference#nodecontext).

#### Node categories

`NodeSpec.category` controls where the node lands in the editor palette. Use a
built-in category (`input`, `clean`, `columns`, `reshape`, `analytics`,
`quality`, `chart`, `ml`, `output`, or `plugins`) to slot it into that section.
Unknown values are normalized to `plugins`, so the node still renders and runs
normally without the frontend needing a new palette section.

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

`ciaren-plugin.json` at the plugin directory root — see
[plugin-manifest.md](../specs/plugin-manifest.md). The loader validates it and
checks compatibility on **two independent axes** before importing your code: the
Ciaren **app** version (`ciaren` specifier) and the **plugin-contract** version
(`api_version` vs the backend's `PLUGIN_API_VERSION`). An incompatible plugin on
either axis is rejected up front and reported in `/api/plugins/diagnostics` — it
never runs. [Contract versioning](../specs/plugin-manifest.md#contract-versioning)
explains when the contract version changes and what that means for your plugin.

You don't have to hand-write it. Because your `Plugin` already declares the id,
version, permissions, nodes, and categories, generate the manifest from the code
so the two can't drift:

```bash
ciaren-plugin manifest ./my-plugin              # writes ciaren-plugin.json
ciaren-plugin manifest ./my-plugin --out -      # or print it to stdout
```

This still ships and validates the manifest before any code runs — it only
removes the duplicated, drift-prone copy.

## 3. Make it discoverable

**Installed package** — declare an entry point in `pyproject.toml`:

```toml
[project.entry-points."ciaren.plugins"]
acme = "acme_hello.plugin:AcmePlugin"
```

**Local directory (no install)** — drop the plugin directory under a path on
`CIAREN_PLUGINS_DIR` (or `~/.ciaren/plugins`), with its `ciaren-plugin.json`
declaring an `entrypoint`.

## 4. Verify

```bash
ciaren serve
curl localhost:8055/api/plugins
curl localhost:8055/api/plugins/diagnostics   # shows isolated load errors
curl localhost:8055/api/catalog/nodes          # your node appears here
```

## Rules

- Depend only on `app.plugin_api`; never import Ciaren internals.
- Ids must be unique. A plugin cannot shadow a core node id — the registry rejects
  the collision and rolls the whole plugin back.
- A failing or incompatible plugin is isolated: it shows up under
  `/api/plugins/diagnostics`, it does not crash the app.
