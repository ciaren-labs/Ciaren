---
title: Python SDK
description: Control Ciaren from Python scripts, notebooks, and orchestrators
search: sdk python client ciaren-client trigger run stream logs async httpx
---

# Python SDK

`ciaren-client` is a thin Python package that wraps the Ciaren REST API
with a friendly interface. It installs independently from the full Ciaren
application, ships both a synchronous (`Ciaren`) and an async (`AsyncCiaren`)
client, and depends only on `httpx`.

Current alpha version: `0.1.0-alpha.1`. The package is typed and ships
`py.typed` for editors and type checkers.

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

The sync and async clients expose the same API. Async methods use the same
names and are awaited.

| Area | Common methods |
|---|---|
| Projects | `list_projects`, `create_project`, `get_project`, `update_project`, `delete_project` |
| Datasets | `upload_dataset`, `list_datasets`, `get_dataset`, `update_dataset`, `delete_dataset`, `restore_dataset`, `list_dataset_versions`, `download_dataset_version`, `get_dataset_schema`, `get_dataset_sample`, `get_dataset_profile` |
| Flows | `list_flows`, `create_flow`, `import_flow`, `get_flow`, `update_flow`, `delete_flow`, `preview_flow`, `export_flow_python` |
| Runs | `create_run`, `list_runs`, `get_run`, `retry_run`, `download_run_output`, `stream_logs` |
| Schedules | `create_schedule`, `list_schedules`, `get_schedule`, `update_schedule`, `delete_schedule`, `run_schedule_now`, `list_schedule_runs` |
| Connections | `list_connections`, `create_connection`, `get_connection`, `update_connection`, `delete_connection`, `test_connection`, `list_connection_tables`, `list_connection_objects` |
| Catalog and transforms | `list_catalog_nodes`, `list_catalog_connectors`, `list_catalog_exporters`, `list_catalog_categories`, `list_transformations`, `preview_transformation` |
| ML | `get_run_ml_metrics`, `register_run_model`, `list_registered_models`, `list_model_catalog`, `set_model_alias`, `clear_model_alias`, `list_ml_experiments` |
| Plugins and marketplace | `list_plugins`, `plugin_diagnostics`, `install_plugin`, `enable_plugin`, `disable_plugin`, `grant_plugin_permissions`, `list_marketplace`, `install_marketplace_plugin` |
| Webhook | `webhook_status`, `trigger` |

#### Projects

```python
project = client.create_project("Revenue Ops", color="emerald")
projects = client.list_projects()
```

#### Datasets

```python
dataset = client.upload_dataset("sales.csv", project_id=project["id"])
schema = client.get_dataset_schema(dataset["id"])
sample = client.get_dataset_sample(dataset["id"])
```

#### Flows

```python
flows = client.list_flows()
# → [{"id": "...", "name": "Sales Pipeline", ...}, ...]

flow = client.get_flow("flow-id")
export = client.export_flow_python("flow-id")
```

#### Runs

`list_runs` mirrors the filtering, sorting, and pagination options of
`GET /api/runs`. `started_after` and `started_before` accept either a
`datetime` or an ISO 8601 string.

```python
run = client.create_run("flow-id", engine="polars")
output = client.download_run_output(run["id"], "node-id")
```

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

```python
run = client.get_run("run-id")
print(run["status"])  # "pending" | "running" | "success" | "failed"
```

`retry_run` re-runs the same flow with the original run's config, creating a
new run with a new id.

```python
new_run = client.retry_run("run-id")
```

#### Schedules

```python
schedule = client.create_schedule("flow-id", "0 9 * * *", timezone="America/Bogota")
client.run_schedule_now(schedule["id"])
```

#### Connections

```python
connection = client.create_connection(
    name="Warehouse",
    provider="postgres",
    kind="database",
    config={"host": "...", "database": "..."},
)
tables = client.list_connection_tables(connection["id"])
```

#### ML

```python
metrics = client.get_run_ml_metrics("run-id")
models = client.list_registered_models()
client.set_model_alias("churn-model", version=3, alias="production")
```

#### Plugins and marketplace

```python
plugins = client.list_plugins()
catalog = client.list_marketplace()
```

#### Webhook trigger

`trigger(flow_id, *, engine=None, parameters=None)` starts a run via the
webhook endpoint. It blocks until the run reaches a terminal state and returns
the full run dict. It raises `httpx.HTTPStatusError` on 4xx/5xx.

```python
run = client.trigger(
    "flow-id",
    engine="pandas",
    parameters={"date": "2026-06-25", "limit": 1000},
)
if run["status"] != "success":
    raise RuntimeError(f"Flow failed: {run['error_message']}")
```

#### Streaming logs

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
- [REST API](/api/rest-api) — endpoint overview behind the SDK
- [REST API: Runs](/api/runs) — the underlying run endpoints
- [Scheduling](/guide/scheduling) — cron-based automation without a caller
