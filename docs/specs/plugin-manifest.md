# The plugin manifest

> Status: **draft**. Implemented as `PluginManifest` in
> `backend/app/plugin_api/manifest.py`.

Every Ciaren plugin declares a manifest. The loader validates it — and checks
Ciaren version compatibility — **before importing any plugin code**, so a
malformed or incompatible plugin is rejected without ever running.

For local-directory discovery the manifest is a `ciaren-plugin.json` file at
the root of the plugin directory. For installed packages the same information is
conveyed by the `ciaren.plugins` entry point plus the package's own metadata.

## Example

```json
{
  "id": "ciaren.databricks",
  "name": "Databricks Connector",
  "version": "1.0.0",
  "publisher": "ciaren",
  "description": "Read/write Delta tables and export Databricks jobs.",
  "license": "commercial",
  "ciaren": ">=1.0,<2.0",
  "api_version": "1.1",
  "entrypoint": "ciaren_databricks.plugin:DatabricksPlugin",
  "permissions": ["network", "credentials"],
  "capabilities": ["connector.databricks", "exporter.databricks_job"],
  "ui": {
    "nodes": ["databricks.read_table", "databricks.write_table"],
    "nodeCategories": {
      "databricks.read_table": "input",
      "databricks.write_table": "output"
    }
  },
  "dependencies": [],
  "license_required": true,
  "trust": "verified"
}
```

## Fields

| Field | Required | Default | Notes |
|---|---|---|---|
| `id` | yes | — | Unique plugin id, e.g. `ciaren.databricks`. |
| `name` | yes | — | Display name. |
| `version` | no | `0.0.0` | PEP 440 version. |
| `publisher` | no | `community` | — |
| `description` | no | `""` | — |
| `license` | no | `community` | `community` or `commercial`. |
| `ciaren` | no | `>=0.1` | PEP 440 specifier set for compatible Ciaren **app** versions. |
| `api_version` | no | `1.0` | The **plugin-contract** version the plugin targets (`MAJOR.MINOR`). Distinct from `version` and `ciaren`. See [Contract versioning](#contract-versioning). |
| `entrypoint` | no | — | `module.path:Attribute` resolving to a `Plugin`. |
| `permissions` | no | `[]` | See below. |
| `capabilities` | no | `[]` | Capability strings the plugin provides. |
| `ui.nodes` | no | `[]` | Node ids the plugin contributes (advisory; the catalog is authoritative). |
| `ui.nodeCategories` | no | `{}` | Palette subgroup for each node id. Valid values are `input`, `clean`, `columns`, `reshape`, `analytics`, `quality`, `ml`, `output`, and `plugins`; missing/invalid values default to `plugins`. |
| `dependencies` | no | `[]` | Other plugin ids it depends on. |
| `license_required` | no | `false` | Whether a license check must pass to enable it. |
| `trust` | no | `community` | `trusted` / `verified` / `community`. Self-declared and **never displayed as-is**: the trust badge shown in the app is derived by verifying the package signature against the user's trusted keys. |

## Permissions

Declared permissions are a **trust and UX boundary**, not a hard sandbox — Python
plugins are not isolated by default. The UI surfaces them before enabling a
plugin. Values: `filesystem_read`, `filesystem_write`, `network`, `credentials`,
`subprocess`, `shell`, `docker`, `local_model_load`, `joblib_load`,
`database_access`, `cloud_access`, `llm_access`, `telemetry`.

## Compatibility

A manifest carries **three independent version axes** — don't conflate them:

| Axis | Field | What it means | When it changes |
|---|---|---|---|
| Plugin release | `version` | The plugin *product's* own SemVer. | Every release, including bugfixes. |
| App compatibility | `ciaren` | Which **Ciaren app** builds it runs on. | When the plugin is tested against new app builds. |
| Contract | `api_version` | Which **plugin-API contract** (`app.plugin_api`) it was built against. | **Only when the contract itself changes.** |

The loader checks the app axis first, then the contract axis, **before importing
any plugin code**; a failure on either lands in `GET /api/plugins/diagnostics`
with the reason. `PluginManifest.is_compatible_with(ciaren_version)` gates the app
axis (pre-releases allowed); `is_api_compatible_with(PLUGIN_API_VERSION)` gates the
contract axis.

### Contract versioning

The backend advertises a single contract version — `app.plugin_api.PLUGIN_API_VERSION`
(currently `"1.1"`), surfaced as `plugin_api_version` in `GET /api/plugins/diagnostics`.
There is **no hand-maintained list of allowed versions**: the set a given backend
accepts is *derived* by a SemVer rule.

A plugin's `api_version` is compatible when:

- **the major matches** — a new major is a breaking contract change; and
- **the plugin's minor is `<=` the backend's** — minors are purely additive, so a
  newer backend still runs an older plugin, but a backend must reject a plugin that
  needs a minor it doesn't provide.

So a backend at `1.3` accepts `{1.0, 1.1, 1.2, 1.3}` and rejects `1.4` and any `2.x`.
Patch components are ignored (`1.1.7` is treated as `1.1`).

**When the contract version bumps** (and nothing else does):

- **Minor** — a backward-compatible *addition* to the public surface of
  `app.plugin_api` (a new provider, spec field, or method with a safe default).
  1.0 → 1.1 was exactly this (added `ModelRef`, `ModelProvider`, `ConnectorRuntime`,
  `config_schema`); every 1.0 plugin keeps working.
- **Major** — a *breaking* change (removing/renaming a public symbol, changing a
  method signature). A backend supports one major at a time by default, so shipping
  a `2.0` backend stops loading `1.x` plugins (they surface as incompatible, not as
  crashes).

Internal refactors and app releases never move the contract version.

**As an author:** `ciaren plugin manifest` stamps `api_version` with the SDK version
you built against, which is the safe default. If your plugin only uses features from
an older minor, declare that lower minor (`--api-version 1.0`) to run on more hosts.
