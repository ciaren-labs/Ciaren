# syntax=docker/dockerfile:1

# ─── Stage 1: Build the frontend ─────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ─── Stage 2: Runtime image ───────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="Ciaren" \
      org.opencontainers.image.description="Visual ETL builder — local-first, dataframe-based" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

# Install uv from its official distroless image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Optional extras to install at build time (comma-separated).
# Examples:  ml  |  postgres  |  ml,postgres  |  all-connectors
# Note: mssql also pulls in the unixODBC driver manager and Microsoft's
# msodbcsql18 driver (see the RUN block below) — building with it accepts
# Microsoft's ODBC Driver for SQL Server EULA on your behalf.
ARG EXTRAS=""

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# xgboost / lightgbm (the ml extra) link against the GNU OpenMP runtime. pyodbc
# (the mssql extra) needs unixODBC. Install only when those extras are requested.
RUN packages=""; \
    if echo "$EXTRAS" | tr ',' ' ' | grep -qw ml; then packages="$packages libgomp1"; fi; \
    if echo "$EXTRAS" | tr ',' ' ' | grep -Eqw 'mssql|all-connectors|all'; then packages="$packages unixodbc"; fi; \
    if [ -n "$packages" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends $packages && \
        rm -rf /var/lib/apt/lists/*; \
    fi

# unixODBC above is only the driver *manager* — pyodbc still needs an actual SQL
# Server ODBC driver registered with it, or every mssql connection fails at
# connect time with "no default driver specified". Microsoft ships msodbcsql18
# only through its own EULA-gated apt repo (ACCEPT_EULA=Y accepts it here on
# your behalf — this block only runs when EXTRAS opts into mssql support).
# Pinned to the bookworm (Debian 12) repo rather than this image's own Debian
# release: Microsoft's per-release repos for newer Debian versions (e.g.
# trixie/13, which this base image now uses) have had broken/lagging repo
# signing, while the bookworm package installs and runs fine on newer bases.
RUN if echo "$EXTRAS" | tr ',' ' ' | grep -Eqw 'mssql|all-connectors|all'; then \
        apt-get update && \
        apt-get install -y --no-install-recommends curl gnupg && \
        curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
        curl -sSL https://packages.microsoft.com/config/debian/12/prod.list -o /etc/apt/sources.list.d/mssql-release.list && \
        apt-get update && \
        ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 && \
        apt-get purge -y --auto-remove curl gnupg && \
        rm -rf /var/lib/apt/lists/*; \
    fi

# ── Install Python dependencies (layer cached until lockfile changes) ──────────
# hatch_build.py and hatch_metadata.py are referenced by the wheel build hook and
# the custom metadata hook in pyproject.toml; hatchling loads both when the
# project is installed below (even in editable mode), so they must be present
# in the build context. The metadata hook reads the repo-root README relative
# to its project root's *parent* (mirroring backend/'s position under the repo
# root); since this image flattens pyproject.toml straight into /app, that
# resolves to /README.md, so it's copied there too.
COPY backend/pyproject.toml backend/uv.lock backend/hatch_build.py backend/hatch_metadata.py ./
COPY README.md /README.md

RUN --mount=type=cache,target=/root/.cache/uv \
    extra_flags=""; \
    for e in $(echo "$EXTRAS" | tr ',' ' '); do \
        [ -n "$e" ] && extra_flags="$extra_flags --extra $e"; \
    done; \
    uv sync --frozen --no-dev --no-install-project $extra_flags

# ── Copy application source ───────────────────────────────────────────────────
COPY backend/app ./app

# Built frontend — main.py auto-discovers app/web/index.html (no env var needed)
COPY --from=frontend-builder /build/dist ./app/web

# Install the project itself into the venv.
# Uses editable mode by default; the wheel build hook (hatch_build.py) does not
# run for editable installs, so no npm is needed here.
RUN --mount=type=cache,target=/root/.cache/uv \
    extra_flags=""; \
    for e in $(echo "$EXTRAS" | tr ',' ' '); do \
        [ -n "$e" ] && extra_flags="$extra_flags --extra $e"; \
    done; \
    uv sync --frozen --no-dev $extra_flags

# ── Startup script: apply migrations then start the server ────────────────────
# The server binds 0.0.0.0 so the container is reachable. The API is
# unauthenticated by default and can execute code (pythonTransform, plugin
# install), so set CIAREN_API_TOKEN (and/or front it with an authenticating
# reverse proxy) before exposing this container beyond a trusted host. The CLI
# prints a warning at startup when it binds wide with no token. See SECURITY.md.
RUN printf '#!/bin/sh\nset -e\nciaren db upgrade\nexec ciaren serve --host 0.0.0.0 "$@"\n' \
    > /usr/local/bin/entrypoint.sh && \
    chmod +x /usr/local/bin/entrypoint.sh

# ── Security: drop to a non-root user ────────────────────────────────────────
RUN groupadd --system ciaren && \
    useradd --system --gid ciaren --no-create-home ciaren && \
    mkdir -p /data && \
    chown -R ciaren:ciaren /app /data

USER ciaren

# ── Port & persistent-data volume ─────────────────────────────────────────────
EXPOSE 8055
VOLUME ["/data"]

# ── Runtime defaults — all overridable via -e / --env-file ───────────────────
# DATA_DIR, DATABASE_URL, and MLFLOW_TRACKING_URI all live inside the /data
# volume so they survive restarts. Settings.MLFLOW_TRACKING_URI defaults to the
# relative "./mlruns", which would resolve against WORKDIR (/app) — outside the
# volume — if left unset here, so it's pinned explicitly like the other two.
# CIAREN_CORS_ORIGINS is unset; same-origin serving (frontend + API on 8055)
# needs no CORS config. Set it if you expose the API to other origins.
ENV CIAREN_DATA_DIR=/data \
    CIAREN_DATABASE_URL=sqlite+aiosqlite:////data/ciaren.db \
    CIAREN_MLFLOW_TRACKING_URI=/data/mlruns \
    CIAREN_ENVIRONMENT=production \
    PATH="/app/.venv/bin:$PATH"

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8055/health')"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD []
