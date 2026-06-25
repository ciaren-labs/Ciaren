# syntax=docker/dockerfile:1

# ─── Stage 1: Build the frontend ─────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ─── Stage 2: Runtime image ───────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="FlowFrame" \
      org.opencontainers.image.description="Visual ETL builder — local-first, dataframe-based" \
      org.opencontainers.image.licenses="Apache-2.0"

# Install uv from its official distroless image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Optional extras to install at build time (comma-separated).
# Examples:  ml  |  postgres  |  ml,postgres  |  all-connectors
# Note: mssql also requires the unixodbc system package.
ARG EXTRAS=""

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# ── Install Python dependencies (layer cached until lockfile changes) ──────────
# hatch_build.py is referenced by the wheel build hook in pyproject.toml;
# hatchling loads it when the project is installed below (even in editable mode),
# so it must be present in the build context.
COPY backend/pyproject.toml backend/uv.lock backend/hatch_build.py ./

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
RUN printf '#!/bin/sh\nset -e\nflowframe db upgrade\nexec flowframe serve --host 0.0.0.0 "$@"\n' \
    > /usr/local/bin/entrypoint.sh && \
    chmod +x /usr/local/bin/entrypoint.sh

# ── Security: drop to a non-root user ────────────────────────────────────────
RUN groupadd --system flowframe && \
    useradd --system --gid flowframe --no-create-home flowframe && \
    mkdir -p /data && \
    chown -R flowframe:flowframe /app /data

USER flowframe

# ── Port & persistent-data volume ─────────────────────────────────────────────
EXPOSE 8055
VOLUME ["/data"]

# ── Runtime defaults — all overridable via -e / --env-file ───────────────────
# DATA_DIR and DATABASE_URL live inside the /data volume so they survive restarts.
# FLOWFRAME_CORS_ORIGINS is unset; same-origin serving (frontend + API on 8055)
# needs no CORS config. Set it if you expose the API to other origins.
ENV FLOWFRAME_DATA_DIR=/data \
    FLOWFRAME_DATABASE_URL=sqlite+aiosqlite:////data/flowframe.db \
    FLOWFRAME_ENVIRONMENT=production \
    PATH="/app/.venv/bin:$PATH"

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8055/health')"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD []
