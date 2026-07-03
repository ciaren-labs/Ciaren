---
title: CLI Reference
description: The ciaren command — serve, init, info, and check
search: cli ciaren serve init info check command env variables flags
---

# CLI Reference

Installing the backend (`pip install -e .`) exposes a `ciaren` command — the
setup surface for running and configuring Ciaren. It uses only the standard
library, so there's nothing extra to install.

```bash
ciaren --help
ciaren --version
```

## `ciaren serve`

Run the API server **and** the background scheduler in a single process (no
broker, no extra services). This is the recommended way to start Ciaren.

```bash
ciaren serve
ciaren serve --port 8001 --reload
ciaren serve --engine pandas --execution-mode process
ciaren serve --no-scheduler
```

| Flag | Default | Description |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Bind host |
| `--port` | `8055` | Bind port |
| `--reload` | off | Auto-reload on code changes (development only) |
| `--db-url` | — | Async database URL; overrides `CIAREN_DATABASE_URL` |
| `--data-dir` | — | Uploads/outputs directory; overrides `CIAREN_DATA_DIR` |
| `--engine` | — | Default engine `polars` \| `pandas`; overrides `CIAREN_DEFAULT_ENGINE` |
| `--execution-mode` | — | `thread` \| `process`; overrides `CIAREN_EXECUTION_MODE` |
| `--log-level` | — | uvicorn log level (`critical`…`trace`) |
| `--no-scheduler` | off | Start the API without the background scheduler |
| `--no-demo` | off | Skip seeding the built-in Demo project on first boot |
| `--run-seed-flows` | off | Run every newly seeded demo flow once after first-boot seeding |
| `--env-file` | — | Load environment variables from this file before resolving settings |

Flags are translated into the matching environment variables before the app is
imported, so they take precedence over your `.env`.

### Pointing at a specific env file

By default Ciaren reads `./.env`. Use `--env-file` to load a different file
(for example a per-environment config) before settings are resolved:

```bash
ciaren serve --env-file /etc/ciaren/production.env
```

Precedence is **flags > existing environment variables > `--env-file` > defaults**,
so values already exported in your shell are not overridden by the file. The same
flag works on `ciaren info` and `ciaren check`, which is handy for
inspecting or validating a specific config:

```bash
ciaren info  --env-file /etc/ciaren/production.env
ciaren check --env-file /etc/ciaren/production.env
```

## `ciaren init`

Write a commented starter `.env` to get going quickly.

```bash
ciaren init                 # writes ./.env
ciaren init --path .env.local
ciaren init --force         # overwrite an existing file
ciaren init --no-ml         # skip provisioning the default local MLflow directory
```

## `ciaren info`

Print the **resolved** configuration the server would use (the database password
is redacted). Handy for confirming which `.env` / env vars are in effect.

```bash
ciaren info
```

```text
Ciaren resolved configuration:
  app_name             Ciaren
  environment          development
  database_url         sqlite+aiosqlite:///./ciaren.db
  data_dir             /path/to/.data
  default_engine       polars
  execution_mode       thread
  scheduler_enabled    True
  ...
```

## `ciaren check`

Validate the environment and exit non-zero on failure — useful in setup scripts
and CI. It checks that:

- the data directory is writable,
- the database URL uses an **async** driver,
- the database is reachable, and
- the dataframe engines are importable.

```bash
ciaren check
```

```text
[ok]   data_dir: /path/to/.data
[ok]   async_driver: sqlite+aiosqlite:///./ciaren.db
[ok]   database: reachable
[ok]   engines: pandas, polars

All checks passed.
```

Both `info` and `check` accept `--output json` for scripting and CI:

```bash
ciaren info --output json
ciaren check --output json   # {"ok": true, "checks": [...]}; exit 1 on failure
```

## `ciaren db`

Manage the database schema through **Alembic migrations**. This is the
production-grade path: it versions the schema and applies changes in order,
across SQLite, PostgreSQL, and MySQL.

