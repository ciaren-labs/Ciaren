# Changelog

All notable changes to Ciaren will be documented in this file.

Ciaren follows the spirit of [Keep a Changelog](https://keepachangelog.com/)
and uses semantic versioning once public releases begin. Until the first stable
release, breaking changes may still happen between alpha versions.

## [Unreleased]

### Added

- **Chart nodes** — a new **Charts** palette category with eight pass-through
  nodes (bar — stackable and horizontal —, line, area, scatter, pie, histogram,
  box plot, correlation heatmap). Each computes its chart over the full run
  data at run time and stores a compact artifact, so the run inspector renders
  instantly and reflects every row processed (editor previews stay
  sample-based). Supports an **Export PNG** button and an optional per-node
  title; a flow can end in a chart node without a file output. Artifacts are
  size-capped (top-N categories with a re-aggregated "Other" bucket, point/series
  caps, label truncation) and were hardened against data-driven edge cases via
  independent audit.
- **Exported code reads like hand-written code, verified equivalent to the
  app** — keyword `assign(col=…)` instead of `**{…}` dicts, explicit
  `fillna({...})`, `df.eval(...)`, `.query(...)` filters, `np.select`
  conditional columns, chainable `.loc[lambda _d: …]` filters/calculated
  columns, and consecutive single-variable steps fused into fluent method
  chains (short runs on one line, longer ones one call per line). A straight
  flow reuses one dataframe variable (`df_1 = df_1.dropna().head(5)`) instead
  of minting a new one per step; branching steps (fan-outs, join inputs) keep
  their own variable. Requires polars `>=1.21` (rolling windows use
  `min_samples`). A new pandas/polars, eager/lazy equivalence harness verifies
  every emitted snippet produces exactly the same result as the in-app run.
- **Import options with auto-detection** — European Excel exports (semicolon
  separator, Latin-1/Windows-1252 encoding, decimal commas) and multi-sheet
  workbooks just work: CSV/TSV dialect is auto-detected at upload, an "Import
  options" row overrides it explicitly, the stored copy is normalized so both
  engines read exactly what the upload showed, and exported scripts reproduce
  the original file's dialect.
- **Failure notifications** — set `CIAREN_NOTIFY_WEBHOOK_URL` and Ciaren POSTs
  a JSON alert when a run fails or a schedule auto-disables (optional
  `CIAREN_NOTIFY_WEBHOOK_SECRET` sent as `X-Ciaren-Secret`). Delivery is
  fire-and-forget with a hard timeout, refuses redirects, and can never affect
  the run itself.
- **Cancel a running run** — POST `/runs/{id}/cancel` and a Stop button on the
  run page. Thread mode stops cooperatively at the next node boundary; process
  mode abandons the worker like the timeout path. Cancelled is a distinct
  status: it doesn't alert, and doesn't count toward schedule auto-disable.
- **Duplicate flows and copy/paste nodes** — a Duplicate action on flow
  cards/rows copies the definition (graph, parameters, engine — not schedules
  or run history), and the editor supports Ctrl/Cmd+C/V/D for nodes with the
  edges between them, fresh ids, and one undo step per paste.
- **`ciaren-client` plugin license/uninstall methods** — the Python SDK now
  wraps `activate_plugin_license`, `remove_plugin_license`, and
  `uninstall_plugin` (sync and async), matching the server and web UI.
- **Plugin API (`0.1.0-alpha.1`)** — the initial plugin contract surface,
  version-gated: a manifest declares the `api_version` it targets, checked
  against the backend's `PLUGIN_API_VERSION` before any plugin code imports,
  with mismatches reported in `/api/plugins/diagnostics` (see
  [Contract versioning](docs/specs/plugin-manifest.md#contract-versioning)).
  Plugins can contribute:
  - **ML model types** via `ModelProvider` — appear in the core Train nodes'
    model picker, train, log to MLflow, and export code through the core
    pipeline; declared hyperparameter defaults apply automatically, and
    declared `import_lines` are used for the estimator import in exported
    scripts.
  - **Typed model references** (`ModelRef`) — plugin train nodes declare
    `model` output ports honored by graph validation, the executor, and both
    code generators, persisting fitted models through a permission-gated,
    MLflow-backed `ModelStore` (`NodeContext.models`). Logged references
    capture the full training config so core Cross-Validate can rebuild
    plugin-trained estimators.
  - **Executable connectors** (`ConnectorRuntime`) — back the connections API
    and SQL/storage flow nodes, with the SSRF guard applied before any plugin
    runtime call and env-var-only secrets resolved per call.
  - **Schema-driven forms** (`config_schema` / `hyperparameter_schema`) —
    render real sidebar/connection forms, falling back to fields inferred from
    a node's default config.
  - Model loading is enforced-permission gated (`local_model_load` /
    `joblib_load` plus artifact-root confinement; pickles always refused).
- **Built-in REST API connector**: read HTTP JSON/CSV endpoints like database
  tables — auth (none / API-key header / bearer / basic, secret from an env
  var), custom headers, default query params, endpoints-as-tables, response
  format + records path, page-number pagination with a page cap, timeout, and
  TLS verification. Endpoints read through SQL Input; API connections are
  read-only, SSRF-guarded, and size-capped.
- The MLP Classifier example plugin (0.2.0) demonstrates both ML extension
  paths and ships signed in the bundled Explore catalog.
- New docs: ML Model Plugins and Connector Plugins guides, plus
  model-reference and plugin-connector sections in the ML and Connections
  guides.
- Developer Certificate of Origin (DCO) policy: contributors must sign off
  commits (`git commit -s`), enforced by CI (`.github/workflows/dco.yml`) and
  a Preflight checkbox on the PR template.
- Versioning and release-tag guidance in `MAINTAINERS.md` (alpha semver,
  unprefixed `X.Y.Z` tag convention, PyPI trusted publishing on tag push for
  both `ciaren` and `ciaren-client`).
- `development` integration branch and `release/x.y.z`/`hotfix/*` branch
  types, matching the branching strategy in `CONTRIBUTING.md`/`MAINTAINERS.md`.
- Public GitHub issue templates, pull request template, CODEOWNERS, support
  guidance, maintainer guidance, and community Discussions.
- Open-core positioning across public documentation: Ciaren Core remains open
  and useful, while premium plugins and hosted services can be commercial.
- Dual licensing documentation: Ciaren Core is AGPL-3.0-only, and the public
  Plugin API/SDK in `backend/app/plugin_api/` is Apache-2.0.
- Local-only Claude context guidance via ignored `local.claude.md`.
- Docker and Docker Compose documentation for single-container
  local/self-hosted use.

### Changed

- **Stricter flow-parameter names** — parameter names may no longer start
  with an underscore (reserved for generated-code helper temps) or match a
  generated dataframe variable (`df_1`, `df_2`, …); either would be silently
  clobbered in exported scripts. The editor rejects these (and Python
  keywords) inline. Existing flows with such names keep loading but fail
  save/run/import with a clear message.
- **Breaking: plugin commands moved to a new `ciaren-plugin` console script.**
  `ciaren plugin {list,install,uninstall,verify,enable,disable,keygen,pack,
  manifest,sign,search,index,license,licenses}` are now top-level subcommands
  of `ciaren-plugin` (e.g. `ciaren plugin install x.ciarenplugin` becomes
  `ciaren-plugin install x.ciarenplugin`) — same distribution, same install,
  just a separate entry point so the everyday `ciaren` CLI stays free of the
  plugin install/authoring surface. The old `ciaren plugin ...` form prints a
  pointer to the new command. See the
  [Plugin CLI Reference](docs/plugins/cli-reference.md).
- README now starts with a demo-first public launch flow, badges, screenshot,
  quick-start instructions, and contributor paths.
- GitHub repository metadata now presents Ciaren as a data and ML workflow
  platform, not only a visual ETL tool.
- Docker image metadata now uses the core AGPL license and aligns with the
  `ciaren db upgrade` + `ciaren serve` CLI path.
- `all-connectors` now includes `asyncpg` so PostgreSQL app database URLs work
  with `postgresql+asyncpg://`.
- scikit-learn, MLflow, and joblib are now core dependencies — `pip install
  ciaren` alone gives you a working Machine Learning palette (train/predict/
  evaluate, MLflow tracking). The `ml` extra is narrowed to XGBoost and
  LightGBM. `CIAREN_ML_ENABLED` still exists as an on/off switch.
- Moved internal, pre-launch planning docs (`PLUGIN_ARCHITECTURE_PLAN.md`,
  `PLUGIN_MARKETPLACE_PAGE_PROPOSAL.md`) out of `docs/` into a new `internal/`
  folder, since VitePress builds every `.md` file under `docs/` into a public
  route regardless of nav linkage.

### Fixed

- **The API stays responsive during heavy work** — dataset upload
  parsing/profiling, on-demand profile backfills, run-output registration,
  SQL/storage parquet snapshots, MLflow registry calls, and plugin
  marketplace verification/hashing now run in worker threads instead of
  blocking the event loop (and the scheduler).
- **Editor: changing an input's dataset wiped valid downstream config** — each
  node is now checked against its own propagated input columns instead of the
  new dataset's raw schema, so derived columns and a join's unchanged branch
  survive a dataset swap.
- **Editor performance on large flows** — validation, column propagation, and
  edge styling re-run only when the graph's structure actually changes, and
  several quadratic graph helpers are linear now.
- **Previews are sliced, off-thread, and fail clearly** — previewing a node
  computes only that node's upstream ancestors, runs off the event loop, and
  a node failing on the user's data returns a 400 naming the node instead of
  a bare 500.
- **Flow import dropped `parameters` and `engine`** — both now survive the
  round-trip, and imported parameter specs are validated at import time.

### Security

- The connector SSRF guard also covers plugin connector **options**: any
  option carrying a URL or sitting under a host/url/endpoint-like key (e.g.
  `base_url`) is checked before the plugin runtime is invoked.
- The REST API connector's response-size cap applies cumulatively across the
  pages of one paginated read, not only per request.
- Security posture documentation notes Ciaren has not yet completed a formal
  independent third-party security audit, while keeping guidance practical
  for controlled internal workflows.
- Plugin loading enforces required plugin license metadata.

### Known Limitations

- Ciaren is alpha software; APIs, data models, and generated code may change
  before a stable release.
- The project is not a distributed or streaming data engine.

## [0.1.0-alpha] - Pending

Initial public alpha release candidate.
