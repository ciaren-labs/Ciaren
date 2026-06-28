---
title: Catalog & Plugins API
description: Backend-fed node catalog and installed-plugin introspection
search: api catalog nodes connectors categories plugins diagnostics extension
---

# Catalog & Plugins API

The **catalog** is the backend's description of every node, connector, and
category the editor can render — sourced from the open-source core and any
installed plugins. The visual editor's palette is built from it, so a plugin that
contributes a node makes it appear without a frontend rebuild.

## Catalog

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/catalog/nodes` | Node specs (handles, default config, category, capabilities). Optional `?category=`. |
| `GET` | `/api/catalog/connectors` | Connector specs with driver availability and connection-form metadata. |
| `GET` | `/api/catalog/exporters` | Code/artifact exporters (python, eager-polars, lazy-polars) with capabilities. |
| `GET` | `/api/catalog/categories` | Palette categories in display order. |

ML nodes are included only when the ML extension is ready (matching
`GET /api/transformations`).

A node spec looks like:

```json
{
  "id": "filterRows",
  "label": "Filter Rows",
  "category": "clean",
  "description": "Keep rows matching a condition.",
  "provider": "flowframe.core",
  "version": "1.0.0",
  "inputs": [{ "id": "in", "type": "dataframe", "required": true, "multi": false }],
  "outputs": [{ "id": "out", "type": "dataframe", "required": true, "multi": false }],
  "default_config": { "column": "", "operator": "==", "value": "" },
  "capabilities": [],
  "permissions": [],
  "requires_ml": false,
  "is_model_sink": false,
  "config_schema": {}
}
```

## Plugins

Introspection **and** management of installed plugins.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/plugins` | Every discovered plugin with its `status` (the core is not listed). |
| `GET` | `/api/plugins/diagnostics` | `loaded`, `gated`, and isolated load/validation `errors`. |
| `POST` | `/api/plugins/{id}/enable` | Re-enable a disabled plugin. |
| `POST` | `/api/plugins/{id}/disable` | Disable a plugin (its code stops loading). |
| `POST` | `/api/plugins/{id}/grant` | Grant permissions (empty body grants all requested → one-click approve). |
| `POST` | `/api/plugins/{id}/revoke` | Revoke permissions (may move the plugin back to pending). |

Each plugin reports a `status`:

- `loaded` — running; its nodes/connectors are in the catalog.
- `disabled` — the user turned it off; not loaded.
- `needs_permissions` — it declares permissions that haven't been granted, so its
  code is **not imported** until you approve them (`missing_permissions` lists
  which). This is the trust/UX boundary — see
  [plugin security](/security/plugin-security).

Plugins are discovered via the `flowframe.plugins` entry-point group and local
plugin directories (`FLOWFRAME_PLUGINS_DIR`, `~/.flowframe/plugins`). A malformed
or incompatible plugin is reported under `diagnostics` rather than crashing the
app. Permission gating applies to **drop-in** (manifest) plugins; entry-point
packages are installed deliberately and load without the gate.

Changes apply live: granting a pending plugin rebuilds the registry so its nodes
appear in the catalog without a restart.

## See also

- [Writing a plugin](/plugins/writing-a-plugin) — build and register one
- [Plugin manifest](/specs/plugin-manifest) — the manifest contract
- [`.flow` format](/specs/flow-format) — the versioned flow document
- [Transformations API](./transformations.md)
