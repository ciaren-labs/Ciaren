---
title: REST API Reference
description: Ciaren REST API — overview and conventions
search: api rest endpoints overview conventions base url swagger webhook trigger
---

# REST API Reference

Ciaren is a FastAPI service. The visual editor is built entirely on this REST
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
- [Runs](./runs.md) — execute flows and read status, logs, per-node results, SSE stream
- [Transformations](./transformations.md) — list node types, preview one node
- [Catalog & Plugins](./catalog.md) — backend-fed node catalog and installed-plugin introspection
- [Schedules](./schedules.md) — run flows automatically on a cron schedule
- [Connections](./connections.md) — reusable database connections for SQL nodes
- **ML endpoints** — model metrics, registration, aliases, experiments, and runs under `/api/ml/*`, `/api/runs/{id}/ml/*`, and `/api/flows/{id}/ml/*`
- **Marketplace** — plugin Explore catalog and install endpoint under `/api/marketplace`

## Webhook trigger

`POST /api/flows/{id}/trigger` starts a run authenticated by a pre-shared secret
(`CIAREN_WEBHOOK_SECRET`). Designed for CI/CD pipelines and external
orchestrators. See the [Webhook guide](/guide/webhook) for full details.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/settings/webhook` | Returns `{"configured": true/false}` (never the secret) |
| `POST` | `/api/flows/{id}/trigger` | Trigger a run; requires `X-Ciaren-Secret` header |

## Conventions

- **Base URL:** `http://localhost:8055` (configurable via `--host`/`--port`).
- **Format:** JSON request and response bodies; `POST /api/datasets/upload` uses
  multipart form data.
- **IDs:** path parameters like `{flow_id}` are the resource's `id`.
- **Health check:** `GET /health` (liveness) returns `{"status": "ok"}` — the
  process is up, no dependencies checked.
- **Readiness check:** `GET /ready` verifies the database is reachable. Returns
  `200` `{"status": "ok", "database": "up"}` when ready, or `503`
  `{"status": "unavailable", "database": "down"}` so a load balancer drains the
  instance.
- **Optional API auth:** when `CIAREN_API_TOKEN` is set, `/api/*` requests must
  send `Authorization: Bearer <token>` or `X-Ciaren-Token: <token>`. Static UI,
  `/health`, `/ready`, OpenAPI docs, and the webhook trigger's own secret are exempt.

## Typical workflow

1. `POST /api/datasets/upload` — upload a CSV/Excel/Parquet file.
2. `POST /api/flows` — save a graph that reads the dataset and applies nodes.
3. `POST /api/flows/{id}/preview` — check the result on sample data.
4. `POST /api/flows/{id}/runs` — run the full pipeline.
5. `GET /api/runs/{run_id}` — poll status and read logs.
6. `GET /api/runs/{run_id}/logs/stream` — stream logs as SSE (optional).
7. `POST /api/flows/{id}/export/python` — get standalone code (pandas and polars).

## See Also

- [Transformations Reference](/transformations/overview) — every node and its config
- [Webhook Trigger](/guide/webhook) — trigger runs from CI/CD or Airflow
- [Python SDK](/guide/sdk) — typed Python client for the API
- [Installation](/guide/installation) — get the backend running
