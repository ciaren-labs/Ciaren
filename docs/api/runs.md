---
title: Runs API
description: Execute flows and read run status, logs, and per-node results
search: api runs execute engine status logs node results duration filter stream sse webhook
---

# Runs API

Execute a flow and read run metadata, status, logs, and per-node results.
The run request accepts an optional `engine`; when omitted it falls back to
the flow's saved `graph_json.engine`, and if that's also unset, to the
server's `DEFAULT_ENGINE` (`polars` out of the box). The resolved engine is
recorded on the run for reproducibility. Each run also stores a per-node
result (status, row/column counts, a small sample, and `duration_ms`) for the
read-only run view.

A run request may also include a `parameters` object to override the flow's
declared [parameters](/guide/parameters) for this run. The resolved values are
returned on the run (and re-used by **Retry**). Unknown names, missing required
values, or type mismatches return `400`. It may also include `input_dataset_id`
(attribute the run to a specific dataset, overriding the graph's own input
node) and `timeout_seconds` (override the server's default run timeout; `0`
means no limit).

```bash
curl -X POST http://localhost:8055/api/flows/{flow_id}/runs \
  -H "Content-Type: application/json" \
  -d '{ "engine": "polars", "parameters": { "input_path": "data/2026-06.csv", "keep": 100 } }'
```

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/flows/{flow_id}/runs` | Execute a flow (optional body `{"engine": "polars"}`) and create a run |
| `GET` | `/api/runs` | List runs, filterable by `flow_id`, `project_id`, `dataset_id`, `status`, `schedule_id`, and start-time range |
| `GET` | `/api/runs/{run_id}` | Get run status, output location, logs, and per-node results |
| `POST` | `/api/runs/{run_id}/retry` | Re-run this run's flow with the same config; produces a new run (new id) |
| `POST` | `/api/runs/{run_id}/cancel` | Request cancellation of a running run (`202`); `400` if it's not `running`, if the row is stale with no active worker, or if process-mode execution shares the pool with other runs |
| `GET` | `/api/runs/{run_id}/output` | Stream a specific output node's result file (`?node_id=`) |
| `GET` | `/api/runs/{run_id}/logs/stream` | Stream run log entries as [server-sent events](#log-streaming-sse) |

Runs created by a schedule carry a `trigger` and `schedule_id` — filter with
`GET /api/runs?schedule_id=` or `GET /api/schedules/{id}/runs`.

Runs started via the [webhook endpoint](/guide/webhook) carry `"trigger": "webhook"`.

Date filters are named for the column they use: `started_after` and
`started_before` compare against `started_at` (ISO 8601 datetimes). The list also
accepts `sort_by` (`created_at`, `started_at`, `status`), `sort_order` (`asc` or
`desc`), `limit` (1-10000, default 100), and `offset` (default 0).

## Restart recovery

Ciaren runs as a single process, so a run still in `running` when the server
restarts (a crash, a deploy, `Ctrl-C` mid-run) was interrupted and can never
finish. On startup — **regardless of whether the scheduler is enabled** — every
such run is reconciled to `failed` with the error message
`Run interrupted by a server restart.`, so run history stays honest and the run
drops out of "active" listings. Re-run it with **Retry** once the server is back.

## Log streaming (SSE)

`GET /api/runs/{run_id}/logs/stream` returns a `text/event-stream` response.

This is **wait-and-fetch, not live streaming**. A run's logs are written once,
atomically, when it finishes, so there is nothing partial to stream mid-run. While
the run is still executing the endpoint emits only SSE **keepalive comments**
(`: keepalive` lines, ignored by clients) to hold the connection open on long runs.
Once the run reaches a terminal state it emits each stored log entry as a `data:`
event and closes with an `event: done` frame:

```
: keepalive

: keepalive

data: {"level":"info","message":"Flow executed in 420 ms, wrote 1 output(s)","duration_ms":420}

data: {"level":"info","message":"Resolved dataset versions","versions":{...}}

event: done
data: {"status":"success","run_id":"run-abc123"}
```

If the wait exceeds the server's maximum (default 1 hour), the stream ends with an
`event: error` frame instead:

```
event: error
data: {"detail":"Timed out waiting for run completion"}
```

Returns **404** immediately (before any SSE data) when the run doesn't exist.

Response headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no` (nginx
buffering disabled).

```bash
# Stream logs for a run
curl -N http://localhost:8055/api/runs/RUN_ID/logs/stream
```

The [Python SDK](/guide/sdk) wraps this as `client.stream_logs(run_id)`.

## See also

- [Flows API](./flows.md) · [Schedules API](./schedules.md)
- [Webhook Trigger](/guide/webhook) · [Python SDK](/guide/sdk)
- [Flow Parameters](/guide/parameters) · [Engines (polars / pandas)](/guide/engines)
