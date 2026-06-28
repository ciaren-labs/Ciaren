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

Read-only introspection of installed plugins and any isolated load errors.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/plugins` | Plugins that loaded successfully (the core is not listed). |
| `GET` | `/api/plugins/diagnostics` | Loaded plugins **plus** isolated load/validation errors. |

Plugins are discovered via the `flowframe.plugins` entry-point group and local
plugin directories (`FLOWFRAME_PLUGINS_DIR`, `~/.flowframe/plugins`). A malformed
or incompatible plugin is reported under `diagnostics` rather than crashing the
app.

:::tip Developer preview
The plugin system is an architectural foundation. Today a plugin contributes
**catalog** entries (so its nodes appear in the palette) and declares
capabilities; wiring a plugin-supplied node into the execution engine is a later
phase. See [Writing a plugin](/plugins/writing-a-plugin).
:::

## See also

- [Writing a plugin](/plugins/writing-a-plugin) — build and register one
- [Plugin manifest](/specs/plugin-manifest) — the manifest contract
- [`.flow` format](/specs/flow-format) — the versioned flow document
- [Transformations API](./transformations.md)
