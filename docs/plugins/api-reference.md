---
title: Plugin API Reference
description: The stable plugin contract — Plugin, the provider interfaces, the spec types, the ServiceRegistry, and the NodeRuntime — that a Ciaren plugin depends on.
search: plugin api reference provider nodeprovider nodespec noderuntime serviceregistry specs permissions contract
---

# Plugin API Reference

This is the reference for `app.plugin_api` — the stable contract a plugin depends
on (and which will publish separately as `ciaren-plugin-api`). A plugin imports
**only** from this package, never from Ciaren's app, engine, or FastAPI
internals.

New to plugins? Start with the [Overview](/plugins/overview) and the
[10-minute tutorial](/plugins/first-plugin); this page is the detailed contract.

```python
from app.plugin_api import (
    Plugin, PluginMetadata, ServiceRegistry,
    NodeProvider, NodeSpec, NodeRuntime, PortSpec, Permission,
    ConnectorProvider, ConnectorSpec, StorageProvider, StorageSpec,
    ExecutionProvider, ExecutionSpec, ExporterProvider, ExporterSpec,
    ValidatorProvider, ValidatorSpec, AIProvider, AICapabilitySpec,
    AuthProvider, AuthMethodSpec, LicenseProvider, LicenseStatus,
)
```

## `Plugin`

The entry point a plugin package exposes. The loader instantiates it and calls
`register()`.

| Method | Signature | Purpose |
| --- | --- | --- |
| `metadata` | `() -> PluginMetadata` | Identity and headline contributions. |
| `register` | `(registry: ServiceRegistry) -> None` | Register one or more providers on the supplied registry. |

```python
class GreetingPlugin(Plugin):
    def metadata(self) -> PluginMetadata: ...
    def register(self, registry: ServiceRegistry) -> None:
        registry.register_node_provider(_GreetingNodeProvider())
```

## `ServiceRegistry`

Passed to `Plugin.register()`. Register each provider you implement:

| Method | Registers |
| --- | --- |
| `register_node_provider(provider)` | a `NodeProvider` |
| `register_connector_provider(provider)` | a `ConnectorProvider` |
| `register_storage_provider(provider)` | a `StorageProvider` |
| `register_execution_provider(provider)` | an `ExecutionProvider` |
| `register_exporter_provider(provider)` | an `ExporterProvider` |
| `register_validator_provider(provider)` | a `ValidatorProvider` |
| `register_ai_provider(provider)` | an `AIProvider` |
| `register_auth_provider(provider)` | an `AuthProvider` |
| `register_license_provider(provider)` | a `LicenseProvider` |

## Provider interfaces

Each provider is an ABC. Implement the ones you need; a single plugin can
implement several. Providers return serializable **specs** (for the catalog) and,
where relevant, opaque **implementations** (duck-typed by the engine).

| Provider | Abstract method | Returns |
| --- | --- | --- |
| `NodeProvider` | `nodes()` | `list[NodeSpec]` |
| | `node_implementations()` *(optional)* | `dict[str, NodeRuntime]` — node id → runtime |
| `ConnectorProvider` | `connectors()` | `list[ConnectorSpec]` |
| `StorageProvider` | `storage_backends()` | `list[StorageSpec]` |
| `ExecutionProvider` | `execution_backends()` | `list[ExecutionSpec]` |
| `ExporterProvider` | `exporters()` | `list[ExporterSpec]` |
| `ValidatorProvider` | `validators()` | `list[ValidatorSpec]` |
| `AIProvider` | `ai_capabilities()` | `list[AICapabilitySpec]` |
| `AuthProvider` | `auth_methods()` | `list[AuthMethodSpec]` |
| `LicenseProvider` | `validate_license(plugin_id)` | `LicenseStatus` |

