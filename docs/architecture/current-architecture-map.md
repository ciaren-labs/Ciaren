# Current Architecture Map (Phase 0)

> Inventory of the extension points that the plugin/open-core refactor
> (`internal/PLUGIN_ARCHITECTURE_PLAN.md`) needs to formalize. This is a snapshot of
> **where knowledge lives today** so later phases can replace static wiring with
> provider registration without missing a spot.

## 1. Static registries (backend)

| Concern | Location | Shape | How it is populated |
|---|---|---|---|
| Transformation nodes | `app/engine/registry.py` | `_REGISTRY: dict[str, BaseTransformation]` | Hard-coded `_register(...)` call listing every node class; ML nodes added by `_register_ml_nodes()` gated on `ml_core_available()`. |
| I/O node types | `app/engine/node_kinds.py` | module-level dicts/frozensets (`INPUT_SOURCE_TYPES`, `OUTPUT_SOURCE_TYPES`, model/handle maps) | Literal dicts. |
| DataFrame engines | `app/engine/backends/` | `@register_engine` decorator into a module dict in `backends/base.py` | `backends/__init__.py` imports `PandasEngine` (always) and `PolarsEngine` (optional). |
| Connectors / providers | `app/connectors/providers.py` | `PROVIDERS: dict[str, Provider]` + `_STORAGE_CONNECTOR_FACTORIES` | Literal dict of `Provider` dataclasses; connector singletons/factories chosen by `provider.kind`. |
| Exporters (codegen) | `app/engine/codegen.py`, `polars_codegen.py`, `sql_codegen.py` | functions, not a registry | One `to_python_code` / `to_polars_code` per transformation; codegen walks the graph. Surfaced via `CodegenService.export`. |
| Validators (quality) | `app/engine/transformations/quality.py` | regular transformations in `_REGISTRY` | Assertion nodes are ordinary `BaseTransformation`s (no separate validator registry). |
| ML node type set | `app/engine/registry.py` | `_ML_TYPES: set[str]` | Filled by `_register_ml_nodes()`; used by the API to hide/show ML nodes. |

There is **no** plugin loader, manifest, capability registry, signature check,
permission model, or license manager today.

## 2. Node metadata duplication (the catalog gap)

The **presentational** node metadata (label, category, default config,
description) lives **only in the frontend**:

- `frontend/src/lib/nodeCatalog.ts` — `NODE_TYPES: NodeTypeDef[]` (label,
  category, `defaultConfig`, handle topology, `requiresMl`, description), plus
  `CATEGORY_LABELS`/`CATEGORY_ORDER`.

The backend only exposes **type names** (`GET /api/transformations` →
`list[str]`) and derives handle topology from the transformation classes
(`input_handles`, `optional_input_handles`, `multi_input`) and `node_kinds.py`
(output handles, model handles). So the same node is described in two places and
the backend cannot serve a complete catalog. **Phase 1b/1c close this** by adding
a backend node-metadata module and a `GET /api/catalog/nodes` endpoint; Phase 1f
makes the frontend consume it.

## 3. The portable flow document

- `app/schemas/flow.py` already defines `FlowDocument` tagged
  `format = "ciaren.flow/v1"`, returned by `POST /api/flows/{id}/export/python`
  (`flow_document`) and accepted by `POST /api/flows/import` (which strips
  environment-specific dataset/connection ids).
- It is **not** versioned with a semver `schemaVersion`, has no JSON-schema, no
  migration path, and does not declare required plugins/capabilities. Phase 1e
  formalizes this without breaking the existing export/import.

Flows persist in the DB as React Flow-compatible `graph_json` (with
`graph_json.parameters` and `graph_json.engine`); there is no `.flow` file on
disk today.

## 4. API surface touching these concerns

- `app/api/routes/transformations.py` — `GET /api/transformations` (type names,
  ML-gated), `POST /api/transformations/preview`.
- `app/api/routes/connections.py` — `GET /api/connections/providers`
  (`list_providers()`), connection CRUD/test.
- `app/api/routes/flows.py` — flow CRUD, `import`, `export/python`.
- ML gating helpers: `app/ml/availability.py` (`ml_core_available`,
  `ml_extension_ready`), `app/engine/registry.py` (`is_ml_node`, `ml_node_types`).

## 5. ML isolation (already partial)

scikit-learn, MLflow, and joblib are core dependencies, so `ml_core_available()`
is effectively always true and `app/engine/transformations/ml/` loads normally
on a base install. Import-isolation now matters only for XGBoost/LightGBM: their
model builders (`_xgboost_classifier`, `_lightgbm_classifier`, etc. in
`app/ml/models.py`) import those libraries lazily inside function bodies, so a
base install without the `[ml]` extra never imports them — `ModelSpec.requires`
gates each of those model types individually. ML lives in
`app/engine/transformations/ml/` and `app/ml/`. The `ML_ENABLED` flag gates the
product surface (palette/routes) at the service layer; the registry gates on
library availability (a defensive check now, since the core libraries are
guaranteed present). This is close to the target "optional provider" model —
Phase 1b expresses it as an explicit `NodeProvider` rather than a
special-cased registry branch.

## 6. Refactor seams (where providers plug in)

1. `registry.py::_REGISTRY` ← built-in `NodeProvider` registers the same node
   instances into a `ServiceRegistry`; the existing `get_transformation` /
   `list_transformation_types` API stays as a thin facade for back-compat.
2. `providers.py::PROVIDERS` ← built-in `ConnectorProvider` exposes the same
   `Provider` rows as `ConnectorSpec`s.
3. `backends/base.py` engine dict ← built-in `ExecutionProvider`.
4. `codegen*.py` ← built-in `ExporterProvider` (python / polars / polars-lazy).
5. `node_kinds.py` + class handle attrs + new node-metadata module ← combined
   into `NodeSpec`s by the built-in `NodeProvider`.

## 7. Constraints carried into the refactor

- Backend stays the source of truth and validates everything.
- Engine code must not import FastAPI; the `plugin_api` layer must not import the
  app's FastAPI/ORM internals.
- ML stays import-isolated; the open core must not import premium plugins.
- Every change keeps the existing endpoints and the test suite green.
