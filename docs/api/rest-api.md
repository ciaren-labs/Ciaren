---
title: REST API Reference
description: FlowFrame REST API — overview and conventions
search: api rest endpoints overview conventions base url swagger
---

# REST API Reference

FlowFrame is a FastAPI service. The visual editor is built entirely on this REST
API, and you can drive every feature with it directly. All endpoints are served
under `http://localhost:8055` by default.

:::tip Interactive docs
Run the backend and open `http://localhost:8055/docs` for the live Swagger UI,
or `http://localhost:8055/redoc` for ReDoc. Both are generated from the running
app, so they always match your version.
:::

## Resources

Each resource has its own reference page:

- [Projects](./projects.md) — workspaces grouping datasets and flows
- [Datasets](./datasets.md) — upload and inspect versioned source files
- [Flows](./flows.md) — saved pipelines (graph), preview, and code export
- [Runs](./runs.md) — execute flows and read status, logs, per-node results
- [Transformations](./transformations.md) — list node types, preview one node
- [Schedules](./schedules.md) — run flows automatically on a cron schedule
- [Connections](./connections.md) — reusable database connections for SQL nodes

## Conventions

- **Base URL:** `http://localhost:8055` (configurable via `--host`/`--port`).
- **Format:** JSON request and response bodies; `POST /api/datasets/upload` uses
  multipart form data.
- **IDs:** path parameters like `{flow_id}` are the resource's `id`.
- **Health check:** `GET /health` returns `{"status": "ok"}`.

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
