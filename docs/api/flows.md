---
title: Flows API
description: Create, read, update, delete, preview, and export flows
search: api flows crud graph nodes edges preview export python pandas polars
---

# Flows API

Create, read, update, and delete saved pipelines. A flow stores a React
Flow-compatible graph (`nodes` and `edges`).

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/flows` | List flows (optionally `?project_id=`) |
| `POST` | `/api/flows` | Create a flow |
| `POST` | `/api/flows/import` | Import a portable `.flow` document; environment bindings are stripped |
| `POST` | `/api/flows/migrate-document` | Validate/migrate a raw `.flow` document to the current schema version without persisting it |
| `GET` | `/api/flows/{flow_id}` | Get one flow |
| `PUT` | `/api/flows/{flow_id}` | Update a flow |
| `DELETE` | `/api/flows/{flow_id}` | Delete a flow; also deletes its run history and schedules |
| `POST` | `/api/flows/{flow_id}/duplicate` | Duplicate a flow (optional `?name=`); copies the graph into a new flow with no run history |
| `POST` | `/api/flows/{flow_id}/preview` | Preview the flow output without saving a run; body accepts `node_id`, `limit`, `profile`, and parameter overrides |
| `POST` | `/api/flows/{flow_id}/export/python` | Export the flow as code; `?free_intermediates=true` also releases intermediate frames in generated code |

The export response carries `code` (pandas), `polars`, `polars_lazy`, and a
portable `flow_document`. See [Engines → Code export](/guide/engines#code-export-pandas-polars-and-lazy-polars).

Previews run against the saved flow graph, not unsaved canvas edits. The preview
path uses the same graph validation and ML feature gate as a full run, so invalid
graphs return `400` and flows with ML nodes return `501` if ML support isn't
enabled on the server.

## See also

- [Runs API](./runs.md) · [Transformations API](./transformations.md)
- [Transformations Reference](/transformations/overview)
