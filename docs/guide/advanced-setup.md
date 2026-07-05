---
title: Advanced Setup
description: Full configuration reference, databases, execution tuning, and production deployment
search: advanced setup configuration env variables production database postgres reverse proxy cors
---

# Advanced Setup

The [Installation guide](/guide/installation) gets you running with sensible
defaults. This page is the reference for everything you can tune: configuration
sources, every environment variable, alternate databases, execution and scheduler
tuning, and a production deployment outline.

## Configuration sources & precedence

The backend (`Settings`) reads configuration in this order — **later wins**:

1. **Built-in defaults** (shown below).
2. **`.env` file** in the backend working directory.
3. **Environment variables** (prefixed `CIAREN_`).
4. **`ciaren serve` flags** (e.g. `--port`, `--db-url`, `--engine`,
   `--execution-mode`, `--data-dir`, `--no-scheduler`), which are applied as env
   vars before the app loads.
5. **Settings page overrides** for a small editable subset (marked **UI** below).
   Saved in Ciaren's database, applied immediately, and re-applied on every
   startup — so once a value is edited in the UI, it wins over the environment
   until you press **Reset** on that setting.

Scaffold a commented file with `ciaren init`, confirm the resolved values with
`ciaren info`, and validate the environment with `ciaren check`.

## The Settings page

The gear icon in the header opens **Settings** — runtime configuration editable
from the browser: default engine, execution mode, run timeout, upload size,
dataset retention, scheduler tuning, and the ML guardrail limits. Each setting
shows where its current value comes from (default, environment, or a saved
override) and what **Reset** would restore. Changes apply to the whole server
and persist across restarts; the few marked "takes effect after restart" are
consumed once at startup. Overrides are designed for the standard
single-process `ciaren serve`; if you run multiple server processes, a change
applies live to the process that handled it and to every process after restart.

::: warning An override mutes its environment variable
While a setting has a saved override (shown as **Custom**), its `CIAREN_*`
environment variable — and the matching `ciaren serve` flag — has **no
effect**: editing or removing the variable changes nothing until you press
**Reset** on that setting. Each row on the page names its variable and, when
overridden, warns that changes to it are being ignored.
:::

Everything else is deliberately **environment-only**: bootstrap values the
server needs before the database is up (`DATABASE_URL`, `DATA_DIR`, …), secrets
(`API_TOKEN`, `WEBHOOK_SECRET`, `NOTIFY_WEBHOOK_SECRET`), the failure-webhook
URL (Ciaren sends the webhook secret to that URL, so only someone with access
to the environment may point it somewhere), and the security guards (CORS/CSRF,
secret allowlists, storage confinement, plugin enforcement). The Settings page
and its API are reachable by exactly the audience those guards constrain, so
exposing them there would let that audience weaken its own guardrails —
changing them requires access to the server's environment.

## Environment variables

All settings use the `CIAREN_` prefix.

