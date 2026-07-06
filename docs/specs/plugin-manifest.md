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
  "api_version": "0.1.0-alpha.1",
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
| `api_version` | no | `0.1.0-alpha.1` | The **plugin-contract** version the plugin targets. Distinct from `version` and `ciaren`. See [Contract versioning](#contract-versioning). |
| `entrypoint` | no | — | `module.path:Attribute` resolving to a `Plugin`. |
| `permissions` | no | `[]` | See below. |
| `capabilities` | no | `[]` | Capability strings the plugin provides. |
| `ui.nodes` | no | `[]` | Node ids the plugin contributes (advisory; the catalog is authoritative). |
| `ui.nodeCategories` | no | `{}` | Palette subgroup for each node id. Valid values are `input`, `clean`, `columns`, `reshape`, `analytics`, `quality`, `chart`, `ml`, `output`, and `plugins`; missing/invalid values default to `plugins`. |
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
(currently `"0.1.0-alpha.1"`), surfaced as `plugin_api_version` in
`GET /api/plugins/diagnostics`. There is **no hand-maintained list of allowed
versions**: the set a given backend accepts is *derived* by a SemVer rule, with the
standard pre-1.0 caveat.

**Right now the contract is pre-1.0 (alpha), so it makes no backward-compatibility
promise.** A plugin's `api_version` is compatible only when its `major.minor` equals
the backend's *exactly*: a `0.1` plugin runs on a `0.1` backend and nothing else.
Any 0.x minor bump is treated as breaking — when the contract moves to `0.2`, every
`0.1` plugin is cleanly rejected and must be rebuilt against `0.2`. (Breaking the
contract freely pre-1.0/during alpha is intentional — there's no
backward-compatibility promise to keep until `1.0`.)

**From `1.0` onward** the rule relaxes to the usual additive-minor form: the major
must match (a new major is breaking) and the plugin's minor be `<=` the backend's,
so a backend at `1.3` would accept `{1.0, 1.1, 1.2, 1.3}` and reject `1.4` and any
`2.x`. Patch and pre-release components are always ignored (`0.1.0-alpha.1` compares
as `0.1`).

**When the contract version bumps** (and nothing else does):

- **Pre-1.0 minor** (e.g. `0.1 → 0.2`) — any change to the public surface of
  `app.plugin_api`, breaking or not; all existing plugins must be rebuilt.
- **1.x minor** — a backward-compatible *addition* (a new provider, spec field, or
  method with a safe default); older plugins keep working.
- **Major** — a *breaking* change (removing/renaming a public symbol, changing a
  method signature). A backend supports one major at a time.

Internal refactors and app releases never move the contract version.

**As an author:** `ciaren-plugin manifest` stamps `api_version` with the SDK version
you built against — during alpha, just rebuild your plugin whenever the contract
bumps. (`--api-version` lets you override it once the contract reaches 1.x and
declaring a lower minor widens host compatibility.)
