# Changelog

All notable changes to Ciaren will be documented in this file.

Ciaren follows the spirit of [Keep a Changelog](https://keepachangelog.com/)
and uses semantic versioning. Until the first stable release (`1.0.0`),
breaking changes may still happen between `0.x` releases.

## [Unreleased]

## [0.1.0-alpha.1] - 2026-07-14

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

### Known limitations

- Ciaren is alpha software; recommended for controlled internal workflows
  while the project matures, not yet for critical production jobs.
- Not a distributed or streaming data engine — batch-style local and
  self-hosted workflows are the product center.
- Has not yet completed a formal independent third-party security audit.
