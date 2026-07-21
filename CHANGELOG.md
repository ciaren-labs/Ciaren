# Changelog

All notable changes to Ciaren will be documented in this file.

Ciaren follows the spirit of [Keep a Changelog](https://keepachangelog.com/)
and uses semantic versioning. Until the first stable release (`1.0.0`),
breaking changes may still happen between `0.x` releases.

## [Unreleased]

## [0.2.0] - 2026-07-20

A repo-wide correctness and hardening pass from an internal audit. Most of it is
straightforward bug fixing, but a few changes alter results or reject input that
previously passed — read **Breaking changes** before upgrading.

### Breaking changes

- **`groupByAggregate` rejects aggregations with no exact polars equivalent**
  (`sem`, `skew`, `kurt`, `size`, `mad`). These previously ran on the pandas
  backend and failed or silently differed elsewhere. *Migration:* switch to a
  supported aggregation, or compute the statistic downstream in a
  `pythonTransform` node.
- **polars `first` / `last` / `nunique` now skip nulls, matching pandas.**
  Groups containing nulls produce different (now correct and engine-consistent)
  values. *Migration:* re-run affected flows; polars results now agree with the
  pandas backend and with the exported code.
- **`concatRows` on polars unions mismatched columns** and null-fills, instead
  of raising. Flows that previously errored now succeed. *Migration:* none.
- **`GET /api/datasets` and `GET /api/flows` return at most 500 rows** by
  default. *Migration:* none for the UI; API consumers that relied on an
  unbounded list should expect truncation until `limit`/`offset` query
  parameters land.
- **A Train node whose model fails to save now fails the run** instead of
  reporting success with an unusable model reference. *Migration:* none — the
  run was already broken downstream; the failure is now visible.
- **Run creation rejects an unknown or cross-project `input_dataset_id`**
  (404 / 400). *Migration:* pass a dataset that exists in the flow's project,
  or omit the field.
- **"Default" is a reserved project name** — creating or renaming a project to
  it returns 400. *Migration:* pick another name.
- **Plugins are re-verified at load.** An installed plugin whose files were
  modified on disk after installation is refused (*migration:* reinstall it to
  re-pin the baseline); an install whose id case-collides with an existing
  plugin is rejected; a plugin whose metadata id differs from its manifest id
  is refused; and a node's declared `provider` is forced to the owning plugin's
  id.
- **Hardened connector mode** (`CIAREN_CONNECTOR_BLOCK_PRIVATE_HOSTS=true`) now
  rejects multi-host / URI-style hostnames (e.g. a comma-separated libpq seed
  list) and refuses `verify_tls: false`. *Migration:* use a single plain
  hostname per connection and keep TLS verification on, or leave the guard off.
- **`pythonTransform` strict mode** (`CIAREN_PYTHON_TRANSFORM_STRICT=true`)
  blocks additional capability modules (`io`, `tempfile`, `socket`, `pickle`,
  …). Imports that are allowed now genuinely work at runtime, where they
  previously failed with an opaque error.

### Security

- Connector SSRF guard now fails closed on multi-host / URI-style hostnames
  (which drivers could expand into a seed list or full URI) and blocks the
  NAT64 range that maps to the cloud metadata endpoint.
- The REST connector re-validates every HTTP redirect hop against the SSRF
  guard, rejects non-`http(s)` redirect targets, refuses to disable TLS
  verification in hardened mode, and no longer forwards `Authorization` /
  API-key headers when a redirect crosses to a different host.
- Marketplace artifact resolution is confined for untrusted (URL-shaped) index
  sources — `file://`, absolute, and `..` paths are rejected — ahead of any
  hosted plugin index.
- Plugins: code integrity is now verified at load (previously only the manifest
  was hashed), a planted or altered bytecode cache can no longer execute in
  place of trusted code, a node's `provider` is bound to its owning plugin, and
  an install whose id case-collides with an existing plugin is rejected.
- SQLite foreign-key enforcement is enabled; the `/api/settings/webhook` auth
  exemption is scoped to `GET`; `pythonTransform` strict mode blocks additional
  capability modules and frame/traceback traversal.
- CI: all GitHub Actions are pinned to commit SHAs (including the OIDC PyPI
  publish jobs), and `API_TOKEN` now documents the need for a long,
  high-entropy value.

### Fixed

- Projects: creating or renaming a project to the reserved name "Default", or
  deleting a project that holds a dataset whose name also exists in the default
  project, no longer returns a 500.
- A `PUT /api/flows` with an explicit `null` project id now moves the flow to
  the default project instead of erroring; an impossible-but-valid cron
  expression (e.g. Feb 30) now returns a validation error instead of a 500.
- Scheduler: daily schedules no longer fire twice during the DST fall-back
  hour; a concurrent user edit is no longer overwritten by a just-finished run;
  a manual "Run now" can no longer start a second concurrent run of a flow the
  scheduler is already running.
- Engine: `groupByAggregate` and `concatRows` now produce identical results on
  the pandas backend, the polars backend, and the exported code (previously a
  config valid on one could fail or differ on another).
- ML: a Train node whose model fails to save now fails clearly instead of
  reporting success with an unusable model; prediction aligns feature columns
  and warns before overwriting an existing column; training hyperparameters are
  bounded to prevent a runaway fit.
- Frontend: file downloads work when an `API_TOKEN` is configured; the flow
  editor warns before discarding unsaved changes; storage-restricted browser
  contexts no longer crash the editor; the "not authorized" message points to
  the real `?api_token=` mechanism.
- Database: networked Postgres/MySQL engines use connection health checks
  (`pool_pre_ping`) so a stale pooled connection no longer surfaces as a 500,
  and startup no longer runs best-effort column patching on Alembic-managed
  databases.
- Listing datasets no longer loads every version of every dataset into memory —
  the latest version and version count come from an aggregate query, so a
  workspace with a long run history stays responsive.

## [0.1.0] - 2026-07-14

First public release of Ciaren — a local-first visual builder for data and ML
workflows that exports clean, readable pandas/polars Python. This is alpha
software: APIs, data models, and generated code may still change before a
stable `1.0`.

### Visual builder

- 80 nodes across 9 categories — inputs, cleaning, columns, reshape,
  analytics, data quality, charts, machine learning, and outputs — including
  8 chart nodes (bar, line, area, scatter, pie, histogram, box plot,
  correlation heatmap) that render instantly from a compact run artifact and
  support one-click PNG export.
- File, SQL, and cloud-storage I/O (S3, GCS, Azure Blob, Snowflake) plus a
  built-in, read-only REST API connector (auth, custom headers, pagination,
  SSRF-guarded).
- Per-node data preview, undo/redo, duplicate flows, and copy/paste nodes
  with their connecting edges.
- Import options with auto-detection — CSV/TSV dialect, encoding, and
  multi-sheet Excel workbooks are detected on upload, with an explicit
  override always available.

### Execution and code export

- Dual-engine execution — **polars** (default) or **pandas**, selectable per
  run.
- Exported Python reads like hand-written code (keyword `assign()`, chainable
  `.loc[lambda _d: …]` filters, fused method chains, reused dataframe
  variables on straight-line flows) and is verified equivalent to the in-app
  run by an automated pandas/polars, eager/lazy equivalence harness.
- Cancel a running run from the UI or API; optional failure webhook
  notifications when a run fails or a schedule auto-disables.

### Data quality and Machine Learning

- Data contract nodes: assert not-null, unique, value range, row count, and
  arbitrary expressions.
- Built-in ML: split, feature engineering, train, predict, and evaluate
  nodes, with MLflow tracking and a Models page. `pip install ciaren` alone
  gives a working ML palette (scikit-learn, MLflow, and joblib are core
  dependencies); XGBoost and LightGBM are available via the `ml` extra.

### Scheduling and automation

- Built-in cron scheduler with retries, catch-up, and auto-disable after
  repeated failures.
- REST, CLI, and webhook-based ways to trigger flows outside the UI.

### Plugin platform

- A versioned, contract-first Plugin API/SDK (`backend/app/plugin_api/`,
  Apache-2.0) — plugins can contribute transformation nodes, ML model types,
  connectors, and schema-driven config forms without forking the core.
- Signed `.ciarenplugin` packaging, local and entry-point discovery, and
  permission-gated model loading.
- `ciaren-client` — a Python SDK for scripting against the server (flows,
  runs, datasets, plugins).
- Two documented example plugins (hello-world node, MLP classifier) covering
  both extension paths.

### Documentation and project

- Full documentation site: getting started, guides, transformation
  reference, recipes, plugin authoring, and API reference.
- Contributing guide, Developer Certificate of Origin (DCO) policy, issue and
  PR templates, and public GitHub Discussions.
- Dual licensing: Ciaren Core is AGPL-3.0-only; the public Plugin API/SDK is
  Apache-2.0 so plugin authors can choose their own license.
- Docker and Docker Compose support for single-container local/self-hosted
  use.

### Security

- pip-audit and npm audit run on every push to `main` and fail CI on new
  high/critical advisories in pinned dependencies.

### Known limitations

- Ciaren is alpha software; recommended for controlled internal workflows
  while the project matures, not yet for critical production jobs.
- Not a distributed or streaming data engine — batch-style local and
  self-hosted workflows are the product center.
- Has not yet completed a formal independent third-party security audit.
