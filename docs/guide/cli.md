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
| `--port` | `8055` | Bind port |
| `--reload` | off | Auto-reload on code changes (development only) |
| `--db-url` | — | Async database URL; overrides `FLOWFRAME_DATABASE_URL` |
| `--data-dir` | — | Uploads/outputs directory; overrides `FLOWFRAME_DATA_DIR` |
| `--engine` | — | Default engine `polars` \| `pandas`; overrides `FLOWFRAME_DEFAULT_ENGINE` |
| `--execution-mode` | — | `thread` \| `process`; overrides `FLOWFRAME_EXECUTION_MODE` |
| `--log-level` | — | uvicorn log level (`critical`…`trace`) |
| `--no-scheduler` | off | Start the API without the background scheduler |
| `--env-file` | — | Load environment variables from this file before resolving settings |

Flags are translated into the matching environment variables before the app is
imported, so they take precedence over your `.env`.

### Pointing at a specific env file

By default FlowFrame reads `./.env`. Use `--env-file` to load a different file
(for example a per-environment config) before settings are resolved:

```bash
flowframe serve --env-file /etc/flowframe/production.env
```

Precedence is **flags > existing environment variables > `--env-file` > defaults**,
so values already exported in your shell are not overridden by the file. The same
flag works on `flowframe info` and `flowframe check`, which is handy for
inspecting or validating a specific config:

```bash
flowframe info  --env-file /etc/flowframe/production.env
flowframe check --env-file /etc/flowframe/production.env
```

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
[ok]   data_dir: /path/to/.data
[ok]   async_driver: sqlite+aiosqlite:///./flowframe.db
[ok]   database: reachable
[ok]   engines: pandas, polars

All checks passed.
```

Both `info` and `check` accept `--output json` for scripting and CI:

```bash
flowframe info --output json
flowframe check --output json   # {"ok": true, "checks": [...]}; exit 1 on failure
```

## `flowframe db`

Manage the database schema through **Alembic migrations**. This is the
production-grade path: it versions the schema and applies changes in order,
across SQLite, PostgreSQL, and MySQL.

```bash
flowframe db upgrade            # apply all migrations up to the latest revision
flowframe db upgrade --revision <id>
flowframe db current            # show the revision the database is stamped at
flowframe db reset --yes        # DROP every table and rebuild from migrations
```

| Subcommand | Description |
|---|---|
| `upgrade` | Apply migrations up to `--revision` (default `head`). Safe to re-run. |
| `current` | Print the revision the database is currently at. |
| `reset` | **Destructive.** Drop all tables and rebuild. Requires `--yes`; refuses when `FLOWFRAME_ENVIRONMENT=production` unless `--force`. |

All three accept `--env-file` so you can target a specific environment's config.

:::tip Upgrading an existing database is safe
`flowframe serve` creates any missing tables on startup, so an existing
FlowFrame database has the full schema but no migration history. The first
`flowframe db upgrade` detects this and **adopts** the schema (records the
current revision) instead of trying to re-create existing tables — so adopting
Alembic never destroys or rewrites your data. From then on, upgrades apply only
the new migrations.
:::

:::warning `db reset` deletes all data
`reset` drops every table. It exists for local development and test
environments. It refuses to run in production unless you pass `--force`.
:::

### Recommended production flow

1. Set `FLOWFRAME_DATABASE_URL` to your async Postgres/MySQL URL.
2. Run `flowframe db upgrade` as part of each deploy (before starting the app).
3. Start the server with `flowframe serve`.

## `flowframe transformations`

Inspect the transformation node types the engine supports — the same set the
visual editor exposes.

```bash
flowframe transformations list
flowframe transformations list --output json
```

```text
23 transformation node types:
  binColumn         inputs=1
  calculatedColumn  inputs=1
  concatRows        inputs=many
  ...
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
