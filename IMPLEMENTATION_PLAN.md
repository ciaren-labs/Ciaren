# Implementation Plan

## Feature Index

| # | Feature | Status | Branch |
|---|---|---|---|
| 1 | [Data Quality Nodes](#1-data-quality-nodes) | **in progress** | `feature/data-quality-nodes` |
| 2 | [Custom Python Transform](#2-custom-python-transform) | planned | — |
| 3 | [Python SDK + Webhook Trigger](#3-python-sdk--webhook-trigger) | planned | — |

---

## 1. Data Quality Nodes

> Status: **in progress** · Branch: `feature/data-quality-nodes`

### Goal

Add a **Quality** category of pass-through transformation nodes that enforce
explicit contracts on data at any point in the graph. A violation either fails
the run immediately (`error` mode) or continues with a warning recorded in the
run log (`warn` mode). The dataframe always passes through unchanged.

This directly addresses the "no hidden logic / unexpected behaviour" goal: data
assumptions become visible in the graph rather than silent expectations in
downstream code.

### Node types

| Type | Config keys | What it checks |
|---|---|---|
| `assertNotNull` | `columns`, `mode` | No nulls in the specified columns |
| `assertUnique` | `columns`, `mode` | No duplicate rows across the specified columns |
| `assertValueRange` | `column`, `min`, `max`, `inclusive`, `mode` | All values fall within [min, max] |
| `assertExpression` | `expression`, `mode` | A boolean column expression is true for every row |
| `assertRowCount` | `min_rows`, `max_rows`, `mode` | Row count falls within the declared bounds |

`mode` defaults to `"error"`. Both modes record the same structured result
(pass/fail, violation count, sample of violating rows) in the run's per-node
result; `"warn"` continues execution while `"error"` stops it.

### Design decisions

1. **Pass-through contract** — `execute()` always returns the original dataframe.
   The node has no side effect on data shape, only on run state.
2. **Structured violation report** — violations carry `{passed, violation_count,
   violating_rows_sample}`. The sample (up to 5 rows) is serialised into
   `logs_json` so the run detail page can display it without re-running.
3. **Warn mode via executor context** — the executor already threads a
   `node_results` dict per run. Assertions write their result into it alongside
   `duration_ms`. For `warn` mode the executor logs the result and continues;
   for `error` mode it raises `AssertionViolationError` which becomes the run's
   `error_message`.
4. **Engine-agnostic via backend abstraction** — each assertion is implemented
   once in `quality.py` using the existing `EngineBackend` methods where
   possible. Polars-specific expressions fall back to pandas syntax via the
   backend's `eval_expression` helper (to be added).
5. **Code export** — each node exports a readable `assert` block or
   `raise ValueError(...)` so the generated script enforces the same contracts
   without FlowFrame.
6. **Frontend** — Quality nodes appear in a new "Quality" palette section.
   Node colour: amber (distinct from cleaning/transform). Run detail shows a
   pass/fail badge per assertion node with the violation count.

### Phases

#### Phase 1 — Backend core ✅

- [x] `app/engine/transformations/quality.py` — `AssertionViolationError`,
      `_CheckResult` dataclass, `_BaseAssertion` mixin, and all 5 node classes.
- [x] `app/engine/registry.py` — register the 5 new types.
- [x] `NodeMetadata` / `NodeResult` — `assertion_passed`, `assertion_violation_count`,
      `assertion_violating_sample` fields; `apply_metadata` and `as_dict` updated.
- [x] Tests: 166 tests covering pass / error-mode fail / warn-mode continue /
      validate_config errors / edge cases (empty frames, boundary values,
      NaN, unknown columns, sample-cap) / executor integration.

#### Phase 2 — Code export ✅

- [x] `to_python_code()` on each assertion node — generates a readable
      `assert`/`if not … raise` block with the violation message.
- [x] `to_polars_code()` on each assertion node.
- [x] Tests: generated code compiles and runs correctly (pandas + polars,
      pass / warn / error-raises parametrized).

#### Phase 3 — Frontend ✅

- [x] Node palette: "Quality" section with 5 types, orange colour scheme.
- [x] Config sidebar forms for each node type (column pickers, range inputs,
      expression textarea, mode toggle).
- [x] Run detail: per-node assertion badge (✅ pass / ⚠ warn / ❌ fail) with
      violation count and sample rows table (up to 5 rows).
- [x] `NodeResult` type extended with assertion fields.

#### Phase 4 — Docs

- [ ] `docs/transformations/assert-not-null.md` and sibling pages.
- [ ] Entry in `docs/transformations/overview.md` Quality section.
- [ ] Sidebar entry in `.vitepress/config.ts`.
- [ ] Note in `CLAUDE.md` node-types list.

---

## 2. Custom Python Transform

> Status: **planned**

### Goal

An escape-hatch node (`pythonTransform`) where the user writes the body of a
Python function that takes the input dataframe and returns a transformed one.
Keeps complex or one-off logic inside FlowFrame rather than forcing a
pre-processing step outside the graph.

### Design decisions

1. **Function-body style** — config stores a `script` string that is the body
   of `def transform(df): …`. The node wraps it as a real function and calls it.
   This avoids `exec` in an arbitrary namespace and makes the scope explicit.
2. **Engine-aware namespace** — polars engine: `pl` and `polars` are available.
   Pandas engine: `pd` and `pandas` are available. No other imports unless the
   user adds them inside the script.
3. **Syntax validation at save time** — `compile(script, …)` in
   `validate_config`; a `SyntaxError` becomes a clean 400.
4. **No sandboxing** — FlowFrame is local-first; the user's machine runs it. A
   sandbox would break legitimate use cases (file access, custom library calls).
   Document clearly that scripts run with full user permissions.
5. **Code export** — the script body is inlined as a named function
   (`def transform_<node_id>(df): …`) in the generated script.
6. **Preview** — works identically to other transformation nodes (same preview
   endpoint, same row limit).

### Phases

#### Phase 1 — Backend core

- [ ] `app/engine/transformations/script.py` — `PythonTransformTransformation`;
      `validate_config` (syntax check); `execute` (wrap + call); `to_python_code`.
- [ ] `app/engine/registry.py` — register `pythonTransform`.
- [ ] Tests: valid script, syntax error caught, wrong return type caught,
      engine-matrix (script uses `pl` / `pd` correctly).

#### Phase 2 — Frontend

- [ ] Node palette entry under "Transform" (or new "Advanced" section).
- [ ] Config sidebar: code editor (Monaco or a `<textarea>` with monospace font),
      engine-aware placeholder snippet, error display.
- [ ] Tests: editor renders, error message surfaced on save.

#### Phase 3 — Docs

- [ ] `docs/transformations/python-transform.md`.
- [ ] Examples: polars snippet, pandas snippet, using an installed library.
- [ ] Security note (no sandboxing, local-only).

---

## 3. Python SDK + Webhook Trigger

> Status: **planned**

### Goal

Make FlowFrame composable with external MLOps pipelines, Airflow DAGs, CI/CD,
and notebooks. Two surfaces:

- **Webhook endpoint** — `POST /api/flows/{id}/trigger` with a secret header,
  so any HTTP-capable system can start a run without knowing the full REST API.
- **Python client package** — `pip install flowframe-client` ships a thin
  `FlowFrame` class that wraps the REST API with a friendly interface.

### Design decisions

1. **Webhook secret** — stored in settings (`FLOWFRAME_WEBHOOK_SECRET`). If
   unset, the endpoint is disabled (returns 404). Header: `X-FlowFrame-Secret`.
   Validates with `hmac.compare_digest` to prevent timing attacks.
2. **Sync + async wait** — the trigger endpoint accepts `?wait=true` to block
   until the run completes and return the run result; default is fire-and-return-
   run-id (the caller polls `GET /api/runs/{id}`).
3. **Client package lives in `client/`** — pure Python, no framework dependency,
   supports both sync (`FlowFrame`) and async (`AsyncFlowFrame`). Published to
   PyPI separately from the main package.
4. **Streaming logs** — `client.run(flow_id, stream_logs=True)` yields log lines
   via server-sent events (SSE) from a `GET /api/runs/{id}/logs/stream` endpoint.
   Blocked runs in CI pipelines benefit most from this.
5. **Auth** — the client accepts an `api_key` param; the server validates it via
   the existing (or new) `FLOWFRAME_API_KEY` setting. No auth by default for
   local use.

### Phases

#### Phase 1 — Webhook endpoint

- [ ] `GET /api/settings/webhook` — returns whether the webhook is configured
      (not the secret itself).
- [ ] `POST /api/flows/{id}/trigger` — validates secret, creates run, returns
      run id; `?wait=true` polls until terminal state.
- [ ] `FLOWFRAME_WEBHOOK_SECRET` setting + docs in `flowframe init` template.
- [ ] Tests: secret validation, fire-and-forget, wait mode.

#### Phase 2 — SSE log streaming

- [ ] `GET /api/runs/{id}/logs/stream` — server-sent events, one log line per
      event, closes when run reaches terminal state.
- [ ] Tests: stream yields lines, closes on completion.

#### Phase 3 — Python client package (`client/`)

- [ ] `client/flowframe_client/__init__.py` — `FlowFrame`, `AsyncFlowFrame`.
- [ ] Methods: `run()`, `get_run()`, `list_runs()`, `get_flow()`, `list_flows()`.
- [ ] `run(stream_logs=True)` consumes the SSE stream and yields log lines.
- [ ] `client/pyproject.toml` — separate package, depends only on `httpx`.
- [ ] Tests: mocked server, sync + async paths.

#### Phase 4 — Docs

- [ ] `docs/guide/sdk.md` — install, connect, trigger a run, stream logs,
      Airflow/Prefect example snippets.
- [ ] `docs/guide/webhook.md` — configure the secret, curl example, GitHub
      Actions example.
- [ ] Sidebar entries in `.vitepress/config.ts`.