```bash
ciaren db upgrade            # apply all migrations up to the latest revision
ciaren db upgrade --revision <id>
ciaren db current            # show the revision the database is stamped at
ciaren db reset --yes        # DROP every table and rebuild from migrations
```

| Subcommand | Description |
| --- | --- |
| `upgrade` | Apply migrations up to `--revision` (default `head`). Safe to re-run. |
| `current` | Print the revision the database is currently at. |
| `reset` | **Destructive.** Drop all tables and rebuild. Requires `--yes`; refuses when `CIAREN_ENVIRONMENT=production` unless `--force`. |

All three accept `--env-file` so you can target a specific environment's config.

:::tip Upgrading an existing database is safe
`ciaren serve` creates any missing tables on startup, so an existing
Ciaren database has the full schema but no migration history. The first
`ciaren db upgrade` detects this and **adopts** the schema (records the
current revision) instead of trying to re-create existing tables — so adopting
Alembic never destroys or rewrites your data. From then on, upgrades apply only
the new migrations.
:::

:::warning `db reset` deletes all data
`reset` drops every table. It exists for local development and test
environments. It refuses to run in production unless you pass `--force`.
:::

### Recommended production flow

1. Set `CIAREN_DATABASE_URL` to your async Postgres/MySQL URL.
2. Run `ciaren db upgrade` as part of each deploy (before starting the app).
3. Start the server with `ciaren serve`.

## `ciaren transformations`

Inspect the transformation node types the engine supports — the same set the
visual editor exposes.

```bash
ciaren transformations list
ciaren transformations list --output json
```

```text
40+ transformation node types:
  binColumn         inputs=1
  calculatedColumn  inputs=1
  concatRows        inputs=many
  ...
```

## `ciaren flow`

Validate and migrate [`.flow` document](/specs/flow-format) files — the portable,
versioned description of a flow. Useful in CI to catch a malformed or outdated
project before importing it.

```bash
ciaren flow validate project.flow              # schema + graph structure
ciaren flow validate project.flow --output json
ciaren flow migrate  project.flow --to 1.1.0   # print the migrated document
ciaren flow migrate  project.flow --to 1.1.0 --write   # write back (keeps a .bak)
```

| Subcommand | Description |
| --- | --- |
| `validate` | Validate document shape **and** graph structure. Exits non-zero (and prints `INVALID`) on failure. |
| `migrate` | Migrate to a newer schema version (default: the latest this build supports). Prints to stdout unless `--write`. |

:::warning `--write` never mutates silently
`migrate --write` keeps a `.bak` backup of the original next to the file before
writing the migrated version.
:::

## Plugin tooling: `ciaren-plugin`

Installing, inspecting, and (for publishers) signing plugins is a separate
command — `ciaren-plugin`, from the same `ciaren` distribution — so the
everyday `ciaren` CLI doesn't carry the plugin-authoring surface. See the
[Plugin CLI Reference](/plugins/cli-reference) for every subcommand, and
[Packaging & Distribution](/plugins/packaging-and-distribution) for the full
publishing workflow.

```bash
ciaren-plugin list                          # discovered plugins + status
ciaren-plugin install my-plugin.ciarenplugin    # verify + install
ciaren-plugin enable acme.myplugin
```

Running the old `ciaren plugin ...` form prints a pointer to the new command.

## Environment variables

All settings use the `CIAREN_` prefix and can be set via the environment or a
`.env` file in the backend directory.

| Variable | Default | Description |
| --- | --- | --- |
| `CIAREN_DATABASE_URL` | `sqlite+aiosqlite:///./ciaren.db` | Async database URL |
| `CIAREN_DATA_DIR` | `.data` | Where uploads, outputs, and previews are written |
| `CIAREN_DEFAULT_ENGINE` | `polars` | Default engine for runs (`polars` \| `pandas`) |
| `CIAREN_EXECUTION_MODE` | `thread` | Compute offload mode (`thread` \| `process`) |
| `CIAREN_RUN_TIMEOUT_SECONDS` | `0` | Abandon a run after N seconds (0 = no limit) |
| `CIAREN_LOG_FORMAT` | `auto` | Log output format (`auto` \| `text` \| `json`) |
| `CIAREN_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins (JSON list) |
| `CIAREN_MAX_UPLOAD_SIZE_MB` | `100` | Maximum upload size |
| `CIAREN_ENVIRONMENT` | `development` | Environment label |
| `CIAREN_API_TOKEN` | — | Optional bearer token required for `/api/*` requests |
| `CIAREN_WEBHOOK_SECRET` | — | Enables `POST /api/flows/{id}/trigger` webhook auth |
| `CIAREN_PYTHON_TRANSFORM_STRICT` | `false` | Enable stricter static checks for Python Transform scripts |
| `CIAREN_CONNECTOR_BLOCK_PRIVATE_HOSTS` | `false` | Block connector endpoints that resolve to private/internal addresses |
| `CIAREN_STORAGE_ALLOWED_ROOTS` | `[]` | Restrict Local Storage connector roots to these directories |
| `CIAREN_FRONTEND_DIST` | — | Explicit path to a built frontend to serve from `ciaren serve` |
| `CIAREN_DATASET_RETENTION_DAYS` | `30` | Days to retain soft-deleted dataset files before purge |
| `CIAREN_SEED_DEMO` | `true` | Seed the built-in Demo project on first boot |
| `CIAREN_SEED_RUN_FLOWS` | `false` | Run newly seeded demo flows once |
| `CIAREN_SCHEDULER_ENABLED` | `true` | Run the background scheduler |
| `CIAREN_SCHEDULER_POLL_INTERVAL_SECONDS` | `30` | Scheduler poll interval |
| `CIAREN_SCHEDULER_MAX_CONCURRENT_RUNS` | `1` | Max simultaneous scheduled runs |
| `CIAREN_SCHEDULER_MAX_CONSECUTIVE_FAILURES` | `5` | Failures before auto-disable (0 = never) |
| `CIAREN_ML_ENABLED` | `true` | Enable ML routes/nodes (built in; set `false` to disable) |
| `CIAREN_MLFLOW_TRACKING_URI` | `./mlruns` | Default MLflow tracking URI |
| `CIAREN_MLFLOW_REGISTRY_URI` | — | Optional MLflow registry URI; defaults to tracking URI |
| `CIAREN_ML_ARTIFACT_DIR` | `ml_artifacts` | Local model artifact root, under `DATA_DIR` when relative |
| `CIAREN_ML_MAX_MODEL_SIZE_MB` | `500` | Maximum model artifact size accepted by ML guardrails |
| `CIAREN_ML_MAX_TRAINING_ROWS` | `5000000` | Maximum rows accepted for one training job |
| `CIAREN_ML_MAX_FEATURE_COLUMNS` | `500` | Maximum feature columns accepted for one training job |
| `CIAREN_MARKETPLACE_INDEX` | bundled catalog | Local marketplace index JSON path for Explore catalog; set `none` to disable |
| `CIAREN_REQUIRE_TRUSTED_PLUGINS` | `false` | Require trusted signatures for marketplace/UI installs |
| `CIAREN_PLUGINS_DIR` | — | Extra plugin directories to scan (`os.pathsep`-separated); see [Writing a plugin](/plugins/writing-a-plugin) |

:::warning Async driver required
`CIAREN_DATABASE_URL` must use an async driver: `sqlite+aiosqlite://`,
`postgresql+asyncpg://`, or `mysql+aiomysql://`. `ciaren check` flags a
non-async URL.
:::

## See also

- [Installation](/guide/installation) — first-time setup
- [Engines](/guide/engines) — `--engine`, `--execution-mode`, run timeouts
- [Scheduling](/guide/scheduling) — the background scheduler
