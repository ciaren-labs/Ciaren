---
title: REST API Reference
description: FlowFrame REST API endpoints
search: api rest endpoints datasets flows runs export
---

# REST API Reference

FlowFrame is a FastAPI service. Today the REST API is the primary way to drive
it (the visual editor is in progress). All endpoints are served under
`http://localhost:8000` by default.

:::tip Interactive docs
Run the backend and open `http://localhost:8000/docs` for the live Swagger UI,
or `http://localhost:8000/redoc` for ReDoc. Both are generated from the running
app, so they always match your version.
:::

## Health

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Returns `{"status": "ok"}` |

## Datasets

Upload and inspect source files (CSV, Excel, Parquet).

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/datasets/upload` | Upload a file and register a dataset |
| `GET` | `/api/datasets` | List datasets |
| `GET` | `/api/datasets/{dataset_id}` | Get one dataset |
| `GET` | `/api/datasets/{dataset_id}/schema` | Inferred column schema |
| `GET` | `/api/datasets/{dataset_id}/sample` | Sample rows |

## Flows

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
| `POST` | `/api/flows/{flow_id}/export/python` | Export the flow as readable pandas code |

## Runs

Execute a flow and read run metadata, status, and logs.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/flows/{flow_id}/runs` | Execute a flow and create a run |
| `GET` | `/api/runs/{run_id}` | Get run status, output location, and logs |

## Transformations

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/transformations` | List available transformation types |
| `POST` | `/api/transformations/preview` | Preview a single transformation against sample data |

## Typical workflow

1. `POST /api/datasets/upload` — upload a CSV/Excel/Parquet file.
2. `POST /api/flows` — save a graph that reads the dataset and applies nodes.
3. `POST /api/flows/{id}/preview` — check the result on sample data.
4. `POST /api/flows/{id}/runs` — run the full pipeline.
5. `GET /api/runs/{run_id}` — poll status and read logs.
6. `POST /api/flows/{id}/export/python` — get standalone pandas code.

## See Also

- [Transformations Reference](/transformations/overview) — every node and its config
- [Installation](/guide/installation) — get the backend running
