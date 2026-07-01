---
title: Installation
description: Install and run Ciaren locally in minutes
search: install setup download run requirements frontend backend
---

# Installation Guide

Get Ciaren running on your machine in a few minutes. Ciaren has two parts:

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
git clone https://github.com/ciaren-labs/Ciaren.git
cd Ciaren
```

### 2. Start the backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows (PowerShell)

# Install Ciaren (exposes the `ciaren` command)
pip install -e .

# Run the API + background scheduler in one process
ciaren serve
```

The backend runs on `http://localhost:8055`. The database schema is **created
automatically** on first start — there is no migration step. Open the interactive
API docs at `http://localhost:8055/docs`.

:::tip Database connectors are optional
The core install stays lightweight. To use external databases from SQL Input /
SQL Output nodes, install the matching connector extra — e.g.
`pip install -e ".[mysql]"`, or grab the connector set with
`pip install -e ".[all]"`. These connector extras are separate from the async
driver used by `CIAREN_DATABASE_URL`; if you want Ciaren's own metadata
database on MySQL, install `aiomysql` and use a `mysql+aiomysql://` URL. See
[Connections](/guide/connections) for the connector list.
:::

:::tip ciaren serve vs. uvicorn
`ciaren serve` is the recommended entry point — it boots the API and the
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

Visit `http://localhost:5173` and start building flows. (During development this
is the URL to open — **not** the backend's `:8055`, which serves the API.)

![Projects page — the first screen you see after installation, with the Demo project ready to explore](/screenshots/projects.png)

:::tip One-command app (no separate frontend server)
Build the frontend once and `ciaren serve` will serve the web UI too, so the
whole app lives at a single URL:

```bash
cd frontend && npm run build      # produces frontend/dist
cd ../backend && ciaren serve  # banner: "Open the app: http://localhost:8055"
```

`ciaren serve` auto-detects `frontend/dist`; override its location with
`CIAREN_FRONTEND_DIST`. Its startup banner always tells you the exact URL to open.
:::

:::tip Enable Machine Learning
The ML nodes (Train / Predict / Evaluate …) only appear once you install the extra
**and** enable the feature:

```bash
pip install -e ".[ml]"
# .env  (ciaren init writes these for you)
CIAREN_ML_ENABLED=true
```

If the **Machine Learning** palette section is missing, check `ciaren check`
(it reports `ml: ok`) and that the frontend you're viewing is up to date. See the
[ML Quick Start](/guide/ml-quickstart).
:::

## Detailed Setup

### Backend with `uv` (faster)

[`uv`](https://docs.astral.sh/uv/) is a fast Python package manager:

```bash
cd backend
uv sync                       # install dependencies
uv run ciaren serve        # run the server
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

The backend reads environment variables (prefixed with `CIAREN_`) and an
optional `.env` file. The fastest way to create one is:

```bash
cd backend
ciaren init        # writes a commented starter .env
```

A minimal `.env`:

```bash
# Database — Ciaren is async, so the URL must use an async driver.
CIAREN_DATABASE_URL=sqlite+aiosqlite:///./ciaren.db
# PostgreSQL: postgresql+asyncpg://user:password@localhost/ciaren
# MySQL:      mysql+aiomysql://user:password@localhost/ciaren

# Where uploads, outputs, and previews are written
CIAREN_DATA_DIR=.data

# Default dataframe engine for runs that don't request one: polars | pandas
CIAREN_DEFAULT_ENGINE=polars

# Allowed CORS origins (JSON list)
CIAREN_CORS_ORIGINS=["http://localhost:5173"]

# Max upload size in MB
CIAREN_MAX_UPLOAD_SIZE_MB=100
```

Run `ciaren info` to print the resolved configuration (the database password
is redacted), and `ciaren check` to validate it (writable data dir, async
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
`sqlite+aiosqlite:///./ciaren.db`, so it runs with zero configuration.

## Database Setup

### SQLite (default)

SQLite requires no setup — it uses a local file (`ciaren.db`), and the schema
is created automatically the first time the backend starts. Tests run against
in-memory SQLite regardless of `DATABASE_URL`.

### PostgreSQL

Install the async driver and point Ciaren at your database:

```bash
pip install asyncpg
```

```bash
# in backend/.env
CIAREN_DATABASE_URL=postgresql+asyncpg://ciaren:password@localhost/ciaren_dev
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

You can also run `ciaren check` for a fuller diagnostic.

### Explore the API

Open `http://localhost:8055/docs` for the interactive Swagger UI, where you can
list datasets, create flows, run them, and export Python code.

## Troubleshooting

### "Port 8055 already in use"

```bash
ciaren serve --port 8001
```

### "Port 5173 already in use"

```bash
VITE_PORT=3000 npm run dev
```

### "Database connection failed"

1. `CIAREN_DATABASE_URL` must use an **async** driver
   (`sqlite+aiosqlite://`, `postgresql+asyncpg://`, `mysql+aiomysql://`).
2. The database server is running (for PostgreSQL / MySQL).
3. The matching async driver package is installed (`asyncpg`, `aiomysql`).

`ciaren check` reports all three at once.

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

Add the calling origin to `CIAREN_CORS_ORIGINS` (a JSON list) in `backend/.env`:

```bash
CIAREN_CORS_ORIGINS=["http://localhost:5173"]
```

## Next Steps

- **[Quick Start Tutorial](/guide/quick-start)** — build your first flow
- **[Interface Tour](/guide/interface)** — learn the UI
- **[Transformation Reference](/transformations/overview)** — all available operations

## Need Help?

- **[Troubleshooting Guide](/guide/troubleshooting)**
- **[GitHub Issues](https://github.com/ciaren-labs/Ciaren/issues)** — report bugs
- **[GitHub Discussions](https://github.com/ciaren-labs/Ciaren/discussions)** — ask questions

---

Once it's running, head to [Quick Start](/guide/quick-start) to build your first data workflow! 🚀
