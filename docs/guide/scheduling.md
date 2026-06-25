---
title: Scheduling
description: Run flows automatically with FlowFrame's built-in cron scheduler
search: scheduling cron schedule retries catch up auto-disable timezone
---

# Scheduling

FlowFrame includes a lightweight, **in-process** scheduler that runs a flow
automatically on a cron schedule — no broker, no extra services. It is meant for
simple recurring jobs, not heavy orchestration; FlowFrame is not an Airflow/dbt
replacement.

::: info How it runs
The scheduler is a single asyncio poller started inside the API process (via the
FastAPI lifespan). `flowframe serve` runs the API and the scheduler together. Run
the API without it using `flowframe serve --no-scheduler` (or
`FLOWFRAME_SCHEDULER_ENABLED=false`). The scheduler is always disabled in tests.
:::

## Creating a schedule

In the UI, open a flow (or the **Schedules** page) and add a schedule with a cron
expression and timezone. Over the API:

```bash
curl -X POST http://localhost:8055/api/flows/{flow_id}/schedules \
  -H "Content-Type: application/json" \
  -d '{
        "cron": "0 7 * * *",
        "timezone": "America/New_York",
        "engine": "polars",
        "enabled": true,
        "catch_up": false,
        "max_retries": 2,
        "retry_delay_seconds": 60
      }'
```

| Field | Default | Description |
| --- | --- | --- |
| `cron` | — (required) | Standard 5-field cron expression |
| `timezone` | `UTC` | IANA timezone used to interpret the cron |
| `name` / `description` | null | Optional labels |
| `engine` | null | Engine for scheduled runs; falls back to the server default |
| `enabled` | `true` | Whether the schedule is active |
| `catch_up` | `false` | Run slots missed while the server was down |
| `max_retries` | `0` | Retries for a failed run before giving up to the next slot |
| `retry_delay_seconds` | `60` | Base backoff between retries |
| `parameters` | null | [Flow-parameter](./parameters.md) overrides applied to every run this schedule fires |

The UI includes a cron builder so you don't have to hand-write expressions.

::: tip Parameterized flows
If the flow declares [parameters](./parameters.md), the schedule form shows a
**Parameter values** section. Values you set there apply to every run this
schedule fires; blanks fall back to each parameter's default — so one flow can
back several schedules that differ only by their parameter values.
:::

## How it decides what to run

`Schedule.next_run_at` (a naive-UTC timestamp) is the **single source of truth**.
Because it's stored in the database, schedules survive restarts without a separate
jobstore. The poller wakes up periodically
(`SCHEDULER_POLL_INTERVAL_SECONDS`, default 30s), runs anything due, and computes
the next slot.

Scheduled runs are recorded like any other run, tagged with their
`trigger` and `schedule_id`. Browse them via `GET /api/schedules/{id}/runs` or
`GET /api/runs?schedule_id=...`, and they open in the normal
[run detail view](/guide/projects-and-runs#runs).

## Reliability behaviors

- **Concurrency & overlap.** Concurrency is capped
  (`SCHEDULER_MAX_CONCURRENT_RUNS`, default 1), and a schedule **skips** a new
  slot if its previous run is still going, so runs never pile up on each other.
- **Catch-up.** If the server was down across one or more slots, `catch_up`
  decides whether those missed slots run when it comes back (off by default, so
  you don't get a burst of stale runs).
- **Retries.** A failed run retries up to `max_retries` with **exponential
  backoff** (`retry_delay_seconds`, capped at 1 hour) before falling back to the
  next cron slot.
- **Auto-disable.** After `SCHEDULER_MAX_CONSECUTIVE_FAILURES` consecutive failed
  runs (default 5) a schedule is **disabled** with a `disabled_reason`.
  Re-enabling it clears the failure streak.
- **Orphan recovery.** On startup, runs left in `running` (interrupted by a crash)
  are marked `failed` — a single process can't resume them.
- **Manual run-now.** `POST /api/schedules/{id}/run-now` triggers an immediate
  one-off run that stays **outside** the retry/auto-disable machinery.

## Configuration

| Setting | Default | Description |
| --- | --- | --- |
| `FLOWFRAME_SCHEDULER_ENABLED` | `true` | Master on/off switch |
| `FLOWFRAME_SCHEDULER_POLL_INTERVAL_SECONDS` | `30` | How often the poller wakes |
| `FLOWFRAME_SCHEDULER_MAX_CONCURRENT_RUNS` | `1` | Max simultaneous scheduled runs |
| `FLOWFRAME_SCHEDULER_MAX_CONSECUTIVE_FAILURES` | `5` | Failures before auto-disable (0 = never) |

## Limitations

- One schedule runs **one flow**. There are no cross-flow dependencies or DAGs of
  flows.
- The scheduler is single-process. For high-availability or distributed
  scheduling, export the flow's Python and run it under your own orchestrator.

## See also

- [REST API: Schedules](/api/rest-api#schedules)
- [Projects & Runs](/guide/projects-and-runs) — where scheduled runs show up
- [CLI Reference](/guide/cli) — `--no-scheduler` and scheduler env vars
