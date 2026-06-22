---
title: CLI Reference
description: The flowframe command — serve, init, info, and check
search: cli flowframe serve init info check command env variables flags
---

# CLI Reference

Installing the backend (`pip install -e .`) exposes a `flowframe` command — the
setup surface for running and configuring FlowFrame. It uses only the standard
library, so there's nothing extra to install.

```bash
flowframe --help
flowframe --version
```

## `flowframe serve`

Run the API server **and** the background scheduler in a single process (no
broker, no extra services). This is the recommended way to start FlowFrame.

```bash
flowframe serve
flowframe serve --port 8001 --reload
flowframe serve --engine pandas --execution-mode process
flowframe serve --no-scheduler
```

| Flag | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Bind host |
| `--port` | `8000` | Bind port |
| `--reload` | off | Auto-reload on code changes (development only) |
| `--db-url` | — | Async database URL; overrides `FLOWFRAME_DATABASE_URL` |
| `--data-dir` | — | Uploads/outputs directory; overrides `FLOWFRAME_DATA_DIR` |
| `--engine` | — | Default engine `polars` \| `pandas`; overrides `FLOWFRAME_DEFAULT_ENGINE` |
| `--execution-mode` | — | `thread` \| `process`; overrides `FLOWFRAME_EXECUTION_MODE` |
| `--log-level` | — | uvicorn log level (`critical`…`trace`) |
| `--no-scheduler` | off | Start the API without the background scheduler |

Flags are translated into the matching environment variables before the app is
imported, so they take precedence over your `.env`.

## `flowframe init`

Write a commented starter `.env` to get going quickly.

```bash
flowframe init                 # writes ./.env
flowframe init --path .env.local
flowframe init --force         # overwrite an existing file
```

## `flowframe info`

Print the **resolved** configuration the server would use (the database password
is redacted). Handy for confirming which `.env` / env vars are in effect.

```bash
flowframe info
```

```text
FlowFrame resolved configuration:
  app_name             FlowFrame
  environment          development
  database_url         sqlite+aiosqlite:///./flowframe.db
  data_dir             /path/to/.data
  default_engine       polars
  execution_mode       thread
  scheduler_enabled    True
  ...
```

## `flowframe check`

Validate the environment and exit non-zero on failure — useful in setup scripts
and CI. It checks that:

- the data directory is writable,
- the database URL uses an **async** driver,
- the database is reachable, and
- the dataframe engines are importable.

```bash
flowframe check
```

```text
[ok]   data dir writable: /path/to/.data
[ok]   database driver is async: sqlite+aiosqlite:///./flowframe.db
[ok]   database reachable
[ok]   engines available: pandas, polars

All checks passed.
```

## Environment variables

All settings use the `FLOWFRAME_` prefix and can be set via the environment or a
`.env` file in the backend directory.

| Variable | Default | Description |
|---|---|---|
| `FLOWFRAME_DATABASE_URL` | `sqlite+aiosqlite:///./flowframe.db` | Async database URL |
| `FLOWFRAME_DATA_DIR` | `.data` | Where uploads, outputs, and previews are written |
| `FLOWFRAME_DEFAULT_ENGINE` | `polars` | Default engine for runs (`polars` \| `pandas`) |
| `FLOWFRAME_EXECUTION_MODE` | `thread` | Compute offload mode (`thread` \| `process`) |
| `FLOWFRAME_RUN_TIMEOUT_SECONDS` | `0` | Abandon a run after N seconds (0 = no limit) |
| `FLOWFRAME_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins (JSON list) |
| `FLOWFRAME_MAX_UPLOAD_SIZE_MB` | `100` | Maximum upload size |
| `FLOWFRAME_ENVIRONMENT` | `development` | Environment label |
| `FLOWFRAME_SCHEDULER_ENABLED` | `true` | Run the background scheduler |
| `FLOWFRAME_SCHEDULER_POLL_INTERVAL_SECONDS` | `30` | Scheduler poll interval |
| `FLOWFRAME_SCHEDULER_MAX_CONCURRENT_RUNS` | `1` | Max simultaneous scheduled runs |
| `FLOWFRAME_SCHEDULER_MAX_CONSECUTIVE_FAILURES` | `5` | Failures before auto-disable (0 = never) |

:::warning Async driver required
`FLOWFRAME_DATABASE_URL` must use an async driver: `sqlite+aiosqlite://`,
`postgresql+asyncpg://`, or `mysql+aiomysql://`. `flowframe check` flags a
non-async URL.
:::

## See also

- [Installation](/guide/installation) — first-time setup
- [Engines](/guide/engines) — `--engine`, `--execution-mode`, run timeouts
- [Scheduling](/guide/scheduling) — the background scheduler
