---
title: REST API Reference
description: FlowFrame REST API endpoints
search: api rest endpoints datasets flows runs export
---

# REST API Reference

FlowFrame is a FastAPI service. The visual editor is built entirely on this REST
API, and you can drive every feature with it directly. All endpoints are served
under `http://localhost:8000` by default.

:::tip Interactive docs
Run the backend and open `http://localhost:8000/docs` for the live Swagger UI,
or `http://localhost:8000/redoc` for ReDoc. Both are generated from the running
app, so they always match your version.
:::

## Health

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Returns `{"status": "ok"}` |

## Projects

Lightweight workspaces that group related datasets and flows. A `Default`
project is created automatically; every dataset and flow belongs to one.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/projects` | List projects (with dataset/flow counts) |
| `POST` | `/api/projects` | Create a project |
| `GET` | `/api/projects/{project_id}` | Get one project |
| `PUT` | `/api/projects/{project_id}` | Update a project |
| `DELETE` | `/api/projects/{project_id}` | Delete a project (its items move to `Default`) |

## Datasets

Upload and inspect source files (CSV, Excel, Parquet). Datasets are **versioned**:
re-uploading a file under the same name appends a new immutable version, so flows
pinned to an earlier version stay reproducible.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/datasets/upload` | Upload a file (optionally `?project_id=`); creates a dataset or a new version |
| `GET` | `/api/datasets` | List datasets (optionally `?project_id=`) |
| `GET` | `/api/datasets/{dataset_id}` | Get one dataset |
| `GET` | `/api/datasets/{dataset_id}/versions` | List all versions, newest first |
| `GET` | `/api/datasets/{dataset_id}/flows` | Flows that use this dataset (lineage) |
| `GET` | `/api/datasets/{dataset_id}/schema` | Inferred column schema (optionally `?version=`) |
| `GET` | `/api/datasets/{dataset_id}/sample` | Sample rows (optionally `?version=`) |

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
| `POST` | `/api/flows/{flow_id}/export/python` | Export the flow as code (returns both `code` = pandas and `polars`) |

## Runs

Execute a flow and read run metadata, status, logs, and per-node results.
The run request accepts an optional `engine` (`polars` default, or `pandas`),
which is recorded on the run for reproducibility. Each run also stores a
per-node result (status, row/column counts, a small sample, and `duration_ms`)
for the read-only run view.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/flows/{flow_id}/runs` | Execute a flow (optional body `{"engine": "polars"}`) and create a run |
| `GET` | `/api/runs` | List runs, filterable by `flow_id`, `project_id`, `dataset_id`, `status`, and date range |
| `GET` | `/api/runs/{run_id}` | Get run status, output location, logs, and per-node results |

## Transformations

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/transformations` | List available transformation types |
| `POST` | `/api/transformations/preview` | Preview a single transformation against sample data |

## Schedules

Run a flow automatically on a cron schedule. A schedule carries a `cron`
expression, a `timezone`, an optional `engine`, and reliability settings
(`max_retries`, `retry_delay_seconds`, `catch_up`). See
[Scheduling](/guide/scheduling) for the behavior.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/flows/{flow_id}/schedules` | List a flow's schedules |
| `POST` | `/api/flows/{flow_id}/schedules` | Create a schedule for a flow |
| `GET` | `/api/schedules` | List all schedules (optionally `?flow_id=`) |
| `GET` | `/api/schedules/{schedule_id}` | Get one schedule |
| `PATCH` | `/api/schedules/{schedule_id}` | Update a schedule (cron, engine, enabled, …) |
| `DELETE` | `/api/schedules/{schedule_id}` | Delete a schedule |
| `POST` | `/api/schedules/{schedule_id}/run-now` | Trigger a one-off run immediately |
| `GET` | `/api/schedules/{schedule_id}/runs` | List runs created by this schedule |

## Typical workflow

1. `POST /api/datasets/upload` — upload a CSV/Excel/Parquet file.
2. `POST /api/flows` — save a graph that reads the dataset and applies nodes.
3. `POST /api/flows/{id}/preview` — check the result on sample data.
4. `POST /api/flows/{id}/runs` — run the full pipeline.
5. `GET /api/runs/{run_id}` — poll status and read logs.
6. `POST /api/flows/{id}/export/python` — get standalone code (pandas and polars).

## See Also

- [Transformations Reference](/transformations/overview) — every node and its config
- [Installation](/guide/installation) — get the backend running
