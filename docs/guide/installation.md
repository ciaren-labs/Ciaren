---
title: Installation
description: Install FlowFrame locally in minutes
search: install setup download run requirements
---

# Installation Guide

Get FlowFrame running on your machine in just a few minutes.

## Requirements

- **Python 3.12+** — [Download Python](https://www.python.org/downloads/)
- **Git** — [Download Git](https://git-scm.com/)
- **PostgreSQL / MySQL (optional)** — SQLite is the zero-setup default

:::info Backend only, for now
FlowFrame today is a backend service (FastAPI + pandas) you drive through its
REST API. The visual editor is in development, so **Node.js is not needed yet** —
it will be required once the `frontend/` package ships.
:::

## Quick Start (5 minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/rodrigo-arenas/FlowFrame.git
cd FlowFrame
```

### 2. Start the Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate    # macOS/Linux
# or
.venv\Scripts\activate        # Windows (PowerShell)

# Install dependencies
pip install -e .

# Start the server
uvicorn app.main:app --reload
```

Backend runs on `http://localhost:8000`. The database schema is created
automatically on first start, so there is no separate migration step to run.

:::tip
The `--reload` flag restarts the server when you change code. Remove it in production.
:::

Open the interactive API docs at `http://localhost:8000/docs` to explore and try
every endpoint.

### 3. Start the Frontend

:::warning UI in development
The visual editor is not available yet — the `frontend/` directory is not part of
the repository today. For now, FlowFrame runs as a backend service you can drive
through its REST API (see the [API Reference](/api/rest-api)). The steps below
describe the planned frontend setup.
:::

In a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend runs on `http://localhost:5173`

### 4. Open in Browser

Visit `http://localhost:5173` and you're ready to build!

## Detailed Setup

### Backend Setup

#### Option 1: Using `uv` (Faster)

```bash
cd backend

# Install uv
curl https://astral.sh/uv/install.sh | sh

# Install dependencies with uv
uv sync

# Start server (tables are created automatically on startup)
uv run uvicorn app.main:app --reload
```

#### Option 2: Traditional pip

```bash
cd backend

python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

pip install -e .[dev]

uvicorn app.main:app --reload
```

### Frontend Setup

:::warning Planned
The `frontend/` package is not part of the repository yet. The steps below
describe the intended setup once the visual editor ships.
:::

```bash
cd frontend

npm install

# Development
npm run dev

# Build for production
npm run build

# Preview built site
npm run preview
```

## Configuration

### Backend Configuration

The backend uses environment variables. Create a `.env` file:

```bash
cd backend
touch .env
```

All settings use the `FLOWFRAME_` prefix. Add:

```
# Database — FlowFrame is async, so the URL must use an async driver.
FLOWFRAME_DATABASE_URL=sqlite+aiosqlite:///./flowframe.db
# or PostgreSQL:
# FLOWFRAME_DATABASE_URL=postgresql+asyncpg://user:password@localhost/flowframe
# or MySQL:
# FLOWFRAME_DATABASE_URL=mysql+aiomysql://user:password@localhost/flowframe

# Environment
FLOWFRAME_ENVIRONMENT=development

# Where uploads, outputs, and previews are written
FLOWFRAME_DATA_DIR=.data

# Allowed CORS origins (JSON list)
FLOWFRAME_CORS_ORIGINS=["http://localhost:5173"]

# Max upload size in MB
FLOWFRAME_MAX_UPLOAD_SIZE_MB=100
```

:::warning Async driver required
The app runs on async SQLAlchemy. A plain `sqlite://`, `postgresql://`, or
`mysql://` URL will fail to connect — always use the async variant
(`sqlite+aiosqlite://`, `postgresql+asyncpg://`, `mysql+aiomysql://`).
:::

The default when no `.env` is present is
`sqlite+aiosqlite:///./flowframe.db`, so the backend runs with zero
configuration.

:::warning
Never commit `.env` to git. Add it to `.gitignore`.
:::

### Frontend Configuration (planned)

Once the visual editor ships, its environment variables will go in
`frontend/.env.local`:

```
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=FlowFrame
```

## Database Setup

### SQLite (Default)

SQLite requires no setup — it uses a local file (`flowframe.db`), and the schema
is created automatically the first time the backend starts. Tests run against
in-memory SQLite regardless of `DATABASE_URL`.

### PostgreSQL

If you prefer PostgreSQL (install the `asyncpg` driver, e.g. `pip install asyncpg`):

#### Install PostgreSQL

- **macOS:** `brew install postgresql`
- **Windows:** [PostgreSQL Installer](https://www.postgresql.org/download/windows/)
- **Linux:** `sudo apt-get install postgresql`

#### Create Database

```bash
psql -U postgres

CREATE DATABASE flowframe_dev;
CREATE USER flowframe WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE flowframe_dev TO flowframe;
```

#### Configure Backend

Update `backend/.env`:

```
FLOWFRAME_DATABASE_URL=postgresql+asyncpg://flowframe:password@localhost/flowframe_dev
```

The backend creates its tables on startup, so no manual migration step is needed.

## Docker Setup (Optional)

### Using Docker Compose

The `frontend` service below is shown for completeness but is **planned** — the
visual editor is not in the repository yet. Run just the `backend` and
`postgres` services for now.

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://flowframe:password@postgres/flowframe
      ENVIRONMENT: development
    depends_on:
      - postgres
    volumes:
      - ./backend:/app

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: flowframe
      POSTGRES_USER: flowframe
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Start:

```bash
docker-compose up -d
```

Access at `http://localhost:5173`

## Verify Installation

### Backend Health

```bash
curl http://localhost:8000/health
```

Expected response: `{"status":"ok"}`

### Explore the API

Open `http://localhost:8000/docs` for the interactive Swagger UI, where you can
list datasets, create flows, run them, and export Python code.

## Troubleshooting

### "Port 8000 already in use"

Change port:

```bash
uvicorn app.main:app --reload --port 8001
```

### "Port 5173 already in use"

Change port:

```bash
npm run dev -- --port 3000
```

### "Database connection failed"

Check:

1. `FLOWFRAME_DATABASE_URL` in `.env` uses an **async** driver
   (`sqlite+aiosqlite://`, `postgresql+asyncpg://`, `mysql+aiomysql://`)
2. The database server is running (if using PostgreSQL or MySQL)
3. The matching async driver package is installed (`asyncpg`, `aiomysql`)

### Module not found errors

Reinstall dependencies:

```bash
# Backend
cd backend
rm -rf .venv
python -m venv .venv
pip install -e .

# Frontend
cd frontend
rm -rf node_modules
npm install
```

### CORS errors

Add your client's origin to `FLOWFRAME_CORS_ORIGINS` in `backend/.env`:

```
FLOWFRAME_CORS_ORIGINS=["http://localhost:5173"]
```

## Next Steps

- **[Quick Start Tutorial](/guide/quick-start)** — build your first flow
- **[Interface Tour](/guide/interface)** — learn the UI
- **[Transformation Reference](/transformations/overview)** — all available operations

## Need Help?

- **[Troubleshooting Guide](/guide/troubleshooting)**
- **[GitHub Issues](https://github.com/rodrigo-arenas/FlowFrame/issues)** — Report bugs
- **[GitHub Discussions](https://github.com/rodrigo-arenas/FlowFrame/discussions)** — Ask questions

---

Once installed and running, head to [Quick Start](/guide/quick-start) to build your first ETL flow! 🚀
