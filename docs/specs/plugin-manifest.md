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
| `ciaren` | no | `>=0.1` | PEP 440 specifier set for compatible Ciaren versions. |
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

`PluginManifest.is_compatible_with(ciaren_version)` returns whether the running
build satisfies the `ciaren` specifier (pre-releases allowed). The loader skips
incompatible plugins and records the reason in `GET /api/plugins/diagnostics`.
