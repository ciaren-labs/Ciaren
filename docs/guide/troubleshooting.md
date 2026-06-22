---
title: Troubleshooting Guide
description: Common issues and how to solve them
search: troubleshooting help issues database cors port
---

# Troubleshooting Guide

Common issues when running the FlowFrame backend. For broader questions, see the
[FAQ](/faq).

## Database connection fails

FlowFrame uses async SQLAlchemy. A plain `sqlite://`, `postgresql://`, or
`mysql://` URL will not connect. Use the async variant in
`FLOWFRAME_DATABASE_URL`:

- `sqlite+aiosqlite:///./flowframe.db` (default)
- `postgresql+asyncpg://user:pass@host/db`
- `mysql+aiomysql://user:pass@host/db`

Install the matching driver (`asyncpg`, `aiomysql`) for non-SQLite databases.
The schema is created automatically on startup, so there is no migration step.

## "Port 8000 already in use"

Start the server on another port:

```bash
uvicorn app.main:app --reload --port 8001
```

## CORS errors

Add the calling origin to `FLOWFRAME_CORS_ORIGINS` (a JSON list) in
`backend/.env`:

```
FLOWFRAME_CORS_ORIGINS=["http://localhost:5173"]
```

## Upload rejected as too large

The default upload limit is 100 MB. Raise it with
`FLOWFRAME_MAX_UPLOAD_SIZE_MB` in `backend/.env`.

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
- [GitHub Issues](https://github.com/rodrigo-arenas/FlowFrame/issues)