| Variable | Default | Description |
| --- | --- | --- |
| `CIAREN_ENVIRONMENT` | `development` | Environment label (`development`, `production`, …) |
| `CIAREN_DEBUG` | `false` | Extra debug behavior |
| `CIAREN_LOG_FORMAT` | `auto` | Log output: `auto` (color on a TTY, else plain) \| `text` \| `json` |
| `CIAREN_DATABASE_URL` | `sqlite+aiosqlite:///./ciaren.db` | Async database URL (see below) |
| `CIAREN_DATA_DIR` | `.data` | Directory for uploads, run outputs, and previews |
| `CIAREN_DEFAULT_ENGINE` | `polars` | Default dataframe engine (`polars` \| `pandas`) **UI** |
| `CIAREN_EXECUTION_MODE` | `thread` | Compute offload mode (`thread` \| `process`) **UI** |
| `CIAREN_RUN_TIMEOUT_SECONDS` | `0` | Abandon a run after N seconds (`0` = no limit) **UI** |
| `CIAREN_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins (JSON list); also trusted by the CSRF origin guard |
| `CIAREN_TRUSTED_HOSTS` | `[]` | Extra hostnames the CSRF origin guard trusts beyond localhost (see [Security](/security/local-first-trust-model)) |
| `CIAREN_MAX_UPLOAD_SIZE_MB` | `100` | Maximum upload size in MB **UI** |
| `CIAREN_API_TOKEN` | — | Optional bearer token required for `/api/*` requests |
| `CIAREN_WEBHOOK_SECRET` | — | Enables `POST /api/flows/{id}/trigger` with `X-Ciaren-Secret` |
| `CIAREN_PYTHON_TRANSFORM_STRICT` | `false` | Enable stricter static checks for Python Transform scripts |
| `CIAREN_CONNECTOR_BLOCK_PRIVATE_HOSTS` | `false` | Block connector endpoints resolving to private/internal addresses |
| `CIAREN_STORAGE_ALLOWED_ROOTS` | `[]` | Restrict Local Storage roots and SQLite/DuckDB database files to these directories |
| `CIAREN_SECRET_ENV_ALLOWLIST` | `[]` | Env vars (or `PREFIX*` patterns) a connection's `env:` secret reference may name; Ciaren's own config vars are always refused |
| `CIAREN_SECRET_FILE_DIRS` | `[]` | Folders `file:` secret references may read (default: `<DATA_DIR>/secrets` and `/run/secrets`); always enforced |
| `CIAREN_FRONTEND_DIST` | — | Explicit path to a built frontend served by the backend |
| `CIAREN_DATASET_RETENTION_DAYS` | `30` | Days to retain soft-deleted dataset files before purge **UI** |
| `CIAREN_SEED_DEMO` | `true` | Seed the built-in Demo project on first boot |
| `CIAREN_SEED_RUN_FLOWS` | `false` | Run newly seeded demo flows once |
| `CIAREN_SCHEDULER_ENABLED` | `true` | Run the background scheduler |
| `CIAREN_SCHEDULER_POLL_INTERVAL_SECONDS` | `30` | How often the scheduler polls for due runs **UI** |
| `CIAREN_SCHEDULER_MAX_CONCURRENT_RUNS` | `1` | Max simultaneous scheduled runs **UI** |
| `CIAREN_NOTIFY_WEBHOOK_URL` | _(unset)_ | POST a JSON alert here when a run fails or a schedule auto-disables |
| `CIAREN_NOTIFY_WEBHOOK_SECRET` | _(unset)_ | Sent as `X-Ciaren-Secret` so the receiver can verify the sender |
| `CIAREN_SCHEDULER_MAX_CONSECUTIVE_FAILURES` | `5` | Failures before a schedule auto-disables (`0` = never) **UI** |
| `CIAREN_ML_ENABLED` | `true` | Enable ML routes/nodes (built in; set `false` to disable) |
| `CIAREN_MLFLOW_TRACKING_URI` | `./mlruns` | Default MLflow tracking URI |
| `CIAREN_MLFLOW_REGISTRY_URI` | — | Optional MLflow registry URI; defaults to tracking URI |
| `CIAREN_ML_ARTIFACT_DIR` | `ml_artifacts` | Local model artifact root, under `DATA_DIR` when relative |
| `CIAREN_ML_MAX_MODEL_SIZE_MB` | `500` | Maximum model artifact size accepted by ML guardrails **UI** |
| `CIAREN_ML_MAX_TRAINING_ROWS` | `5000000` | Maximum rows accepted for one training job **UI** |
| `CIAREN_ML_MAX_FEATURE_COLUMNS` | `500` | Maximum feature columns accepted for one training job **UI** |
| `CIAREN_MARKETPLACE_INDEX` | bundled catalog | Local marketplace index JSON path for Explore catalog; set `none` to disable |
| `CIAREN_MARKETPLACE_LICENSE_ISSUER_KEYS` | unset | Registers a `TokenLicenseProvider` per configured issuer key, for validating plugin license tokens at startup |
| `CIAREN_REQUIRE_TRUSTED_PLUGINS` | `false` | Require trusted signatures for marketplace/UI installs |
| `CIAREN_PLUGIN_PERMISSION_ENFORCEMENT` | `off` | Runtime enforcement of plugin permissions: `off` / `warn` (log ungranted actions) / `enforce` (block them). Not a sandbox — see [Plugin Security](/security/plugin-security#opt-in-runtime-enforcement) |

Booleans accept `true`/`false`; lists (like `CORS_ORIGINS`) are JSON.
Variables marked **UI** can also be edited at runtime from the Settings
page; a saved override takes precedence over the variable until reset.

## Database

Ciaren uses **async SQLAlchemy**, so the URL must use an async driver.

| Database | URL form | Driver to install |
| --- | --- | --- |
| SQLite (default) | `sqlite+aiosqlite:///./ciaren.db` | bundled |
| PostgreSQL | `postgresql+asyncpg://user:pass@host:5432/dbname` | `pip install asyncpg` |
| MySQL / MariaDB | `mysql+aiomysql://user:pass@host:3306/dbname` | `pip install aiomysql` |

```bash
# backend/.env
CIAREN_DATABASE_URL=postgresql+asyncpg://ciaren:secret@localhost:5432/ciaren
```

The schema is **created automatically** on startup — there is no separate
migration step. `ciaren check` verifies the driver is async and that the
database is reachable.

:::warning Async driver required
A plain `sqlite://`, `postgresql://`, or `mysql://` URL will fail to connect.
Always use the `+aiosqlite` / `+asyncpg` / `+aiomysql` variant.
:::

## Data directory

`CIAREN_DATA_DIR` (default `.data`) is where uploaded files, run outputs, and
previews are written. In production, point it at a persistent, writable volume —
`ciaren check` confirms it's writable. The database stores metadata; the data
dir stores the actual files.

## Execution tuning

Ciaren runs synchronous dataframe work off the event loop so the API stays
responsive. `CIAREN_EXECUTION_MODE` (also editable on the
[Settings page](#the-settings-page)) chooses **how** that work is offloaded.
This section is the practical guidance on which mode to use; for the engine
(polars/pandas) side of performance, see [Engines](/guide/engines).

### `thread` vs `process`: which to use

**Stay on `thread` (the default) unless a symptom below pushes you off it.**
For the typical setup — one person, one run at a time, the polars engine — it
is simpler, fully featured, and just as fast: polars compute is multithreaded
Rust that releases the GIL, so a *single* run already uses every core in
either mode. `process` pays off in specific server scenarios, not in general.

| | `thread` (default) | `process` |
| --- | --- | --- |
| Parallelism **between** concurrent runs | GIL-serialized for pandas-heavy work | true multi-core across runs |
| Parallelism **within** one run | full (polars is multi-core internally) | same |
| Cancelling a run | cooperative and precise | coarse: recycles the whole pool, and is **refused** while other runs share it |
| `RUN_TIMEOUT_SECONDS` | run is abandoned but its thread finishes — CPU stays busy | worker recycled — CPU actually reclaimed |
| A run segfaults or exhausts memory | can take down the whole server | only the worker dies; the API stays up |
| Plugin **node-level** hooks | fire | don't fire (graph-level hooks only) |
| Startup cost per worker | none | spawn re-imports the app — noticeably slower first run, especially on Windows |

Switch to **`process`** when:

- Ciaren is a **long-lived shared server running scheduled jobs** — crash
  isolation and a timeout that really reclaims CPU matter more than precise
  cancellation.
- You raised `SCHEDULER_MAX_CONCURRENT_RUNS` above 1 **and** your flows are
  pandas-heavy — the one case where the GIL actually serializes work.

Stay on **`thread`** when:

- You use Ciaren interactively on your own machine (the install default):
  full cancel support, plugin node hooks, no spawn overhead.
- Your flows run on polars — `process` adds moving parts without adding speed
  for a single run.

### Practical notes

- **Neither mode is a security boundary.** A `process` worker has the same
  privileges and filesystem access as the server; it isolates *crashes*, not
  *code*. For untrusted Python Transform scripts see
  `CIAREN_PYTHON_TRANSFORM_STRICT` and the
  [security docs](/security/plugin-security).
- Switching the mode at runtime (Settings page) is safe: it applies from the
  next run.
- `SCHEDULER_MAX_CONCURRENT_RUNS` also sizes the process pool, and the pool is
  created once — that setting needs a restart to fully apply.
- **`CIAREN_RUN_TIMEOUT_SECONDS`** (`0` = no limit) abandons an over-running
  run in both modes; only `process` mode gets the CPU back immediately (the
  worker is recycled). Pair a timeout with `process` on unattended servers.

```bash
# a shared box running scheduled jobs: isolation + a 5-minute cap per run
CIAREN_RUN_TIMEOUT_SECONDS=300 ciaren serve --execution-mode process
```

## Scheduler tuning

The background scheduler runs inside the API process. See
[Scheduling](/guide/scheduling) for behavior. Relevant settings:

- `CIAREN_SCHEDULER_ENABLED` — master switch (or `ciaren serve --no-scheduler`).
- `CIAREN_SCHEDULER_POLL_INTERVAL_SECONDS` — lower = more responsive, more wakeups.
- `CIAREN_SCHEDULER_MAX_CONCURRENT_RUNS` — cap on simultaneous scheduled runs.
- `CIAREN_SCHEDULER_MAX_CONSECUTIVE_FAILURES` — auto-disable threshold.

:::tip Run the API without the scheduler
If you run multiple API replicas, enable the scheduler on **only one** of them
(`--no-scheduler` on the rest) — it is a single-process poller and isn't designed
to coordinate across replicas.
:::

## CORS

When the frontend is served from a different origin than the API, add that origin
to `CIAREN_CORS_ORIGINS` (a JSON list):

```bash
CIAREN_CORS_ORIGINS=["https://ciaren.example.com","http://localhost:5173"]
```

## Production deployment

Ciaren is local-first, but you can host it. A typical setup:

### Backend

```bash
python -m pip install --pre ciaren
# bind to all interfaces, no reload, info logs
ciaren serve --host 0.0.0.0 --port 8055 --log-level info
```

- Set `CIAREN_ENVIRONMENT=production`.
- Use a managed PostgreSQL/MySQL via `CIAREN_DATABASE_URL`.
- Put the data dir on a persistent volume.
- Run it under a process manager (systemd, Docker, etc.).
- Set `CIAREN_LOG_FORMAT=json` to emit one JSON object per log line
  (level, logger, message, timestamp, plus any structured fields) for a log
  collector. The default `auto` prints human-readable lines.
- Point your orchestrator's **liveness** probe at `/health` and its
  **readiness** probe at `/ready` (the latter returns `503` until the database
  is reachable). See [REST API conventions](/api/rest-api#conventions).

### Frontend

The React app is a static build that calls the API at the path `/api` on **its
own origin** (there is no runtime API-URL variable — only the dev-server proxy).
So in production you serve the built files and reverse-proxy `/api` to the
backend, typically behind one web server:

```bash
cd frontend
npm ci
npm run build         # outputs static files to frontend/dist/
```

Serve `frontend/dist/` and route `/api/*` to the backend. Example nginx:

```nginx
server {
  listen 80;
  server_name ciaren.example.com;

  root /srv/ciaren/dist;            # frontend build
  location / { try_files $uri /index.html; }

  location /api/ {                      # proxy to the backend
    proxy_pass http://127.0.0.1:8055;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
}
```

Because the browser then talks to a single origin, you usually don't need to
touch `CORS_ORIGINS` for this layout.

::: warning Alpha software
Ciaren is in early development and has not completed a formal independent
third-party security audit. If you deploy it beyond localhost, review the
[security notes](https://github.com/ciaren-labs/Ciaren/blob/main/SECURITY.md),
set `CIAREN_API_TOKEN`, place it behind trusted access controls, and validate
the deployment against your own data and operational requirements.
:::

### Frontend dev overrides

For local development against a non-default backend, the dev server (not the
production build) honors:

- `VITE_PORT` — change the dev server port (default `5173`).
- `VITE_API_TARGET` — where the dev proxy forwards `/api` (default
  `http://localhost:8055`).

```bash
VITE_PORT=3000 VITE_API_TARGET=http://localhost:8001 npm run dev
```

## Verifying

```bash
ciaren info     # print resolved settings (DB password redacted)
ciaren check    # data dir writable? async driver? DB reachable? engines present?
```

## See also

- [CLI Reference](/guide/cli) — every command and flag
- [Engines](/guide/engines) — polars/pandas, execution mode, timeouts
- [Scheduling](/guide/scheduling) — the background scheduler
- [Installation](/guide/installation) — the basic setup
