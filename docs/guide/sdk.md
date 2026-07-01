---
title: Python SDK
description: Control Ciaren from Python scripts, notebooks, and orchestrators
search: sdk python client ciaren-client trigger run stream logs async httpx
---

# Python SDK

`ciaren-client` is a thin Python package that wraps the Ciaren REST API
with a friendly interface. It ships both a synchronous (`Ciaren`) and an
async (`AsyncCiaren`) client, and depends only on `httpx`.

## Installation

```bash
pip install ciaren-client
```

Or from the repository during development:

```bash
pip install -e path/to/Ciaren/client
```

## Quick start

```python
from ciaren_client import Ciaren

client = Ciaren("http://localhost:8055", webhook_secret="my-secret")

# Trigger a run and wait for it to complete
run = client.trigger("your-flow-id")
print(run["status"])  # "success" or "failed"
```

::: info Webhook secret required for trigger()
`trigger()` calls `POST /api/flows/{id}/trigger` which requires
`CIAREN_WEBHOOK_SECRET` to be set on the server. See the
[Webhook guide](/guide/webhook) for setup instructions. The other methods
(`list_flows`, `get_run`, etc.) work without a secret.
:::

## Sync client — `Ciaren`

```python
from ciaren_client import Ciaren

client = Ciaren(
    base_url="http://localhost:8055",
    webhook_secret="my-secret",   # required only for trigger()
    api_token="my-api-token",     # required only if CIAREN_API_TOKEN is set on the server
    timeout=30.0,                 # httpx request timeout in seconds
)
```

::: info API token for network-exposed servers
Ciaren is unauthenticated by default (local-first). If the server sets
`CIAREN_API_TOKEN` — recommended whenever it's reachable outside loopback,
e.g. the Docker image or behind a reverse proxy — every `/api/*` request
except `trigger()` must carry it, or the server returns `401`. Pass it as
`api_token` and the client sends `Authorization: Bearer <token>` on every
request. See [Advanced setup](/guide/advanced-setup) and
[SECURITY.md](https://github.com/ciaren-labs/Ciaren/blob/main/SECURITY.md)
for the deployment posture.
:::

Use it as a context manager to ensure the underlying `httpx.Client` is closed:

```python
with Ciaren("http://localhost:8055", webhook_secret="my-secret") as client:
    run = client.trigger("flow-id")
```

### Methods

#### `list_flows()`

```python
flows = client.list_flows()
# → [{"id": "...", "name": "Sales Pipeline", ...}, ...]
```

#### `get_flow(flow_id)`

```python
flow = client.get_flow("flow-id")
```

#### `list_runs(*, flow_id=None, project_id=None, dataset_id=None, schedule_id=None, status=None, started_after=None, started_before=None, sort_by="created_at", sort_order="desc", limit=100, offset=0)`

Mirrors the filtering, sorting, and pagination options of `GET /api/runs`.
`started_after`/`started_before` accept either a `datetime` or an ISO 8601
string.

```python
runs = client.list_runs(flow_id="flow-id")

# Filter by schedule and status, sorted oldest-first, paginated
runs = client.list_runs(
    schedule_id="schedule-id",
    status="failed",
    sort_by="started_at",
    sort_order="asc",
    limit=50,
    offset=50,
)
```

#### `get_run(run_id)`

```python
run = client.get_run("run-id")
print(run["status"])  # "pending" | "running" | "success" | "failed"
```

#### `retry_run(run_id)`

Re-runs the same flow with the original run's config, creating a new run
(new id). Returns the new run dict.

```python
new_run = client.retry_run("run-id")
```

#### `trigger(flow_id, *, engine=None, parameters=None)`

Start a run via the webhook endpoint. Blocks until the run reaches a terminal
state and returns the full run dict. Raises `httpx.HTTPStatusError` on 4xx/5xx.

```python
run = client.trigger(
    "flow-id",
    engine="pandas",
    parameters={"date": "2026-06-25", "limit": 1000},
)
if run["status"] != "success":
    raise RuntimeError(f"Flow failed: {run['error_message']}")
```

#### `stream_logs(run_id)`

Yield log entry dicts from the SSE stream of a run. Stops when the server sends
the `done` event.

```python
for entry in client.stream_logs("run-id"):
    print(f"[{entry['level']}] {entry['message']}")
```

## Async client — `AsyncCiaren`

```python
from ciaren_client import AsyncCiaren

async with AsyncCiaren("http://localhost:8055", webhook_secret="my-secret") as client:
    run = await client.trigger("flow-id")
```

All methods are the same as the sync client, prefixed with `await`:

```python
flows = await client.list_flows()
run = await client.trigger("flow-id", engine="polars")
run = await client.get_run("run-id")
```

`stream_logs` is an async generator:

```python
async for entry in client.stream_logs("run-id"):
    print(entry["message"])
```

## Notebook example

```python
from ciaren_client import Ciaren

client = Ciaren("http://localhost:8055", webhook_secret="my-secret")

run = client.trigger("my-etl-flow", parameters={"month": "2026-05"})
print(f"Status: {run['status']}")
print(f"Output: {run['output_location']}")

# Stream the logs after the fact
for entry in client.stream_logs(run["id"]):
    print(f"  {entry['message']}")
```

## Airflow / Prefect example

```python
# Airflow PythonOperator
from ciaren_client import Ciaren

def run_etl(**context):
    client = Ciaren("http://ciaren:8055", webhook_secret="{{ var.value.ciaren_webhook_secret }}")
    run = client.trigger("pipeline-flow")
    if run["status"] != "success":
        raise ValueError(f"Ciaren run failed: {run['error_message']}")

# Prefect task
from prefect import task
from ciaren_client import AsyncCiaren

@task
async def trigger_flow(flow_id: str):
    async with AsyncCiaren("http://ciaren:8055", webhook_secret=...) as client:
        return await client.trigger(flow_id)
```

## Error handling

All methods raise `httpx.HTTPStatusError` when the server returns a 4xx or
5xx status. `trigger()` also raises `ValueError` if `webhook_secret` is not
configured on the client.

```python
import httpx
from ciaren_client import Ciaren

client = Ciaren("http://localhost:8055", webhook_secret="my-secret")
try:
    run = client.trigger("flow-id")
except httpx.HTTPStatusError as e:
    print(f"HTTP {e.response.status_code}: {e.response.json()['detail']}")
```

## See also

- [Webhook Trigger](/guide/webhook) — server-side setup for `trigger()`
- [REST API: Runs](/api/runs) — the underlying run endpoints
- [Scheduling](/guide/scheduling) — cron-based automation without a caller
