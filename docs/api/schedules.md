---
title: Schedules API
description: Run flows automatically on a cron schedule
search: api schedules cron timezone engine retries catch_up run-now runs
---

# Schedules API

Run a flow automatically on a cron schedule. A schedule carries a `cron`
expression, a `timezone`, an optional `engine`, and reliability settings
(`max_retries`, `retry_delay_seconds`, `catch_up`, `run_timeout_seconds`). See
[Scheduling](/guide/scheduling) for the behavior.

A schedule for a parameterized flow may also carry a `parameters` object —
[flow-parameter](/guide/parameters) overrides applied to every run it fires.
Blank/omitted values fall back to each parameter's declared default.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/flows/{flow_id}/schedules` | List a flow's schedules |
| `POST` | `/api/flows/{flow_id}/schedules` | Create a schedule for a flow |
| `GET` | `/api/schedules` | List all schedules (optionally `?flow_id=`) |
| `GET` | `/api/schedules/{schedule_id}` | Get one schedule |
| `PATCH` | `/api/schedules/{schedule_id}` | Update a schedule (cron, engine, `is_enabled`, …) |
| `DELETE` | `/api/schedules/{schedule_id}` | Delete a schedule |
| `POST` | `/api/schedules/{schedule_id}/run-now` | Trigger a one-off run immediately |
| `GET` | `/api/schedules/{schedule_id}/runs` | List runs created by this schedule |

A manual `run-now` stays out of the retry/auto-disable machinery — it's a plain
one-off execution.

Schedule reads include a `recent_runs` array — the last five runs the schedule
fired, newest first, each with `id`, `status`, and `created_at`. The UI uses it
for the run-history icons on the Schedules page; for the full history use
`GET /api/schedules/{schedule_id}/runs`.

`GET /api/schedules/{schedule_id}/runs` accepts the same pagination shape as
the runs list: `limit` (1-10000, default 100) and `offset` (default 0).

## See also

- [Scheduling](/guide/scheduling) · [Runs API](./runs.md) · [Flow Parameters](/guide/parameters)
