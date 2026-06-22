# CLAUDE.md

## Project Summary

FlowFrame is an open-source, local-first visual ETL builder for simple,
pandas-based data transformations. Users build common ETL flows visually,
execute them through a Python/FastAPI backend, and export readable Python code.

It is **not** an Airflow/dbt/Spark replacement. Keep it lightweight.

## Current Status (read first)

- **Backend exists and is the working product**: FastAPI app, execution engine,
  transformation registry, dataset/flow/run persistence, and Python code export.
- **There is no frontend yet.** The `frontend/` directory does not exist.
  Do not reference a running UI, `localhost:5173`, or screenshots as if they
  exist. The React editor described below is the planned design, not shipped code.
- **Guardrail:** never document, demo, or claim a feature that is not implemented
  in `backend/`. When in doubt, check the code (`app/engine/registry.py` lists the
  real transformations) before writing docs or examples.

## Product Vision

The simplest possible visual ETL tool for small and medium datasets.

Primary users: analysts, data-curious business users, Python beginners,
developers who want quick repeatable pandas pipelines, and educators.

Core promise:
> Upload data, build a visual cleaning pipeline, preview results, run it, and
> export readable Python code.

## Non-Goals

- Airflow/Spark/dbt replacement, distributed or streaming execution
- Kubernetes orchestration, complex scheduling, dozens of connectors
- Enterprise permissions, multi-tenant SaaS, real-time collaboration

## Tech Stack

**Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x (async),
Alembic, pandas. Optional dataframe engines behind a backend abstraction
(`app/engine/backends/`): pandas (default), polars.

**Frontend (planned):** React, TypeScript, Vite, @xyflow/react, TanStack Query,
Zustand, shadcn/ui, Tailwind, React Hook Form + Zod.

**Database:** SQLAlchemy is the abstraction layer.
- **Default is SQLite** (zero-setup, file or in-memory). Tests run against
  in-memory SQLite (`sqlite+aiosqlite:///:memory:`).
- PostgreSQL / MySQL / others are supported via `DATABASE_URL`.
- **Guardrail:** the app is async — `DATABASE_URL` must use an async driver
  (`sqlite+aiosqlite://`, `postgresql+asyncpg://`, `mysql+aiomysql://`).
- Never hardcode database-specific behavior unless isolated behind an adapter.

## Development Principles

1. Keep the MVP small; prefer explicit code over clever abstractions.
2. Every visual node maps to one clear pandas operation.
3. Generated Python code must be readable and educational.
4. Backend is the source of truth; it validates everything (the frontend only
   validates early for UX).
5. Avoid vendor lock-in; keep the app easy to run locally.
6. Design for extension, but do not over-engineer.
7. Every new transformation must include tests.

## Core Domain Model

- **Flow** — saved pipeline: `id, name, description, graph_json, created_at, updated_at`.
- **Dataset** — source/uploaded file: `id, name, source_type, location, schema_json, sample_json, timestamps`.
- **FlowRun** — one execution: `id, flow_id, status, input_dataset_id, output_location, started_at, finished_at, error_message, logs_json`.
- **Transformation Node** — graph node: `id, type, label, config, position, input_handles, output_handles`.

## Node Types

- **Input:** CSV, Excel, Parquet
- **Cleaning:** rename/drop/select columns, filter rows, fill/drop nulls,
  remove duplicates, change types, sort, limit, replace values, string ops
- **Transform:** calculated column, group by + aggregate, join/merge, union/concat
- **Output:** CSV, Excel, Parquet

`app/engine/registry.py` is the authoritative list — keep docs in sync with it.

## API Design

REST only (no GraphQL for MVP).

- Flows: `GET/POST /api/flows`, `GET/PUT/DELETE /api/flows/{id}`
- Preview: `POST /api/flows/{id}/preview`, `POST /api/transformations/preview`
- Runs: `POST /api/flows/{id}/runs`, `GET /api/runs/{id}`
- Schedules: `GET/POST /api/flows/{id}/schedules`, `GET /api/schedules`,
  `GET/PATCH/DELETE /api/schedules/{id}`, `POST /api/schedules/{id}/run-now`
- Datasets: `POST /api/datasets/upload`, `GET /api/datasets`,
  `GET /api/datasets/{id}/sample`, `GET /api/datasets/{id}/schema`
- Code export: `POST /api/flows/{id}/export/python`

## Execution Engine

The engine: receives graph JSON → validates structure → topologically sorts
nodes → loads inputs → executes transformations in order → stores/returns output
→ saves run metadata, errors, and readable logs.

Each transformation implements a shared interface:

```python
class Transformation:
    type: str

    def validate_config(self, config: dict) -> None: ...
    def execute(self, df, config: dict): ...
    def to_python_code(self, input_var: str, output_var: str, config: dict) -> str: ...
```

Graph JSON is React Flow-compatible (`nodes` with `id/type/position/data.config`,
`edges` with `id/source/target`).

The default dataframe engine is **polars** (`settings.DEFAULT_ENGINE`); a run
may override it per request. The synchronous executor runs in a worker thread
(`asyncio.to_thread`) so it never blocks the event loop.

## Scheduling

A `Schedule` (cron + timezone + optional engine) runs a flow automatically. The
scheduler is a single in-process asyncio poller (`app/scheduler/runner.py`)
started in the FastAPI lifespan; `Schedule.next_run_at` (naive UTC) is the single
source of truth, so it survives restarts without a separate jobstore. It isolates
per-schedule failures, caps concurrency, skips overlapping runs, and applies a
per-schedule `catch_up` policy for slots missed while the server was down.
Configurable via `SCHEDULER_ENABLED` / `SCHEDULER_POLL_INTERVAL_SECONDS` /
`SCHEDULER_MAX_CONCURRENT_RUNS` (disabled in tests).

## Coding Standards

**Backend:** type hints everywhere; Pydantic schemas for API I/O; thin route
handlers; business logic in `services`; dataframe logic in `app/engine`.
Do **not** import FastAPI inside the engine, mix ORM models with Pydantic
schemas, or use pandas directly in route files. Add tests per transformation.

**Frontend (when it exists):** TypeScript, feature folders, React Flow logic in
`components/flow`/`features/flows`, TanStack Query for server state, Zustand for
local UI state, shadcn/ui components, Zod-validated config forms, API calls
centralized in `lib/api.ts`.

**Naming:** clear and specific (`DropNullsTransformation`, `FlowExecutionService`).
Avoid `Processor`, `Manager`, `Handler`, `Thing`, and generic abstractions.

## Testing

Backend: unit tests for transformations and graph validation, API tests for flow
CRUD, and at least one full CSV-pipeline integration test. Run with `pytest`
(tests use in-memory SQLite regardless of `DATABASE_URL`).

## Working Agreements for Claude

1. Start with the smallest working vertical slice; don't add infra before needed.
2. Make `DATABASE_URL` configurable via environment variables.
3. Keep generated Python code readable; avoid premature optimization.
4. Add tests when adding transformations.
5. Update docs when architecture changes — and only document what is implemented.
6. Ask before adding large dependencies.

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (90-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk vitest run          # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%)
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->
