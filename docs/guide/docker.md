---
title: Docker
description: Run FlowFrame with Docker — single-command setup, optional ML and database extras
search: docker container compose deployment
layout: doc
---

# Docker

FlowFrame ships a multi-stage Docker image that bundles the React frontend and
the FastAPI backend into a single container. You get one port, one volume for
data persistence, and zero Node.js or Python tooling required on the host.

## Prerequisites

- [Docker Desktop](https://docs.docker.com/get-docker/) 24+ (or Docker Engine
  - Docker Compose v2)
- No other dependencies — the image includes Python 3.13, all backend packages,
  and the pre-built frontend

## Quick start

```bash
# clone the repo (or download the Dockerfile + docker-compose.yml)
git clone https://github.com/rodrigo-arenas/FlowFrame.git
cd FlowFrame

# build and start (SQLite, no extras — takes ~3 min on first build)
docker compose up --build
```

Open [http://localhost:8055](http://localhost:8055).

:::info First start
On the first run the entrypoint applies any pending database migrations before
the server starts, so the initial boot takes a few extra seconds.
:::

## Image layout

| Path inside container | Purpose |
| ----------------------- | --------- |
| `/app/` | FlowFrame source + virtual environment (`/app/.venv/`) |
| `/app/app/web/` | Built React frontend (served by FastAPI at runtime) |
| `/data/` | **Persistent volume** — SQLite DB, uploads, run outputs, MLflow |

The `/data` volume is the only path that changes at runtime. Mount it as a
named volume (default) or a bind-mount to control where data lives on the host.

## Configuration

Every `FLOWFRAME_*` setting can be passed as an environment variable. The
`docker-compose.yml` already wires the most common ones through shell variables
with sensible defaults, so you can override without editing the file:

```bash
# examples — pass on the command line
FLOWFRAME_DEFAULT_ENGINE=pandas docker compose up
FLOWFRAME_MAX_UPLOAD_SIZE_MB=500 docker compose up
FLOWFRAME_SCHEDULER_ENABLED=false docker compose up
```

Or create a `.env` file next to `docker-compose.yml`:

```bash
# .env  (never commit this file)
FLOWFRAME_MAX_UPLOAD_SIZE_MB=500
FLOWFRAME_DEFAULT_ENGINE=pandas
FLOWFRAME_EXECUTION_MODE=process
FLOWFRAME_SCHEDULER_MAX_CONCURRENT_RUNS=3
FLOWFRAME_RUN_TIMEOUT_SECONDS=300
```

See `flowframe info` (below) for the full list of resolved settings, or
`docs/guide/cli.md` for a description of every variable.

## Optional feature extras

Extras are installed at **build time** via the `EXTRAS` build argument. Pass a
comma-separated list:

| Extra | Adds |
| ------- | ------ |
| `ml` | scikit-learn, XGBoost, LightGBM, MLflow — enables ML nodes |
| `postgres` | asyncpg + psycopg — PostgreSQL support |
| `mysql` | pymysql — MySQL support |
| `mongo` | pymongo — MongoDB support |
| `mssql` | pyodbc — MSSQL support *(also needs `unixodbc` system pkg)* |
| `all-connectors` | postgres + mysql + mongo (no mssql) |

```bash
# ML support
EXTRAS=ml docker compose build && docker compose up

# PostgreSQL connector
EXTRAS=postgres docker compose build && docker compose up

# Both
EXTRAS=ml,postgres docker compose build && docker compose up
```

:::warning Rebuild required
Changing `EXTRAS` requires a rebuild (`docker compose build`). The extra
packages are baked into the image layer, not installed at runtime.
:::

## Changing the port

```bash
FLOWFRAME_PORT=9000 docker compose up
```

Or override directly:

```bash
docker run -p 9000:8055 flowframe:latest
```

## Data persistence

By default `docker-compose.yml` uses a named Docker volume (`flowframe-data`).
All uploads, run outputs, the SQLite database, and MLflow run data live there.

To use a **bind mount** instead (easier to inspect/backup):

```yaml
# docker-compose.override.yml
services:
  flowframe:
    volumes:
      - ./my-flowframe-data:/data
```

## Using PostgreSQL

1. Rebuild with the `postgres` extra:

   ```bash
   EXTRAS=postgres docker compose build
   ```

2. Set the database URL at runtime:

   ```bash
   FLOWFRAME_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/flowframe \
     docker compose up
   ```

   Or add it to your `.env` file.

:::tip
The database URL must use an **async driver**: `postgresql+asyncpg://`,
`mysql+aiomysql://`, or `sqlite+aiosqlite://`. Plain `postgresql://` will fail.
:::

## Running CLI commands inside the container

```bash
# inspect resolved settings
docker compose exec flowframe flowframe info

# validate the environment (data dir, database, engines, ML)
docker compose exec flowframe flowframe check

# check the current migration revision
docker compose exec flowframe flowframe db current

# list available transformation node types
docker compose exec flowframe flowframe transformations list
```

For a one-off container (no Compose):

```bash
docker run --rm \
  -e FLOWFRAME_DATABASE_URL=sqlite+aiosqlite:////data/flowframe.db \
  -v flowframe-data:/data \
  --entrypoint flowframe \
  flowframe:latest info
```

## Building the image manually

```bash
# base image (SQLite + polars + pandas)
docker build -t flowframe:latest .

# with ML extras
docker build --build-arg EXTRAS=ml -t flowframe:ml .

# with multiple extras
docker build --build-arg EXTRAS=ml,postgres -t flowframe:full .
```

## Production checklist

- **Set `FLOWFRAME_ENVIRONMENT=production`** — already the default in
  `docker-compose.yml`; disables debug output and the `db reset` guard.
- **Mount `/data` as a named volume or bind-mount** — so data survives
  container replacement.
- **Set `FLOWFRAME_CORS_ORIGINS`** if your frontend and API are on different
  origins (unnecessary when both are served from the same port).
- **Pin the image tag** — use `flowframe:v0.1.0` rather than `latest` in
  production compose files.
- **Run behind a reverse proxy** (nginx, Caddy, Traefik) for TLS and
  compression. The image does not include TLS termination.
- **Back up `/data`** regularly — it contains the database and all uploaded
  files.

## Image size notes

The image is built in two stages so no Node.js, npm, or build tooling ends up
in the final layer:

- **Stage 1** (`node:20-alpine`): builds the React frontend → ~200 MB, discarded
- **Stage 2** (`python:3.13-slim`): runtime only → ~350 MB base, ~600 MB with ML extras

To further reduce size, avoid installing extras you don't need. The `ml` extra
alone adds ~250 MB of ML libraries.

## Troubleshooting

### Container exits immediately

```bash
docker logs <container-id>
```

Common causes: the `/data` directory isn't writable, or `DATABASE_URL` uses a
sync driver. Check with `flowframe check` before starting.

### Health check fails

The health check at `/health` is polled every 30 seconds with a 60-second
start period. If the server takes longer to start (e.g. due to a large
migration), increase `start_period` in `docker-compose.yml`.

### ML nodes not visible

ML nodes only appear when `FLOWFRAME_ML_ENABLED=true` **and** the `[ml]` extra
was installed at build time. Verify with:

```bash
docker compose exec flowframe flowframe check
```

A `[warn] ml: ML_ENABLED but [ml] extra not installed` line means you need to
rebuild with `EXTRAS=ml`.

### Port already in use

```bash
FLOWFRAME_PORT=9001 docker compose up
```

## See also

- [CLI Reference](./cli.md) — all `flowframe` sub-commands and flags
- [Advanced Setup](./advanced-setup.md) — environment variables, database config
- [CI/CD Pipeline](../CI_CD.md) — how Docker builds are tested in GitHub Actions
