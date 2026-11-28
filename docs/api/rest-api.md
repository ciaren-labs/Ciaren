---
title: REST API Reference
description: "Overview of the Ciaren REST API: the FastAPI endpoints behind the visual editor, base URL, Swagger UI and ReDoc, conventions, and a typical workflow."
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
- [Settings](./settings.md) — read and override the runtime-editable server settings
- **ML endpoints** — model metrics, registration, aliases, experiments, and runs under `/api/ml/*`, `/api/runs/{id}/ml/*`, and `/api/flows/{id}/ml/*`
- **Marketplace** — plugin Explore catalog and install endpoint under `/api/marketplace`
- **Flow assistant** — status, provider list, API keys, proposals and saved-change history under `/api/assistant/*` (see [below](#flow-assistant-endpoints))

## Webhook trigger

`POST /api/flows/{flow_id}/trigger` starts a run authenticated by a pre-shared secret
(`CIAREN_WEBHOOK_SECRET`). Designed for CI/CD pipelines and external
orchestrators. See the [Webhook guide](/guide/webhook) for full details.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/settings/webhook` | Returns `{"configured": true/false}` (never the secret) |
| `POST` | `/api/flows/{flow_id}/trigger` | Trigger a run; requires `X-Ciaren-Secret` header |

## Flow assistant endpoints

The editor's [Flow assistant](/guide/flow-assistant) panel is built on these
endpoints and are shaped for it, so treat the request and response bodies as
editor-internal. Like the rest of `/api` they honour `CIAREN_API_TOKEN` and the
browser-origin guard.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/assistant/status` | Active provider, key source and model, and whether a key is `configured`, `missing` or `unavailable` (never the key) |
| `GET` | `/api/assistant/providers` | Providers with their listed models and reasoning efforts |
| `GET` | `/api/assistant/keychain` | Whether this host has a usable OS keychain for saved keys |
| `GET` / `POST` | `/api/assistant/keys` | List saved keys (name, provider, model, effort, state; never the key) or add one |
| `PATCH` / `DELETE` | `/api/assistant/keys/{key_id}` | Edit, enable or disable, replace or remove a saved key |
| `POST` | `/api/assistant/keys/{key_id}/activate` | Use this key for the assistant |
| `POST` | `/api/assistant/flows/{flow_id}/turn` | Ask the assistant to build, answer from the guides or diagnose; returns a proposal, a question or an explanation. Needs the saved flow revision; `409` when that revision is stale, the flow is disabled or unsaved |
| `DELETE` | `/api/assistant/flows/{flow_id}/turns/{request_id}` | Cancel a running turn |
| `POST` | `/api/assistant/flows/{flow_id}/apply` | Confirm a proposal by its token and save it. Nothing changes the flow until this call |
| `GET` | `/api/assistant/flows/{flow_id}/activity` | Confirmed assistant changes for the flow, most recent first (`?cursor=`) |
| `POST` | `/api/assistant/flows/{flow_id}/activity/{event_id}/preview` | Preview the reversal of a saved change |
| `POST` | `/api/assistant/flows/{flow_id}/activity/{event_id}/revert` | Confirm a previewed reversal |

Saving keys needs `ciaren[keyring]` and an unlocked OS keychain. For a server
without one, configure the provider through environment variables or a secret
file instead. See [Flow assistant](/guide/flow-assistant#deployment-and-credentials).

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
  Browser clients may use either header; CORS preflight allows `X-Ciaren-Token`.
  The bundled web UI keeps the token **in memory and `sessionStorage` only** (never
  `localStorage`): it is cleared when the browser session ends and is not inherited
  by the next user of a shared machine. You can seed it once from a bookmarked
  `…/?api_token=<token>` URL, which the UI strips from the address bar. Sending the
  token as a *header* (rather than a cookie) is deliberate — it is what defeats
  cross-site (CSRF) requests, since a browser can't attach a custom header
  cross-site without a preflight the token gate would reject.
- **Browser origin guard:** without an API token, state-changing (`POST`/`PUT`/
  `PATCH`/`DELETE`) `/api/*` requests that carry a browser `Origin` header are
  refused (`403`) unless the origin is in `CIAREN_CORS_ORIGINS` or its hostname
  is local (`localhost`, `127.0.0.1`, `::1`) or listed in `CIAREN_TRUSTED_HOSTS`.
  This blocks CSRF/DNS-rebinding against a local, unauthenticated instance;
  clients that send no `Origin` (curl, scripts, server-to-server) are unaffected.
  See [Local-first trust model](/security/local-first-trust-model).

## Typical workflow

1. `POST /api/datasets/upload` — upload a CSV/TSV/Excel/Parquet/JSON/text file.
2. `POST /api/flows` — save a graph that reads the dataset and applies nodes.
3. `POST /api/flows/{id}/preview` — check the result on sample data.
4. `POST /api/flows/{id}/runs` — run the full pipeline.
5. `GET /api/runs/{run_id}` — poll status and read logs.
6. `GET /api/runs/{run_id}/logs/stream` — stream logs as SSE (optional).
7. `POST /api/flows/{id}/export/python` — get standalone code (pandas and polars).

In the editor you can also build the graph of step 2 by describing it to the
[Flow assistant](/guide/flow-assistant), then reviewing the proposal and choosing
**Apply and save**.

## See Also

- [Transformations Reference](/transformations/overview) — every node and its config
- [Webhook Trigger](/guide/webhook) — trigger runs from CI/CD or Airflow
- [Python SDK](/guide/sdk) — typed Python client for the API
- [Installation](/guide/installation) — get the backend running
