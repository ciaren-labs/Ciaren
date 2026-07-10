# Backend architecture guide

A short map of where things go and the boundaries between them. The layering rules
below are **enforced by tests** (`backend/tests/test_architecture_boundaries.py`), so
a violation fails CI rather than eroding the structure silently.

## Layers

```
HTTP  ──▶  API layer        app/api/            thin adapters: parse request → call a service → shape response
          Application       app/services/       use cases: validation, queries, transactions, orchestration
          Engine            app/engine/         execute / validate / codegen graphs; pure compute, no web
          Integrations      app/connectors/     external DBs, storage, REST; no web/DB-model knowledge
          Persistence       app/db/             SQLAlchemy models + Alembic migrations
          Contracts         app/schemas/        Pydantic request/response models
          Plugins           app/plugin_api/ + app/plugins/   extension contracts + runtime
          Bootstrap         app/bootstrap/      startup/shutdown lifecycle, seeding, frontend mount
```

`app/main.py` is only a composition root: `create_app()` wires middleware
(`app/api/middleware.py`), error handlers (`app/api/errors.py`), routers
(`app/api/routers.py`), and the frontend mount (`app/bootstrap/frontend.py`); the
startup/shutdown sequence lives in `app/bootstrap/lifespan.py`.

## Enforced boundary rules

1. **Routes don't take a raw `AsyncSession`.** A route depends on a `*ServiceDep`
   (see `app/api/deps.py`) and delegates DB work to the service. The one exception
   is the `/ready` readiness probe, whose job *is* to check DB connectivity.
2. **The engine imports no web/service/schema layer** (`fastapi`, `app.api`,
   `app.services`, `app.schemas`). It operates on plain graph dicts and dataframes.
3. **Connectors know nothing about the web or DB models** (no `fastapi`, `app.api`,
   `app.db`, `app.schemas`). They speak `ConnectionSpec`/`StorageSpec` only.
4. **Services stay below the API layer** (no `app.api` imports).
5. **Plugins integrate only through `app.plugin_api`** contracts.

If one of these tests fails, move the logic to the right layer — don't relax the rule.

## Transactions

A service method owns its transaction (commit/rollback). Routes never commit. When a
use case spans work that must be atomic within one request-scoped session, keep the
commit at the service boundary; use a SAVEPOINT (`db.begin_nested()`) for a
best-effort sub-step that must not poison the outer transaction (e.g. output-dataset
registration in `ExecutionService.run`).

## REST / routing conventions

Routers are mounted in `app/api/routers.py`. Conventions:

- **Top-level collections** mount at `/api/<resource>`: `/api/flows`, `/api/datasets`,
  `/api/projects`, `/api/connections`, `/api/transformations`, `/api/catalog`,
  `/api/plugins`, `/api/marketplace`, `/api/settings`.
- **Nested / sibling paths** are owned by a router mounted at the bare `/api` prefix
  that declares its full paths internally: e.g. `runs` owns both
  `/api/flows/{id}/runs` and `/api/runs/...`; `ml`, `schedules`, and `webhooks`
  likewise.
- **Non-CRUD actions** use an explicit verb sub-path: `/api/flows/{id}/duplicate`,
  `/api/runs/{id}/cancel`, `/api/runs/{id}/retry`, `/api/datasets/{id}/restore`.
- **Health probes** are unprefixed: `/health` (liveness), `/ready` (readiness).
- Registration order matters: all API routers are included before the SPA catch-all
  (`app/bootstrap/frontend.py`), so `/api/*` is never shadowed by the frontend.

The registered route set is snapshotted in
`backend/tests/test_route_snapshot.py` — an intentional route change updates the
snapshot; an accidental one (typo, collision, dropped route) fails the test.

## Adding things

- **New endpoint**: thin route in `app/api/routes/`, logic in a service, contract in
  `app/schemas/`, wired via a `*ServiceDep` in `app/api/deps.py` and included in
  `app/api/routers.py`.
- **New node**: metadata (`engine/node_metadata.py`), config validation, pandas +
  polars execution and codegen (with lazy safety), parity tests, docs, and the
  frontend catalog fallback. A contract test (`backend/tests/test_node_catalog_contract.py`)
  guards the backend catalog against drift.
- **New connector/plugin**: implement the `app/plugin_api` contract; declare driver
  availability, permissions, and clear install/config error messages; add contract
  tests.
- **Schema change**: an Alembic migration is the single source of truth
  (`app/migrations/`); `init_db`'s additive-column pass is a dev convenience only.

## Adding a node (checklist)

The backend is the authoritative catalog; the frontend only keeps a static fallback
for offline/first-paint. Do all of this so the two never diverge:

1. **Transformation** — implement `BaseTransformation` in `app/engine/transformations/`:
   `validate_config`, `execute` (pandas), plus the polars path and `to_python_code` /
   `to_polars_code` (codegen), keeping lazy-safety in mind. Register it.
2. **Metadata** — add the node's label, category, description, and default config in
   `app/engine/node_metadata.py`; declare its handle topology (input/optional/model
   handles, output handles) via `node_kinds` so the catalog reports it.
3. **Parity tests** — validate + execute (pandas and polars) + codegen (pandas,
   polars, lazy). Behavior must match across engines.
4. **Catalog contract** — regenerate the catalog snapshot and reconcile the frontend
   fallback:
   - `CIAREN_UPDATE_NODE_CATALOG_SNAPSHOT=1 pytest tests/test_node_catalog_contract.py`
   - update `frontend/src/features/flows/editor/nodeCatalog.ts` until
     `frontend/src/features/flows/editor/__tests__/nodeCatalog.contract.test.ts` passes.
5. **Docs** — document the node where user-facing node docs live.

The catalog contract test fails if the backend metadata changes without the snapshot
(and thus the frontend fallback) being reconciled — that's the drift guard.
