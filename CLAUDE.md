# CLAUDE.md

## Project Summary

FlowFrame is an open-source, local-first visual ETL builder for simple,
dataframe-based data transformations. Users build common ETL flows visually,
execute them through a Python/FastAPI backend, and export readable Python code.

It is **not** an Airflow/dbt/Spark replacement. Keep it lightweight.

## Current Status (read first)

- **Backend is the source of truth**: FastAPI app, execution engine,
  transformation registry, dataset/flow/run persistence, in-process scheduler,
  and Python code export.
- **The frontend exists** in `frontend/` (Vite + React 18 + TS strict). Shipped
  pages: landing, projects, datasets, the React Flow editor, runs history + run
  detail, schedules (list + detail + cron builder), and connections. Dev server
  defaults to port **5173** (frontend) proxying the API at **8055** (backend);
  both are configurable via `VITE_PORT` and `VITE_API_TARGET`.
- **Guardrail:** never document, demo, or claim a feature that is not actually
  implemented. Check the code before writing docs or examples — the backend
  (`app/engine/registry.py` for transformations, `app/engine/node_kinds.py` for
  I/O node types, `app/api/routes/` for the API) and the frontend
  (`frontend/src/features/`) are authoritative.

## Product Vision

A practical, local-first visual ETL tool for small and medium datasets —
powerful enough for data analysts and data engineers, approachable enough
for business analysts and Python beginners.

Primary users: data analysts, data engineers, developers who want
repeatable pipelines without infrastructure overhead, business analysts,
and Python learners getting started with data transformation.

Core promise:
> Upload data, build a visual pipeline, preview every step, run it,
> schedule it, get your outputs — and export readable Python code when you need it.

## Non-Goals

- Airflow/Spark/dbt replacement, distributed or streaming execution
- Kubernetes orchestration, complex scheduling, dozens of connectors
- Enterprise permissions, multi-tenant SaaS, real-time collaboration

## Tech Stack

**Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x (async),
Alembic, polars, pandas. Pluggable dataframe engine abstraction lives in
`app/engine/backends/`: polars (default), pandas.

**Frontend:** React, TypeScript, Vite, @xyflow/react, TanStack Query,
Zustand, shadcn/ui, Tailwind, React Hook Form + Zod. Lives in `frontend/`.

**Database:** SQLAlchemy is the abstraction layer.
- **Default is SQLite** (zero-setup, file or in-memory). Tests run against
  in-memory SQLite (`sqlite+aiosqlite:///:memory:`).
- PostgreSQL / MySQL / others are supported via `DATABASE_URL`.
- **Guardrail:** the app is async — `DATABASE_URL` must use an async driver
  (`sqlite+aiosqlite://`, `postgresql+asyncpg://`, `mysql+aiomysql://`).
- Never hardcode database-specific behavior unless isolated behind an adapter.

## Development Principles

1. Keep the MVP small; prefer explicit code over clever abstractions.
2. Every visual node maps to one clear dataframe operation.
3. Generated Python code must be readable and runnable anywhere.
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
- **Flow Parameter** — typed, named value declared on a flow (stored in
  `graph_json.parameters`, like `graph_json.engine`); node configs reference it
  via `{{ name }}`. `app/engine/parameters.py` resolves values (precedence:
  per-run override > per-schedule override > default), coerces to type, and
  substitutes into node configs before execution/preview/codegen. A run records
  the resolved values (`FlowRun.parameters_json`); a schedule stores overrides
  (`Schedule.parameters_json`). Exported code renders them as variables
  (`app/engine/codegen_params.py`).

## Node Types

- **Input:** CSV, Excel, Parquet, SQL (database, via `app/connectors/`),
  Storage (S3/GCS/Azure Blob, via `app/connectors/`)
- **Cleaning:** rename/drop/select columns, filter rows, fill/drop nulls,
  remove duplicates, change types, sort, limit, replace values, string ops,
  split column, map values, remove outliers, round numbers, bin column,
  sample rows
- **Transform:** calculated column, group by + aggregate, join/merge,
  union/concat, parse dates, extract date parts, pivot, unpivot,
  window function, conditional column
- **Quality:** assertNotNull, assertUnique, assertValueRange, assertExpression,
  assertRowCount — pass-through nodes that enforce data contracts; violations
  either fail the run (error mode) or log a warning (warn mode)
- **Advanced:** pythonTransform — user-supplied Python function body; engine
  namespace (`pd`/`pl`) injected; syntax validated at save time
- **Output:** CSV, Excel, Parquet, SQL (database), Storage (S3/GCS/Azure Blob)

`app/engine/registry.py` is the authoritative list for transformation nodes.
`app/engine/node_kinds.py` is the authoritative list for I/O node types —
keep docs in sync with both.

## API Design

REST only (no GraphQL for MVP).

- Flows: `GET/POST /api/flows`, `GET/PUT/DELETE /api/flows/{id}`
- Preview: `POST /api/flows/{id}/preview`, `POST /api/transformations/preview`
- Runs: `POST /api/flows/{id}/runs`, `GET /api/runs` (filterable by flow,
  schedule, status, date), `GET /api/runs/{id}`, `GET /api/runs/{id}/output`,
  `POST /api/runs/{id}/retry`, `GET /api/runs/{id}/logs/stream` (SSE)
- Webhook: `GET /api/settings/webhook`, `POST /api/flows/{id}/trigger`
  (requires `X-FlowFrame-Secret` header; set `FLOWFRAME_WEBHOOK_SECRET` to enable)
- Schedules: `GET/POST /api/flows/{id}/schedules`, `GET /api/schedules`,
  `GET/PATCH/DELETE /api/schedules/{id}`, `POST /api/schedules/{id}/run-now`,
  `GET /api/schedules/{id}/runs`
