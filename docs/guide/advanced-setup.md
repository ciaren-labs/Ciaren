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
3. **Environment variables** (prefixed `FLOWFRAME_`).
4. **`flowframe serve` flags** (e.g. `--port`, `--db-url`, `--engine`,
   `--execution-mode`, `--data-dir`, `--no-scheduler`), which are applied as env
   vars before the app loads.

Scaffold a commented file with `flowframe init`, confirm the resolved values with
`flowframe info`, and validate the environment with `flowframe check`.

## Environment variables

All settings use the `FLOWFRAME_` prefix.

| Variable | Default | Description |
|---|---|---|
| `FLOWFRAME_APP_NAME` | `FlowFrame` | Display name |
| `FLOWFRAME_ENVIRONMENT` | `development` | Environment label (`development`, `production`, …) |
| `FLOWFRAME_DEBUG` | `false` | Extra debug behavior |
| `FLOWFRAME_DATABASE_URL` | `sqlite+aiosqlite:///./flowframe.db` | Async database URL (see below) |
| `FLOWFRAME_DATA_DIR` | `.data` | Directory for uploads, run outputs, and previews |
| `FLOWFRAME_DEFAULT_ENGINE` | `polars` | Default dataframe engine (`polars` \| `pandas`) |
| `FLOWFRAME_EXECUTION_MODE` | `thread` | Compute offload mode (`thread` \| `process`) |
| `FLOWFRAME_RUN_TIMEOUT_SECONDS` | `0` | Abandon a run after N seconds (`0` = no limit) |
| `FLOWFRAME_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins (JSON list) |
| `FLOWFRAME_MAX_UPLOAD_SIZE_MB` | `100` | Maximum upload size in MB |
| `FLOWFRAME_SCHEDULER_ENABLED` | `true` | Run the background scheduler |
| `FLOWFRAME_SCHEDULER_POLL_INTERVAL_SECONDS` | `30` | How often the scheduler polls for due runs |
| `FLOWFRAME_SCHEDULER_MAX_CONCURRENT_RUNS` | `1` | Max simultaneous scheduled runs |
| `FLOWFRAME_SCHEDULER_MAX_CONSECUTIVE_FAILURES` | `5` | Failures before a schedule auto-disables (`0` = never) |

Booleans accept `true`/`false`; lists (like `CORS_ORIGINS`) are JSON.

## Database

FlowFrame uses **async SQLAlchemy**, so the URL must use an async driver.

| Database | URL form | Driver to install |
|---|---|---|
| SQLite (default) | `sqlite+aiosqlite:///./flowframe.db` | bundled |
| PostgreSQL | `postgresql+asyncpg://user:pass@host:5432/dbname` | `pip install asyncpg` |
| MySQL / MariaDB | `mysql+aiomysql://user:pass@host:3306/dbname` | `pip install aiomysql` |

```bash
# backend/.env
FLOWFRAME_DATABASE_URL=postgresql+asyncpg://flowframe:secret@localhost:5432/flowframe
```

The schema is **created automatically** on startup — there is no separate
migration step. `flowframe check` verifies the driver is async and that the
database is reachable.

:::warning Async driver required
A plain `sqlite://`, `postgresql://`, or `mysql://` URL will fail to connect.
Always use the `+aiosqlite` / `+asyncpg` / `+aiomysql` variant.
:::

## Data directory

`FLOWFRAME_DATA_DIR` (default `.data`) is where uploaded files, run outputs, and
previews are written. In production, point it at a persistent, writable volume —
`flowframe check` confirms it's writable. The database stores metadata; the data
dir stores the actual files.

## Execution tuning

FlowFrame runs synchronous dataframe work off the event loop so the API stays
responsive. See [Engines](/guide/engines) for the full picture.

- **`FLOWFRAME_EXECUTION_MODE=thread`** (default) — a worker thread; simplest.
- **`FLOWFRAME_EXECUTION_MODE=process`** — a `ProcessPoolExecutor` for true
  multi-core parallelism. Only picklable arguments cross the process boundary, so
  the database session always stays in the parent process.

- **`FLOWFRAME_RUN_TIMEOUT_SECONDS`** abandons an over-running run. In `process`
  mode the worker is recycled to reclaim the CPU; in `thread` mode the run is
  abandoned but the thread finishes. `0` disables the limit.

```bash
flowframe serve --execution-mode process
# with a 5-minute cap per run:
FLOWFRAME_RUN_TIMEOUT_SECONDS=300 flowframe serve --execution-mode process
```

## Scheduler tuning

The background scheduler runs inside the API process. See
[Scheduling](/guide/scheduling) for behavior. Relevant settings:

- `FLOWFRAME_SCHEDULER_ENABLED` — master switch (or `flowframe serve --no-scheduler`).
- `FLOWFRAME_SCHEDULER_POLL_INTERVAL_SECONDS` — lower = more responsive, more wakeups.
- `FLOWFRAME_SCHEDULER_MAX_CONCURRENT_RUNS` — cap on simultaneous scheduled runs.
- `FLOWFRAME_SCHEDULER_MAX_CONSECUTIVE_FAILURES` — auto-disable threshold.

:::tip Run the API without the scheduler
If you run multiple API replicas, enable the scheduler on **only one** of them
(`--no-scheduler` on the rest) — it is a single-process poller and isn't designed
to coordinate across replicas.
:::

## CORS

When the frontend is served from a different origin than the API, add that origin
to `FLOWFRAME_CORS_ORIGINS` (a JSON list):

```bash
FLOWFRAME_CORS_ORIGINS=["https://flowframe.example.com","http://localhost:5173"]
```

## Production deployment

FlowFrame is local-first, but you can host it. A typical setup:

### Backend

```bash
pip install -e .
# bind to all interfaces, no reload, info logs
flowframe serve --host 0.0.0.0 --port 8000 --log-level info
```

- Set `FLOWFRAME_ENVIRONMENT=production`.
- Use a managed PostgreSQL/MySQL via `FLOWFRAME_DATABASE_URL`.
- Put the data dir on a persistent volume.
- Run it under a process manager (systemd, Docker, etc.).

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
  server_name flowframe.example.com;

  root /srv/flowframe/dist;            # frontend build
  location / { try_files $uri /index.html; }

  location /api/ {                      # proxy to the backend
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
}
```

Because the browser then talks to a single origin, you usually don't need to
touch `CORS_ORIGINS` for this layout.

::: warning Alpha software
FlowFrame is in early development with no stability guarantee. If you deploy it,
treat it as experimental, review the [security notes](https://github.com/rodrigo-arenas/FlowFrame/blob/main/SECURITY.md),
and don't expose it to untrusted users or place mission-critical pipelines on it.
:::

### Frontend dev overrides

For local development against a non-default backend, the dev server (not the
production build) honors:

- `VITE_PORT` — change the dev server port (default `5173`).
- `VITE_API_TARGET` — where the dev proxy forwards `/api` (default
  `http://localhost:8000`).

```bash
VITE_PORT=3000 VITE_API_TARGET=http://localhost:8001 npm run dev
```

## Verifying

```bash
flowframe info     # print resolved settings (DB password redacted)
flowframe check    # data dir writable? async driver? DB reachable? engines present?
```

## See also

- [CLI Reference](/guide/cli) — every command and flag
- [Engines](/guide/engines) — polars/pandas, execution mode, timeouts
- [Scheduling](/guide/scheduling) — the background scheduler
- [Installation](/guide/installation) — the basic setup
