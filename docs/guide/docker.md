---
title: Docker
description: Run Ciaren with Docker — single-command setup, built-in ML, optional database extras
search: docker container compose deployment
layout: doc
---

# Docker

Ciaren ships a multi-stage Docker image that bundles the React frontend and
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
git clone https://github.com/ciaren-labs/Ciaren.git
cd Ciaren

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
| `/app/` | Ciaren source + virtual environment (`/app/.venv/`) |
| `/app/app/web/` | Built React frontend (served by FastAPI at runtime) |
| `/data/` | **Persistent volume** — SQLite DB, uploads, run outputs, MLflow |

The `/data` volume is the only path that changes at runtime. Mount it as a
named volume (default) or a bind-mount to control where data lives on the host.

:::warning Keep MLflow data inside /data
The image sets `CIAREN_MLFLOW_TRACKING_URI=/data/mlruns` by default so trained
models and run history survive container recreation. If you override this
variable, use an **absolute path under `/data`** (or a remote tracking server
URI) — a relative path resolves against the container's working directory
(`/app`), which is *not* part of the `/data` volume and is discarded the next
time the container is recreated.
:::

## Configuration

Every `CIAREN_*` setting can be passed as an environment variable. The
`docker-compose.yml` already wires the most common ones through shell variables
with sensible defaults, so you can override without editing the file:

```bash
# examples — pass on the command line
CIAREN_DEFAULT_ENGINE=pandas docker compose up
CIAREN_MAX_UPLOAD_SIZE_MB=500 docker compose up
CIAREN_SCHEDULER_ENABLED=false docker compose up
```

Or create a `.env` file next to `docker-compose.yml`:

```bash
# .env  (never commit this file)
CIAREN_MAX_UPLOAD_SIZE_MB=500
CIAREN_DEFAULT_ENGINE=pandas
CIAREN_EXECUTION_MODE=process
CIAREN_SCHEDULER_MAX_CONCURRENT_RUNS=3
CIAREN_RUN_TIMEOUT_SECONDS=300
```

See `ciaren info` (below) for the full list of resolved settings, or
`docs/guide/cli.md` for a description of every variable.

## Optional feature extras

Extras are installed at **build time** via the `EXTRAS` build argument. Pass a
comma-separated list:

scikit-learn, MLflow, and joblib ship in every image — the ML nodes work with
no extra. `EXTRAS` only adds:

