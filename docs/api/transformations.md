---
title: Transformations API
description: List available node types and preview a single transformation
search: api transformations list preview node types sample
---

# Transformations API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/transformations` | List available transformation types |
| `POST` | `/api/transformations/preview` | Preview a single transformation against sample data |

`GET /api/transformations` returns the registered node types from
[`app/engine/registry.py`](https://github.com/rodrigo-arenas/FlowFrame/blob/main/backend/app/engine/registry.py).
`POST /api/transformations/preview` runs one node's config against supplied sample
rows — this powers the editor's live preview without saving a run.

:::tip Full node metadata
`GET /api/transformations` returns only type names. For the complete node catalog
(labels, categories, handles, default config — including plugin-contributed
nodes), use [`GET /api/catalog/nodes`](./catalog.md).
:::

## See also

- [Catalog & Plugins API](./catalog.md) — full node metadata + plugin introspection
- [Transformations Reference](/transformations/overview) — every node and its config
- [Flows API](./flows.md)