- Datasets: `POST /api/datasets/upload`, `GET /api/datasets`,
  `GET/PATCH/DELETE /api/datasets/{id}`, `GET /api/datasets/{id}/schema`,
  `GET /api/datasets/{id}/sample`, `GET /api/datasets/{id}/profile`,
  `GET /api/datasets/{id}/versions`,
  `GET /api/datasets/{id}/versions/{version}/download`,
  `GET /api/datasets/{id}/flows`
- Connections: `GET/POST /api/connections`, `GET/PATCH/DELETE /api/connections/{id}`,
  `POST /api/connections/test-config`, `POST /api/connections/{id}/test`,
  `GET /api/connections/{id}/tables`, `GET /api/connections/{id}/objects`,
  `GET /api/connections/providers`
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
may override it per request. The synchronous executor runs off the event loop so
it never blocks: `EXECUTION_MODE` selects a worker thread (`thread`, default) or
a `ProcessPoolExecutor` (`process`, true multi-core; see
`app/engine/process_pool.py`). Only picklable args cross the process boundary —
the DB session always stays in the parent. `RUN_TIMEOUT_SECONDS` (0 = off)
abandons an over-running run; in `process` mode the pool is recycled to reclaim
the CPU, in `thread` mode the run is abandoned but the thread finishes. Each
node records a `duration_ms` (in the run DAG / `node_results`) for observability.

## Running

The `flowframe` console script (`app/cli.py`, stdlib argparse) is the setup
surface. Commands:
- `flowframe serve` — boots the API + background scheduler in a single process
  (no broker). Flags map to env vars before the app imports:
  `--host/--port/--reload/--log-level`, `--db-url`, `--data-dir`, `--engine`,
  `--execution-mode`, `--no-scheduler`. Default port is **8055**.
- `flowframe init` — write a commented starter `.env` (`--path`, `--force`).
- `flowframe info` — print the resolved settings (DB password redacted).
- `flowframe check` — validate the environment: data dir writable, async driver,
  database reachable, engines available (exit 1 on failure).
- `flowframe db upgrade|current|reset` — Alembic schema management (see DB note).
- `flowframe transformations list` — list registered node types from the registry.

Commands that resolve settings accept `--env-file PATH` (load a specific `.env`
before settings resolve; existing env vars win, serve flags still override).
`info`/`check`/`transformations list` accept `--output table|json`.

**Database migrations:** the Alembic environment lives in `app/migrations/` (so
it ships in the wheel, not a sibling dir). `flowframe db upgrade` applies
migrations; because `serve` still bootstraps the schema via `create_all`,
`upgrade` **adopts** an existing un-migrated DB by stamping the current head
instead of re-creating tables — so adopting Alembic is non-destructive. SQLite
runs migrations in batch mode (`render_as_batch`). `db reset` is destructive,
requires `--yes`, and refuses when `ENVIRONMENT=production` unless `--force`.

## Scheduling

A `Schedule` (cron + timezone + optional engine) runs a flow automatically. The
scheduler is a single in-process asyncio poller (`app/scheduler/runner.py`)
started in the FastAPI lifespan; `Schedule.next_run_at` (naive UTC) is the single
source of truth, so it survives restarts without a separate jobstore. It isolates
per-schedule failures, caps concurrency, skips overlapping runs, and applies a
per-schedule `catch_up` policy for slots missed while the server was down.

Reliability behaviors:
- **Orphan recovery:** on startup, runs left `running` (interrupted by a crash)
  are marked `failed` — single-process means they can never resume.
- **Retries:** a failed run retries up to `max_retries` with exponential backoff
  (`retry_delay_seconds`, capped at 1h) before falling back to the next cron slot.
- **Auto-disable:** after `SCHEDULER_MAX_CONSECUTIVE_FAILURES` consecutive failed
  runs a schedule is disabled with a `disabled_reason`; re-enabling clears the
  streak. Manual `run-now` stays out of the retry/auto-disable machinery.
- **Run history:** runs carry `trigger`/`schedule_id`; filter via
  `GET /api/runs?schedule_id=` or `GET /api/schedules/{id}/runs`.

Configurable via `SCHEDULER_ENABLED` / `SCHEDULER_POLL_INTERVAL_SECONDS` /
`SCHEDULER_MAX_CONCURRENT_RUNS` / `SCHEDULER_MAX_CONSECUTIVE_FAILURES` (the
scheduler is disabled in tests).

## Coding Standards

**Backend:** type hints everywhere; Pydantic schemas for API I/O; thin route
handlers; business logic in `services`; dataframe logic in `app/engine`.
Do **not** import FastAPI inside the engine, mix ORM models with Pydantic
schemas, or use pandas directly in route files. Add tests per transformation.

**Frontend:** TypeScript, feature folders under `frontend/src/features/`, React
Flow logic in `components/flow`/`features/flows`, TanStack Query for server state
(hooks per feature) keyed via `lib/queryClient.ts`, Zustand for local UI state,
shadcn/ui components, Zod-validated config forms, all API calls centralized in
`lib/api.ts` with shared types in `lib/types.ts`.

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
7. **When implementing a new feature or changing existing UI/UX**, check whether the
   docs need new or updated screenshots. Specifically:
   - Scan `docs/public/screenshots/` for existing screenshots that may be stale.
   - Check the relevant doc pages (`docs/guide/`, `docs/transformations/`) for
     `![…](/screenshots/…)` references that need refreshing.
   - If a new page or major UI change has no screenshot yet, note which page(s)
     would benefit from one and propose taking them (screenshots are captured with
     Python Playwright via the `mcp__claude-in-chrome__*` browser tools or the
     script in `docs/scripts/` if it exists).

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
