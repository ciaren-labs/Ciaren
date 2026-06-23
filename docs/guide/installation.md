---
title: Installation
description: Install and run FlowFrame locally in minutes
search: install setup download run requirements frontend backend
---

# Installation Guide

Get FlowFrame running on your machine in a few minutes. FlowFrame has two parts:

- a **backend** (FastAPI + the execution engine and scheduler), and
- a **frontend** (the React visual editor).

You can run the backend on its own and drive it through the
[REST API](/api/rest-api), or run both for the full visual experience.

## Requirements

- **Python 3.12+** — [Download Python](https://www.python.org/downloads/)
- **Node.js 18+** — [Download Node.js](https://nodejs.org/) (only for the frontend)
- **Git** — [Download Git](https://git-scm.com/)
- A database is **optional**: SQLite is the zero-setup default. PostgreSQL / MySQL
  are supported via an async driver.

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/rodrigo-arenas/FlowFrame.git
cd FlowFrame
```

### 2. Start the backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows (PowerShell)

# Install FlowFrame (exposes the `flowframe` command)
pip install -e .

# Run the API + background scheduler in one process
flowframe serve
```

The backend runs on `http://localhost:8055`. The database schema is **created
automatically** on first start — there is no migration step. Open the interactive
API docs at `http://localhost:8055/docs`.

:::tip Database connectors are optional
The core install stays lightweight. To connect to external databases, install the
matching driver as an extra — e.g. `pip install -e ".[mysql]"`, or grab them all
with `pip install -e ".[all]"`. See [Connections](/guide/connections) for the
full list.
:::

:::tip flowframe serve vs. uvicorn
`flowframe serve` is the recommended entry point — it boots the API and the
background scheduler together. It accepts flags like `--port`, `--reload`,
`--db-url`, `--engine`, and `--no-scheduler`. See the
[CLI reference](/guide/cli) for all of them. (Under the hood it runs the same
`app.main:app` ASGI app, so `uvicorn app.main:app --reload` still works if you
prefer.)
:::

### 3. Start the frontend (visual editor)

In a second terminal:

```bash
cd frontend

npm install
npm run dev
```

The editor runs on `http://localhost:5173` and proxies `/api` calls to the
backend on port `8055`.

### 4. Open in your browser

Visit `http://localhost:5173` and start building flows.

## Detailed Setup

### Backend with `uv` (faster)

[`uv`](https://docs.astral.sh/uv/) is a fast Python package manager:

```bash
cd backend
uv sync                       # install dependencies
uv run flowframe serve        # run the server
```

For development dependencies (tests, linting, type-checking):

```bash
uv sync --all-groups
# or with pip:
pip install -e .[dev]
```

### Frontend scripts

```bash
cd frontend

npm run dev       # start the dev server (default port 5173)
npm run build     # type-check and build for production
npm run preview   # preview the production build
npm run test      # run the Vitest unit tests
```

To run the dev server on a different port, set `VITE_PORT`; to point it at a
backend on another host/port, set `VITE_API_TARGET`:

```bash
VITE_PORT=3000 VITE_API_TARGET=http://localhost:8001 npm run dev
```

## Configuration

The backend reads environment variables (prefixed with `FLOWFRAME_`) and an
optional `.env` file. The fastest way to create one is:

```bash
cd backend
flowframe init        # writes a commented starter .env
```

A minimal `.env`:

```bash
# Database — FlowFrame is async, so the URL must use an async driver.
FLOWFRAME_DATABASE_URL=sqlite+aiosqlite:///./flowframe.db
# PostgreSQL: postgresql+asyncpg://user:password@localhost/flowframe
# MySQL:      mysql+aiomysql://user:password@localhost/flowframe

# Where uploads, outputs, and previews are written
FLOWFRAME_DATA_DIR=.data

# Default dataframe engine for runs that don't request one: polars | pandas
FLOWFRAME_DEFAULT_ENGINE=polars

# Allowed CORS origins (JSON list)
FLOWFRAME_CORS_ORIGINS=["http://localhost:5173"]

# Max upload size in MB
FLOWFRAME_MAX_UPLOAD_SIZE_MB=100
```

Run `flowframe info` to print the resolved configuration (the database password
is redacted), and `flowframe check` to validate it (writable data dir, async
driver, database reachable, engines available). For the full settings reference,
alternate databases, execution tuning, and production deployment, see
**[Advanced Setup](/guide/advanced-setup)** (and the [CLI reference](/guide/cli#environment-variables)).

:::warning Async driver required
The app runs on async SQLAlchemy. A plain `sqlite://`, `postgresql://`, or
`mysql://` URL will fail — always use the async variant (`sqlite+aiosqlite://`,
`postgresql+asyncpg://`, `mysql+aiomysql://`).
:::

:::warning Don't commit `.env`
Keep secrets out of version control — `.env` is already in `.gitignore`.
:::

When no `.env` is present, the backend defaults to
`sqlite+aiosqlite:///./flowframe.db`, so it runs with zero configuration.

## Database Setup

### SQLite (default)

SQLite requires no setup — it uses a local file (`flowframe.db`), and the schema
is created automatically the first time the backend starts. Tests run against
in-memory SQLite regardless of `DATABASE_URL`.

### PostgreSQL

Install the async driver and point FlowFrame at your database:

```bash
pip install asyncpg
```

```bash
# in backend/.env
FLOWFRAME_DATABASE_URL=postgresql+asyncpg://flowframe:password@localhost/flowframe_dev
```

The backend creates its tables on startup, so there is no manual migration step.
MySQL works the same way with `pip install aiomysql` and a
`mysql+aiomysql://` URL.

## Verify the Install

### Backend health

```bash
curl http://localhost:8055/health
```

Expected response: `{"status":"ok"}`

You can also run `flowframe check` for a fuller diagnostic.

### Explore the API

Open `http://localhost:8055/docs` for the interactive Swagger UI, where you can
list datasets, create flows, run them, and export Python code.

## Troubleshooting

### "Port 8055 already in use"

```bash
flowframe serve --port 8001
```

### "Port 5173 already in use"

```bash
VITE_PORT=3000 npm run dev
```

### "Database connection failed"

1. `FLOWFRAME_DATABASE_URL` must use an **async** driver
   (`sqlite+aiosqlite://`, `postgresql+asyncpg://`, `mysql+aiomysql://`).
2. The database server is running (for PostgreSQL / MySQL).
3. The matching async driver package is installed (`asyncpg`, `aiomysql`).

`flowframe check` reports all three at once.

### Module not found errors

Reinstall the backend from a clean virtual environment:

```bash
cd backend
rm -rf .venv
python -m venv .venv
source .venv/bin/activate    # or .venv\Scripts\activate on Windows
pip install -e .
```

For the frontend, remove `node_modules` and reinstall:

```bash
cd frontend
rm -rf node_modules
npm install
```

### CORS errors

Add the calling origin to `FLOWFRAME_CORS_ORIGINS` (a JSON list) in `backend/.env`:

```bash
FLOWFRAME_CORS_ORIGINS=["http://localhost:5173"]
```

## Next Steps

- **[Quick Start Tutorial](/guide/quick-start)** — build your first flow
- **[Interface Tour](/guide/interface)** — learn the UI
- **[Transformation Reference](/transformations/overview)** — all available operations

## Need Help?

- **[Troubleshooting Guide](/guide/troubleshooting)**
- **[GitHub Issues](https://github.com/rodrigo-arenas/FlowFrame/issues)** — report bugs
- **[GitHub Discussions](https://github.com/rodrigo-arenas/FlowFrame/discussions)** — ask questions

---

Once it's running, head to [Quick Start](/guide/quick-start) to build your first ETL flow! 🚀
