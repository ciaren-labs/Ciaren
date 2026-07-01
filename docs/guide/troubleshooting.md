---
title: Troubleshooting Guide
description: Common issues and how to solve them
search: troubleshooting help issues database cors port
---

# Troubleshooting Guide

Common issues when running Ciaren. For broader questions, see the [FAQ](/faq).

:::tip
Run `ciaren check` to validate your environment in one shot — it reports a
non-writable data dir, a non-async database URL, an unreachable database, and the
available engines.
:::

## Database connection fails

Ciaren uses async SQLAlchemy. A plain `sqlite://`, `postgresql://`, or
`mysql://` URL will not connect. Use the async variant in
`CIAREN_DATABASE_URL`:

- `sqlite+aiosqlite:///./ciaren.db` (default)
- `postgresql+asyncpg://user:pass@host/db`
- `mysql+aiomysql://user:pass@host/db`

Install the matching driver (`asyncpg`, `aiomysql`) for non-SQLite databases.
The schema is created automatically on startup, so there is no migration step.

## "Port 8055 already in use"

Start the server on another port:

```bash
ciaren serve --port 8001
```

## Frontend can't reach the backend

The dev server proxies `/api` to `http://localhost:8055` by default. If your
backend runs elsewhere, point the proxy at it:

```bash
VITE_API_TARGET=http://localhost:8001 npm run dev
```

If the frontend port `5173` is taken, change it with `VITE_PORT=3000 npm run dev`
— and remember to add the new origin to `CIAREN_CORS_ORIGINS`.

## A scheduled flow stopped running

A schedule is **auto-disabled** after several consecutive failed runs (default 5),
with a `disabled_reason`. Re-enable it to clear the streak. Manual *run-now* stays
out of the retry/auto-disable machinery. See [Scheduling](/guide/scheduling).

## CORS errors

Add the calling origin to `CIAREN_CORS_ORIGINS` (a JSON list) in
`backend/.env`:

```
CIAREN_CORS_ORIGINS=["http://localhost:5173"]
```

## Upload rejected as too large

The default upload limit is 100 MB. Raise it with
`CIAREN_MAX_UPLOAD_SIZE_MB` in `backend/.env`.

## Module not found errors

Reinstall the backend in editable mode from a clean virtual environment:

```bash
cd backend
rm -rf .venv
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e .
```

## Still stuck?

- [Installation Guide](/guide/installation)
- [FAQ](/faq)
- [GitHub Issues](https://github.com/ciaren/ciaren/issues)
