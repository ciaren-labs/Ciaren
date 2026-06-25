---
title: Runs API
description: Execute flows and read run status, logs, and per-node results
search: api runs execute engine status logs node results duration filter
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

Runs created by a schedule carry a `trigger` and `schedule_id` — filter with
`GET /api/runs?schedule_id=` or `GET /api/schedules/{id}/runs`.

## See also

- [Flows API](./flows.md) · [Schedules API](./schedules.md)
- [Flow Parameters](/guide/parameters) · [Engines (polars / pandas)](/guide/engines)
