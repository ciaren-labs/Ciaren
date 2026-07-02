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

The contract itself is versioned independently of the app:
`app.plugin_api.PLUGIN_API_VERSION` (currently `"0.1.0-alpha.1"`). A plugin
declares which contract it targets via its manifest's `api_version`; the loader
rejects a plugin whose contract is incompatible with the running backend **before
importing it**. **Pre-1.0 (alpha) the contract makes no backward-compatibility
promise** — a plugin must target the *exact* `major.minor` the backend provides;
from 1.0 on, minors become additive and only a major bump breaks. The backend's
own value is exposed as `plugin_api_version` in `GET /api/plugins/diagnostics`.
See [Contract versioning](/specs/plugin-manifest#contract-versioning) for the full
policy.

::: info The 0.1 contract surface
`ModelRef` and typed model wires, `ModelProvider`/`ModelTypeSpec` (contribute
trainable model types to the ML catalog), `NodeContext`/`ModelStore`
(`NodeRuntime.execute_with_context`), executable connectors
(`ConnectorRuntime` + `ConnectorProvider.connector_implementations`), and
schema-driven forms (`ConfigFieldSpec` / `config_schema`).
:::

```python
from app.plugin_api import (
    Plugin, PluginMetadata, ServiceRegistry,
    NodeProvider, NodeSpec, NodeRuntime, NodeContext, ModelStore, PortSpec, Permission,
    ConnectorProvider, ConnectorSpec, ConnectorRuntime, ConnectorTestResult,
    ModelProvider, ModelTypeSpec, ModelRef,
    ConfigFieldSpec, validate_config_schema,
    StorageProvider, StorageSpec,
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
| `register_model_provider(provider)` | a `ModelProvider` |
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
| | `connector_implementations()` *(optional)* | `dict[str, ConnectorRuntime]` — connector id → runtime |
| `ModelProvider` | `model_types()` | `list[ModelTypeSpec]` |
| | `model_builders()` *(optional)* | `dict[str, callable]` — model type id → estimator builder |
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
| `execute` | `(inputs, config) -> dict[str, Any]` | `inputs` maps input-handle → DataFrame; return output-handle → DataFrame. |
| `execute_with_context` | `(inputs, config, context: NodeContext) -> dict[str, Any]` | Ciaren's actual entry point; the default delegates to `execute`. Override **this one instead** when the node needs host services (ModelStore, preview flag). |
| `imports` | `(config) -> list[str]` | Extra top-level import lines the exported script needs. |
| `to_python_code` | `(input_vars, output_vars, config) -> str \| None` | Readable **pandas** code (`df` variables), or `None` if not exportable. |

Override `execute` **or** `execute_with_context` — never neither. Handle
conventions match the node's `NodeSpec`: a single-input node reads
`inputs["in"]` and returns `{"out": frame}`.

```python
class AddGreetingRuntime(NodeRuntime):
    def execute(self, inputs, config):
        df = inputs["in"].copy()
        df[config.get("column") or "greeting"] = "Hello!"
        return {"out": df}
```

## `NodeContext`

Host services passed to `execute_with_context`:

| Field | Type | Notes |
| --- | --- | --- |
| `plugin_id` | `str` | The plugin the node belongs to. |
| `permissions` | `frozenset[Permission]` | Permissions the user actually **granted** (not what the manifest requested). |
| `models` | `ModelStore \| None` | MLflow-backed model persistence; `None` when the server has no ML support installed. |
| `in_preview` | `bool` | True during editor previews on sampled data — skip training/persisting and return a cheap placeholder, like the core train nodes do. |

## `ModelStore`

The sanctioned persistence path for plugin-trained models — estimators become
MLflow artifacts; only a typed `ModelRef` travels through the graph.

| Method | Notes |
| --- | --- |
| `log_sklearn_model(model, *, model_type, task_type, target_column=None, feature_columns=(), params=None, metrics=None, input_example=None, experiment=None, preprocessing=None, seed=None, training_config=None) -> ModelRef` | Persist a fitted sklearn-compatible model to MLflow and return its reference. Raises when it cannot persist (never silently emits a dangling reference). The reference's `model_config_json` is part of the model-wire **contract**: it records the same shape the core train nodes emit (`model_type`, `target_column`, `feature_columns`, `hyperparameters` from `params`, `preprocessing`, `seed`) so core consumers like Cross-Validate can rebuild the estimator; `training_config` entries overlay the generated config. |
| `load_model(ref_or_uri) -> Any` | Load after the host's security checks. Deserializing executes pickled code, so it is **permission-gated**: MLflow URIs need `local_model_load` (or `joblib_load`); a local `.joblib` path needs `joblib_load` *and* must live inside the server's artifact root. `.pkl`/`.pickle` are always refused. |

## `ModelRef`

The typed payload of a **model wire** — a frozen dataclass with a one-row-frame
round-trip. The core train nodes emit exactly this frame, and the core
consumers (`mlPredict`, `featureImportance`, `mlCrossValidate`) read it, so
plugin and core models interoperate in both directions.

| Member | Notes |
| --- | --- |
| `task_type`, `model_type` | e.g. `"classification"`, `"mlp_classifier"`. |
| `mlflow_run_id`, `model_uri` | Where the artifact lives (`runs:/…` / `models:/…`); `None` for definition-only/preview references. |
| `target_column`, `feature_columns`, `training_config` | What the model was trained on. |
| `to_frame()` / `from_frame(frame)` | Convert to/from the one-row pandas frame carried on a `model` handle (`MODEL_REF_COLUMNS` is the public column layout). |

## `ConnectorRuntime`

The runnable side of a plugin connector — pandas-based like `NodeRuntime`.
`config` is the saved connection flattened to a plain mapping (`host`, `port`,
`database`, `username`, `password` *resolved from the env var for the one call*,
`options`); `options` on read/write carries the flow node's config plus `limit`
for bounded preview reads. Only `read` is required; unimplemented optional
methods surface as a clear "not supported by this connector" error.

| Method | Notes |
| --- | --- |
| `test(config) -> ConnectorTestResult` | Cheap reachability/auth check for the Connections page. |
| `list_tables(config) -> list[dict]` | `{"name", "schema", "row_count"}` entries (query-style connectors). |
| `list_objects(config, prefix="") -> list[str]` | Object/file names (storage-style connectors). |
| `read(config, options) -> DataFrame` | **Required.** Backs `sqlInput` (sql/api kinds) or `storageInput` (storage kind). |
| `write(frame, config, options) -> None` | Backs `sqlOutput` / `storageOutput`. |

## `ModelTypeSpec`

Describes a trainable model type contributed to the ML catalog; it appears in
the matching core train node's picker and trains through the core pipeline.

| Field | Notes |
| --- | --- |
| `id` | The `model_type` id (unique across the catalog), e.g. `"mlp_classifier"`. |
| `label`, `task`, `supervised`, `provider`, `description` | Catalog metadata; `task` is one of `classification`/`regression`/`clustering`/`dimensionality_reduction`/`timeseries`. |
| `requires`, `install_hint` | Importable modules the builder needs; the hint shown when missing. |
| `default_hyperparameters`, `hyperparameter_schema` | Drive the model picker's hyperparameter form (same field dialect as `config_schema`). The defaults are also **merged under the user's values** before your builder is called, so an untouched form trains with what the catalog advertises. |
| `import_lines` | Top-level imports exported training scripts use for the estimator. When empty, the import is derived from the estimator's class module — declare them whenever the estimator's `repr` needs anything beyond that. |

The matching builder (from `ModelProvider.model_builders()`) is
`(hyperparameters: dict, seed: int | None) -> estimator` and must return an
sklearn-compatible estimator. Hyperparameters arrive sanitized to JSON-native
values; inject the seed unless the user set one explicitly.

## `ConfigFieldSpec` and `config_schema`

A deliberately small, UI-oriented form dialect (not full JSON Schema), shared by
plugin **node** config forms (`NodeSpec.config_schema`), **connector** connection
forms (`ConnectorSpec.config_schema`), and **model** hyperparameter forms
(`ModelTypeSpec.hyperparameter_schema`). Shape: `{"fields": [ … ]}` where each
field validates as:

| Field | Notes |
| --- | --- |
| `key` | Config key the field reads/writes. |
| `label`, `help`, `placeholder` | Presentation (label defaults to the key). |
| `type` | `string` · `number` · `integer` · `boolean` · `select` · `string_list` · `column` · `column_list` (column kinds resolve against the node's incoming wire; node forms only). |
| `required`, `default` | Behavior for fresh configs and validation. |
| `options` | Choices (select only). |
| `min` / `max` | Bounds (number/integer). |
| `secret` | Render masked — for env-var *names*; Ciaren never stores secret values. |

A malformed schema fails **at registration** (`validate_config_schema`), never at
render time.

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
| `requires_ml` | `bool` | `False` | Only available when built-in ML is enabled. |
| `is_model_sink` | `bool` | `False` | Terminal that persists a model (e.g. a train node). |
| `is_flow_terminal` | `bool` | `False` | Node can complete a valid flow without a downstream output node. |
| `config_schema` | `dict` | `{}` | Schema-driven sidebar form — see [`ConfigFieldSpec`](#configfieldspec-and-config-schema). Without one, the editor infers editable fields from `default_config`. |

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

- **`ConnectorSpec`** — `kind` (`"sql"` / `"mongo"` / `"storage"` / `"mlflow"`,
  or your own, e.g. `"api"` — sql-ish kinds back the SQL nodes, `storage` backs
  the storage nodes), `available`, `driver_module`, `extra` (pip extra for the
  install hint), `permissions`, `metadata` (form flags: host/port/auth/bucket/…),
  and `config_schema` (extra connector-specific form fields, stored in the
  connection's `options`).
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
