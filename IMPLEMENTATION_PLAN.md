# Implementation Plan — Flow Parameters

> Status: **in progress** · Started 2026-06-24 · Branch: `feature/ml-extension`
> (no prior implementation plans existed in the repo)

## Goal

Make a flow **reusable across runs** by letting it declare named, typed
**parameters** that node configs reference with `{{ name }}` placeholders. Values
resolve at run / preview / schedule time, with this precedence:

```
per-run override (API body)  >  per-schedule override  >  flow default
```

This is the single highest-leverage gap vs. commercial visual-ETL tools (Alteryx
app parameters, KNIME flow variables, dbt vars, Talend contexts): it turns "one
flow per file/date" into "one flow, many runs", and it composes with scheduling
(same flow, different `{{ date }}` each night) and code export.

### Example

Parameters declared on the flow (stored in `graph_json.parameters`):

```json
{
  "parameters": [
    {"name": "input_path", "type": "string", "default": "data/sales.csv"},
    {"name": "min_amount", "type": "number", "default": 0},
    {"name": "keep_top",   "type": "integer", "default": 100}
  ]
}
```

Referenced inside node configs:

```json
{"type": "storageInput", "data": {"config": {"path": "{{ input_path }}"}}}
{"type": "filterRows",   "data": {"config": {"column": "amount", "op": ">=", "value": "{{ min_amount }}"}}}
{"type": "limitRows",    "data": {"config": {"n": "{{ keep_top }}"}}}
```

Run with overrides: `POST /api/flows/{id}/runs` body
`{"parameters": {"input_path": "data/2026-06.csv", "min_amount": 50}}`.

## Design decisions

1. **Storage**: parameter *specs* live on the graph document under a top-level
   `parameters` key (a list), exactly like the existing `engine` key. No new flow
   column, and they travel with export/import for free.
2. **Reference syntax**: `{{ name }}` inside **string** config values.
   - A value that is *exactly* `{{ name }}` is replaced with the **typed** value
     (so an `integer` param stays an `int` for e.g. `limitRows.n`).
   - A placeholder embedded in a larger string (`data/{{ date }}.csv`) is string-
     interpolated (`str(value)`).
   - Unknown placeholders are left untouched (never crash on literal braces).
3. **Substitution is pure & central**: `apply_parameters(graph, overrides) ->
   (resolved_graph, values)` deep-copies the graph and rewrites only each node's
   `data.config`. The executor, graph validation and code generators stay
   parameter-unaware — they only ever see a fully-resolved graph.
4. **Types** (kept small): `string`, `integer`, `number`, `boolean`. Dates are
   strings for now.
5. **Validation**: unknown override keys, missing required values (no default and
   no override), and type-coercion failures raise `ParameterError`, surfaced as a
   `400` before the run row is created.
6. **Reproducibility**: a run stores the **resolved** graph as its
   `graph_snapshot_json` (what actually executed) **and** the resolved
   `parameters_json` (the values used). Retry reuses the original run's values.

## Phases

### Phase 1 — Backend core ✅ (this change)

- [x] `app/core/enums.py` — add `ParameterType` StrEnum.
- [x] `app/engine/parameters.py` — `read_parameter_specs`, `resolve_values`,
      `substitute`, `apply_parameters`, `ParameterError` (pure, no deps on engine).
- [x] `app/schemas/parameter.py` — `ParameterSpec` Pydantic model.
- [x] `FlowRunCreate.parameters` and `FlowRunRead.parameters`.
- [x] `FlowRun.parameters_json` column + `FlowPreviewRequest.parameters`.
- [x] `Schedule.parameters_json` column + schedule create/update/read schemas +
      `ScheduleService` + `SchedulerRunner` pass-through.
- [x] `ExecutionService.run` — resolve params, run on the resolved graph, store
      values; `retry` reuses prior values. `PreviewService.preview_flow` resolves.
- [x] Alembic migration adding `flow_runs.parameters_json` and
      `schedules.parameters_json`.
- [x] Tests: parameters unit module + parameterized run + schedule override.

### Phase 2 — Code export as real variables ✅

- [x] Emit a `# Flow parameters` block at the top of the generated pandas /
      eager-polars / lazy-polars scripts (`name = default`) and reference the
      variables in node code instead of inlining literals. Implemented via
      `app/engine/codegen_params.py`: a `CodeRef` whose `repr` is the Python
      expression (`{{ name }}` → bare variable; `data/{{ x }}.csv` →
      `'data/{}.csv'.format(x)`), substituted into node configs which the
      generators already render with `{value!r}`. `CodegenService` falls back to
      inlining resolved defaults if a node can't handle a substituted value, so
      export never fails.
- [x] Save-time spec validation in `FlowService` create/update
      (`validate_parameter_specs`): malformed `parameters` lists (bad name,
      duplicate, unknown type, uncoercible default) are a clean 400.
- [x] Tests: `tests/engine/test_codegen_params.py` (unit) +
      `tests/api/test_export_parameters.py` (variables rendered, scripts compile,
      save-time 400s).

### Phase 3 — Frontend (next)

- [ ] Parameters panel in the flow editor (`frontend/src/features/flows`): list /
      add / edit / remove specs (name, type, default, description), persisted into
      `graph_json.parameters`.
- [ ] `{{ name }}` reference affordance in config forms (autocomplete of declared
      params; validation that referenced names exist).
- [ ] "Run with parameters" dialog on manual run; parameter overrides on the
      schedule create/edit form.
- [ ] Show the resolved parameter values on the run detail page.
- [ ] `lib/api.ts` / `lib/types.ts` — carry `parameters` on run + schedule.

### Phase 4 — Docs

- [ ] `docs/guide/` page on flow parameters; update `docs/api/runs.md` and
      `docs/api/schedules.md`; update `CLAUDE.md` domain model notes.

## Risks / notes

- Substitution only touches `data.config`; `dataset_id` / `connection_id`
  bindings are UUIDs chosen in the UI and not expected to be parameterized.
- Type-typed full-match replacement is what lets numeric/boolean params flow into
  configs that expect non-strings — keep that branch covered by tests.
- Migration is additive (nullable JSON columns) → non-destructive on every
  backend; `serve`'s `create_all` already picks up the new columns for fresh DBs.
