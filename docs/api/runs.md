---
title: Runs API
description: Execute flows and read run status, logs, and per-node results
search: api runs execute engine status logs node results duration filter stream sse webhook
---

# Runs API

Execute a flow and read run metadata, status, logs, and per-node results.
The run request accepts an optional `engine` (`polars` default, or `pandas`),
which is recorded on the run for reproducibility. Each run also stores a
per-node result (status, row/column counts, a small sample, and `duration_ms`)
for the read-only run view.

A run request may also include a `parameters` object to override the flow's
declared [parameters](/guide/parameters) for this run. The resolved values are
returned on the run (and re-used by **Retry**). Unknown names, missing required
values, or type mismatches return `400`.

```bash
curl -X POST http://localhost:8055/api/flows/{flow_id}/runs \
  -H "Content-Type: application/json" \
  -d '{ "engine": "polars", "parameters": { "input_path": "data/2026-06.csv", "keep": 100 } }'
```

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/flows/{flow_id}/runs` | Execute a flow (optional body `{"engine": "polars"}`) and create a run |
| `GET` | `/api/runs` | List runs, filterable by `flow_id`, `project_id`, `dataset_id`, `status`, `schedule_id`, and date range |
| `GET` | `/api/runs/{run_id}` | Get run status, output location, logs, and per-node results |
| `POST` | `/api/runs/{run_id}/retry` | Re-run this run's flow with the same config; produces a new run (new id) |
| `GET` | `/api/runs/{run_id}/logs/stream` | Stream run log entries as [server-sent events](#log-streaming-sse) |

Runs created by a schedule carry a `trigger` and `schedule_id` — filter with
`GET /api/runs?schedule_id=` or `GET /api/schedules/{id}/runs`.

Runs started via the [webhook endpoint](/guide/webhook) carry `"trigger": "webhook"`.

## Log streaming (SSE)

`GET /api/runs/{run_id}/logs/stream` returns a `text/event-stream` response.
It polls the database until the run reaches a terminal state, then emits each
stored log entry as an SSE `data:` event and closes with an `event: done` frame:

```
data: {"level":"info","message":"Flow executed in 420 ms, wrote 1 output(s)","duration_ms":420}

data: {"level":"info","message":"Resolved dataset versions","versions":{...}}

event: done
data: {"status":"success","run_id":"run-abc123"}
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
