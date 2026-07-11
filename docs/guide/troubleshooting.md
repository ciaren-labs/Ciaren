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

If API auth is enabled, browser clients can send either
`Authorization: Bearer <token>` or `X-Ciaren-Token: <token>`; both are allowed by
the API's CORS preflight handling.

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
python -m pip install --pre ciaren
```

If you are working from a source checkout, reinstall the local package instead:
`pip install -e .` from the `backend/` directory.

## Install fails on Windows with a long-path error

A `pip install` can fail on Windows with an error like
`OSError: [Errno 2] No such file or directory: '...\mlflow\store\db_migrations\versions\...'`
and a hint about enabling *long-path support*. Ciaren bundles MLflow, whose
internal file paths are long, so installing into a deeply nested folder can push
the full path past Windows' legacy 260-character limit.

Fix it either way:

- **Enable long paths (recommended, one-time).** In an Administrator PowerShell:

  ```powershell
  Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' LongPathsEnabled 1
  ```

  Reopen your terminal, then reinstall. See the
  [pip long-paths note](https://pip.pypa.io/warnings/enable-long-paths).
- **Or install into a shorter path** — create the virtual environment close to
  the drive root (for example `C:\ciaren\.venv`) instead of a deeply nested
  directory.

## ML training succeeds but the model isn't tracked (Windows)

A training run finishes **green**, its metrics show up, but the node's **model
URI** and **MLflow run id** are blank — and a downstream **Predict** or **Feature
Importance** node then fails because there's no model to load. The server log
shows a warning like:

```
mlTrainClassifier: MLflow logging failed ([WinError 206] The filename or extension
is too long: '...\mlruns\...\models\...') — model trained but not tracked.
```

This is the same Windows 260-character path limit as the install error above, but
at **run time**: MLflow writes artifacts under your tracking directory
(`CIAREN_MLFLOW_TRACKING_URI`, default `./mlruns` inside the working directory),
and its nested `mlruns/<exp>/<run>/models/...` layout can push the full path over
the limit when Ciaren runs from a deeply nested folder. Training itself is
in-memory, so it still succeeds — only the logging step fails, which is why the
run is green but untracked.

Fix it either way:

- **Enable long paths** (recommended, one-time) — the same
  `LongPathsEnabled` registry setting shown in the install section above.
- **Point the tracking store somewhere short** — set an absolute, shallow
  `CIAREN_MLFLOW_TRACKING_URI` (for example `CIAREN_MLFLOW_TRACKING_URI=C:\mlruns`),
  or run Ciaren from a directory close to the drive root. You can also edit the
  **Local MLflow** connection's Tracking URI in the **Connections** page.

## Still stuck?

- [Installation Guide](/guide/installation)
- [FAQ](/faq)
- [GitHub Issues](https://github.com/ciaren-labs/Ciaren/issues)