A catalog-only `NodeProvider` may omit `node_implementations()` (the node appears
but isn't executable); return a `{node_id: NodeRuntime}` map to make it run.

## `NodeRuntime`

The runnable side of a plugin node. The contract is **pandas-based and
engine-agnostic**: you receive and return pandas DataFrames keyed by handle, and
Ciaren converts to/from the active engine (polars/pandas) around the call.

| Method | Signature | Notes |
| --- | --- | --- |
| `validate_config` | `(config) -> None` | Raise `ValueError` on invalid config. Default: accept anything. |
| `execute` | `(inputs, config) -> dict[str, Any]` | **Required.** `inputs` maps input-handle → DataFrame; return output-handle → DataFrame. |
| `imports` | `(config) -> list[str]` | Extra top-level import lines the exported script needs. |
| `to_python_code` | `(input_vars, output_vars, config) -> str \| None` | Readable **pandas** code (`df` variables), or `None` if not exportable. |

Handle conventions match the node's `NodeSpec`: a single-input node reads
`inputs["in"]` and returns `{"out": frame}`.

```python
class AddGreetingRuntime(NodeRuntime):
    def execute(self, inputs, config):
        df = inputs["in"].copy()
        df[config.get("column") or "greeting"] = "Hello!"
        return {"out": df}
```

## Spec types

Specs are Pydantic models — JSON-serializable descriptions of *what* a plugin
contributes. They carry no executable behavior.

### `NodeSpec`

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `id` | `str` | — | Node type, unique in the catalog (e.g. `"greeting.add"`). |
| `label` | `str` | — | Display name. |
| `category` | `str` | — | UI grouping (`"input"`, `"clean"`, `"columns"`, `"reshape"`, `"ml"`, …). |
| `description` | `str` | `""` | Shown in the palette/inspector. |
| `provider` | `str` | `"ciaren.core"` | Namespaced provider id. |
| `version` | `str` | `"1.0.0"` | Node version. |
| `inputs` | `tuple[PortSpec, …]` | `()` | Input handles. |
| `outputs` | `tuple[PortSpec, …]` | `()` | Output handles. |
| `default_config` | `dict` | `{}` | Config for a freshly-created node. |
| `capabilities` | `tuple[str, …]` | `()` | Capabilities needed at run time. |
| `permissions` | `tuple[Permission, …]` | `()` | Permissions the node needs. |
| `requires_ml` | `bool` | `False` | Only available when the ML extension is on. |
| `is_model_sink` | `bool` | `False` | Terminal that persists a model (e.g. a train node). |
| `config_schema` | `dict` | `{}` | Reserved for schema-driven forms (unused today). |

### `PortSpec`

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `id` | `str` | — | Handle id (e.g. `"in"`, `"out"`, `"train"`). |
| `type` | `"dataframe" \| "model"` | `"dataframe"` | A `model` output may only feed a `model` input. |
| `required` | `bool` | `True` | Whether an incoming edge is required (inputs). |
| `multi` | `bool` | `False` | Accept multiple incoming edges (e.g. concat). |

### Other specs (shared shape)

`ConnectorSpec`, `StorageSpec`, `ExecutionSpec`, `ExporterSpec`, `ValidatorSpec`,
`AICapabilitySpec`, and `AuthMethodSpec` all carry an `id`, a `label`, a
`provider`, and `capabilities`, plus a few type-specific fields:

- **`ConnectorSpec`** — `kind` (`"sql"` / `"mongo"` / `"storage"` / `"mlflow"`),
  `available`, `driver_module`, `extra` (pip extra for the install hint),
  `permissions`, `metadata` (form flags: host/port/auth/bucket/…).
- **`ExecutionSpec`** — `available` (an engine name the executor understands).
- **`ExporterSpec`** — `format` (e.g. `"python"`) and `file_extension`.
- **`ValidatorSpec`** / **`AICapabilitySpec`** — a `description`.

### `PluginMetadata`

`id`, `name`, `version`, `publisher`, `description`, `capabilities`,
`permissions`.

### `LicenseStatus`

Returned by `LicenseProvider.validate_license()`: `plugin_id`, `valid`,
`license_type`, `expires_at`, `reason`.

## `Permission`

Permissions a plugin may request in its manifest. They are a **trust and UX
boundary** surfaced before a plugin is enabled — not a hard sandbox. See
[Plugin Security & Permissions](/security/plugin-security).

`filesystem_read` · `filesystem_write` · `network` · `credentials` ·
`subprocess` · `shell` · `docker` · `local_model_load` · `joblib_load` ·
`database_access` · `cloud_access` · `llm_access` · `telemetry`

## See also

- [Plugins Overview](/plugins/overview) — the extension-points map
- [Build Your First Plugin](/plugins/first-plugin) — step-by-step tutorial
- [Writing a Plugin](/plugins/writing-a-plugin) — events, rules, and details
- [Plugin Manifest](/specs/plugin-manifest) · [.flow Format](/specs/flow-format)