| Extra | Adds |
| ------- | ------ |
| `ml` | XGBoost, LightGBM — extra gradient-boosting model choices |
| `postgres` | asyncpg + psycopg — PostgreSQL support |
| `mysql` | pymysql — MySQL SQL-node connector support |
| `mongo` | pymongo — MongoDB support |
| `mssql` | pyodbc — MSSQL support *(also installs the `unixodbc` driver manager and Microsoft's `msodbcsql18` driver)* |
| `all-connectors` | postgres + mysql + mongo + s3 + gcs + azure + mssql + duckdb + snowflake |

```bash
# XGBoost + LightGBM model choices
EXTRAS=ml docker compose build && docker compose up

# PostgreSQL connector
EXTRAS=postgres docker compose build && docker compose up

# Both
EXTRAS=ml,postgres docker compose build && docker compose up
```

:::info mssql and the Microsoft EULA
Building with `EXTRAS=mssql` (or `all-connectors`/`all`) pulls Microsoft's
`msodbcsql18` package from Microsoft's own apt repository and passes
`ACCEPT_EULA=Y` to accept the [ODBC Driver for SQL Server license
terms](https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
on your behalf during the build. Without it, `pyodbc` has a driver *manager*
(`unixodbc`) but no actual driver, so every SQL Server connection fails with
"Data source name not found and no default driver specified."
:::

:::warning Rebuild required
Changing `EXTRAS` requires a rebuild (`docker compose build`). The extra
packages are baked into the image layer, not installed at runtime.
:::

## Changing the port

```bash
CIAREN_PORT=9000 docker compose up
```

Or override directly:

```bash
docker run -p 9000:8055 ciaren:latest
```

## Data persistence

By default `docker-compose.yml` uses a named Docker volume (`ciaren-data`).
All uploads, run outputs, the SQLite database, and MLflow run data live there.

To use a **bind mount** instead (easier to inspect/backup):

```yaml
# docker-compose.override.yml
services:
  ciaren:
    volumes:
      - ./my-ciaren-data:/data
```

## Using PostgreSQL

1. Rebuild with the `postgres` extra:

   ```bash
   EXTRAS=postgres docker compose build
   ```

2. Set the database URL at runtime:

   ```bash
   CIAREN_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/ciaren \
     docker compose up
   ```

   Or add it to your `.env` file.

:::tip
The database URL must use an **async driver**: `postgresql+asyncpg://`,
`mysql+aiomysql://`, or `sqlite+aiosqlite://`. Plain `postgresql://` will fail.
The `postgres` extra includes the app database driver (`asyncpg`); the `mysql`
extra is for SQL-node connectors and does not add `aiomysql` to the image.
:::

## Running CLI commands inside the container

```bash
# inspect resolved settings
docker compose exec ciaren ciaren info

# validate the environment (data dir, database, engines, ML)
docker compose exec ciaren ciaren check

# check the current migration revision
docker compose exec ciaren ciaren db current

# list available transformation node types
docker compose exec ciaren ciaren transformations list
```

For a one-off container (no Compose):

```bash
docker run --rm \
  -e CIAREN_DATABASE_URL=sqlite+aiosqlite:////data/ciaren.db \
  -v ciaren-data:/data \
  --entrypoint ciaren \
  ciaren:latest info
```

## Building the image manually

```bash
# base image (SQLite + polars + pandas + built-in ML)
docker build -t ciaren:latest .

# with XGBoost + LightGBM
docker build --build-arg EXTRAS=ml -t ciaren:ml .

# with multiple extras
docker build --build-arg EXTRAS=ml,postgres -t ciaren:full .
```

## Production checklist

- **Set `CIAREN_ENVIRONMENT=production`** — already the default in
  `docker-compose.yml`; disables debug output and activates the `db reset`
  guard (`ciaren db reset` then refuses to run unless `--force` is also passed).
- **Mount `/data` as a named volume or bind-mount** — so data survives
  container replacement.
- **Set `CIAREN_CORS_ORIGINS`** if your frontend and API are on different
  origins (unnecessary when both are served from the same port).
- **Pin the image tag** — use `ciaren:v0.1.0-alpha.1` rather than `latest` in
  production compose files.
- **Run behind a reverse proxy** (nginx, Caddy, Traefik) for TLS and
  compression. The image does not include TLS termination.
- **Back up `/data`** regularly — it contains the database and all uploaded
  files.

## Image size notes

The image is built in two stages so no Node.js, npm, or build tooling ends up
in the final layer:

- **Stage 1** (`node:22-alpine`): builds the React frontend → ~200 MB, discarded
- **Stage 2** (`python:3.13-slim`): runtime only, now includes scikit-learn,
  MLflow, and joblib in the base image

To further reduce size, avoid installing extras you don't need. The `ml` extra
now only adds XGBoost and LightGBM, so its footprint is smaller than before —
the base image itself is correspondingly larger since core ML libraries moved
into it.

## Troubleshooting

### Container exits immediately

```bash
docker logs <container-id>
```

Common causes: the `/data` directory isn't writable, or `DATABASE_URL` uses a
sync driver. Check with `ciaren check` before starting.

### Health check fails

The container health check polls `/health` (liveness) every 30 seconds with a
60-second start period. If the server takes longer to start (e.g. due to a large
migration), increase `start_period` in `docker-compose.yml`.

For orchestrators (Kubernetes, a load balancer) use `/ready` as the **readiness**
probe: it returns `503` until the database is reachable, so traffic is only
routed once the instance can actually serve it. Keep `/health` as the liveness
probe so a hung process is restarted without being masked by a transient DB blip.

### ML nodes not visible

The base image already includes scikit-learn, MLflow, and joblib, so the ML
nodes only go missing if `CIAREN_ML_ENABLED=false` — or the image is somehow
broken/stripped-down. XGBoost/LightGBM model *choices* specifically need the
`ml` extra baked in at build time. Verify with:

```bash
docker compose exec ciaren ciaren check
```

A `[warn] ml: ...` line means either `CIAREN_ML_ENABLED` is off, or the image
wasn't built normally — rebuild without a custom `--no-deps`-style override.
Missing XGBoost/LightGBM specifically means rebuild with `EXTRAS=ml`.

### Trained models / MLflow run history disappeared after a redeploy

`CIAREN_MLFLOW_TRACKING_URI` must point somewhere inside the `/data` volume
(the default, `/data/mlruns`, already does). If it was overridden to a relative
path or a path outside `/data`, MLflow wrote into the container's writable
layer instead of the volume, and that layer is gone once the container is
recreated. Set it back to an absolute `/data/...` path (or point it at an
external MLflow tracking server) and re-train.

### SQL Server connection fails with "no default driver specified"

The image only ships the `msodbcsql18` driver when built with `EXTRAS=mssql`
(or `all-connectors`/`all`) — `unixodbc` alone is just the driver manager, with
nothing registered in it. Rebuild with the extra:

```bash
EXTRAS=mssql docker compose build && docker compose up
```

### Port already in use

```bash
CIAREN_PORT=9001 docker compose up
```

## See also

- [CLI Reference](./cli.md) — all `ciaren` sub-commands and flags
- [Advanced Setup](./advanced-setup.md) — environment variables, database config
