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
| `GET` | `/api/flows` | List flows |
| `POST` | `/api/flows` | Create a flow |
| `GET` | `/api/flows/{flow_id}` | Get one flow |
| `PUT` | `/api/flows/{flow_id}` | Update a flow |
| `DELETE` | `/api/flows/{flow_id}` | Delete a flow |
| `POST` | `/api/flows/{flow_id}/preview` | Preview the flow output without saving a run |
| `POST` | `/api/flows/{flow_id}/export/python` | Export the flow as code (returns both `code` = pandas and `polars`) |

The export response carries both dialects: `code` (pandas) and `polars`. See
[Engines → Code export](/guide/engines#code-export).

## See also

- [Runs API](./runs.md) · [Transformations API](./transformations.md)
- [Transformations Reference](/transformations/overview)
