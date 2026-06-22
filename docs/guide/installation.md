---
title: Installation
description: Install FlowFrame locally in minutes
search: install setup download run requirements
---

# Installation Guide

Get FlowFrame running on your machine in just a few minutes.

## Requirements

- **Python 3.11+** — [Download Python](https://www.python.org/downloads/)
- **Node.js 18+** — [Download Node.js](https://nodejs.org/)
- **Git** — [Download Git](https://git-scm.com/)
- **PostgreSQL (optional)** — for persistent storage (SQLite is default)

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

Backend runs on `http://localhost:8000`

:::tip
The `--reload` flag restarts the server when you change code. Remove it in production.
:::

### 3. Start the Frontend

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

# Run migrations
uv run alembic upgrade head

# Start server
uv run uvicorn app.main:app --reload
```

#### Option 2: Traditional pip

```bash
cd backend

python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

pip install -e .[dev]

# Run migrations
alembic upgrade head

uvicorn app.main:app --reload
```

### Frontend Setup

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

Add:

```
# Database
DATABASE_URL=sqlite:///./flowframe.db
# or PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost/flowframe

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO

# CORS (allow frontend)
FRONTEND_URL=http://localhost:5173
```

:::warning
Never commit `.env` to git. Add it to `.gitignore`.
:::

### Frontend Configuration

Environment variables go in `frontend/.env.local`:

```
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=FlowFrame
```

## Database Setup

### SQLite (Default)

SQLite requires no setup — it uses a local file (`flowframe.db`).

```bash
# Run migrations
cd backend
alembic upgrade head
```

### PostgreSQL

If you prefer PostgreSQL:

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
DATABASE_URL=postgresql://flowframe:password@localhost/flowframe_dev
```

#### Run Migrations

```bash
cd backend
alembic upgrade head
```

## Docker Setup (Optional)

### Using Docker Compose

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
      DATABASE_URL: postgresql://flowframe:password@postgres/flowframe
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

### Frontend Health

Visit `http://localhost:5173` in your browser. You should see the home page.

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
1. DATABASE_URL in `.env`
2. PostgreSQL is running (if using it)
3. Migrations were run: `alembic upgrade head`

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

Update `backend/.env`:

```
FRONTEND_URL=http://localhost:5173
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
