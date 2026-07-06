# Changelog

All notable changes to Ciaren will be documented in this file.

Ciaren follows the spirit of [Keep a Changelog](https://keepachangelog.com/)
and uses semantic versioning once public releases begin. Until the first stable
release, breaking changes may still happen between alpha versions.

## [Unreleased]

### Added

- **Chart nodes** — a new **Charts** palette category with eight nodes (bar —
  stackable and horizontal —, line, area, scatter, pie, histogram, box plot,
  correlation heatmap). Each is a pass-through that computes its chart over the
  **full run data** at run time and stores a compact artifact on the run, so
  opening a run renders the chart instantly and reflects every row that run
  processed (the editor's preview charts remain sample-based). Charts render in
  the run inspector with an **Export PNG** button (title + legend drawn onto
  the image) and support an optional per-node chart title. A flow ending in a
  chart node is complete without a file output. Artifacts are size-capped
  (top-N categories with an exactly re-aggregated "Other" bucket, point/series
  caps, label truncation) and were hardened by an independent audit against
  data-driven edge cases (categories literally named "Other", series named
  "label"/"x", ±inf values, high-cardinality axes).
- **Exports now read like hand-written code** — every node emitter was
  reworked to produce what a person would type: keyword `assign(col=…)`
  instead of `**{…}` dicts, `fillna({'age': df['age'].median()})` instead
  of guarded comprehensions for explicitly picked columns,
  `df.eval('total = price * quantity')`, `.query(…)` filters, `np.select`
  conditional columns, one-statement casts, `df.round({…})`, joins as
  `left.merge(right, on='id', how='left')`, and window/rolling/difference
  nodes as a single chainable expression (pandas index alignment; polars
  `.over(partition, order_by=…)`). Defaults the libraries already assume
  are no longer spelled out. A ~40-case extension of the equivalence
  harness proves the cleaner scripts still compute exactly what the app
  runs, and the docs' generated-code snippets, example walkthroughs, and
  the export GIF were regenerated from the new output.
- **Import options with auto-detection** — European Excel exports (semicolon
  separator, Latin-1/Windows-1252 encoding, decimal commas) and multi-sheet
  workbooks now just work: CSV/TSV dialect is auto-detected at upload, an
  "Import options" row overrides it explicitly (separator, encoding, decimal
  mark, Excel sheet by name or index), the stored copy is normalized so both
  engines always read exactly what the upload showed, and exported Python
  scripts reproduce the original file's dialect.
- **Failure notifications** — set `CIAREN_NOTIFY_WEBHOOK_URL` and Ciaren
  POSTs a JSON alert when a run fails or a schedule auto-disables (optional
  `CIAREN_NOTIFY_WEBHOOK_SECRET` is sent as `X-Ciaren-Secret`). Delivery is
  fire-and-forget with a hard timeout, refuses redirects, and can never
  affect the run itself.
- **Cancel a running run** — POST `/runs/{id}/cancel` and a Stop button on
  the run page. Thread mode stops cooperatively at the next node boundary
  (the in-flight node finishes, the rest are skipped, no outputs written);
  process mode abandons the worker like the timeout path. Cancelled is a
  distinct run status: it doesn't alert, and a cancelled scheduled run
  doesn't count toward auto-disable.
- **Duplicate flows and copy/paste nodes** — a Duplicate action on flow
  cards/rows copies the definition (graph, parameters, engine — not
  schedules or run history), and the editor supports Ctrl/Cmd+C/V/D for
  nodes with the edges between them, fresh ids, and one undo step per paste.
- **Chainable pandas filters and calculated columns in exported code** — the
  pandas emitters for Filter Rows, Filter by Expression, and Calculated
  Column now use the idiomatic callable forms (`.loc[lambda _d: …]`,
  `assign(total=lambda _d: …)`), so a straight pandas flow exports as a
  single fluent chain end to end, just like polars.
- **Fluent method chains in exported code** — both code generators now merge
  consecutive single-variable steps of a linear flow into one chained
  expression, the way a person would write it: short runs on one line
  (`df_1 = df_1.dropna().head(5)`), longer ones in parenthesized fluent style
  with one call per line (`df_1 = (\n    df_1.filter(...)\n    .group_by(...)…`).
  The fusion pass is AST-validated and conservative: statements whose
  right-hand side references the running variable more than once (e.g. pandas
  boolean masks) may open a chain but never continue one, and joins, fan-outs,
  `del` statements (memory-freeing mode), comments, and multi-line snippets
  keep their exact previous shape and semantics.
- **`ciaren-client` plugin license/uninstall methods** — the Python SDK was
  missing wrappers for three plugin endpoints the server and web UI already
  exposed: `activate_plugin_license`, `remove_plugin_license`, and
  `uninstall_plugin` (sync and async). Filled in alongside the license-token
  and install-compatibility work below so the SDK stays a complete thin
  client over the REST API.
- **Plugin-contract version gating** — a plugin manifest now declares the
  plugin-API contract it targets via `api_version` (distinct from the plugin's own
  `version` and from `ciaren` app compatibility). The loader checks it against the
  backend's `PLUGIN_API_VERSION` (now `0.1.0-alpha.1`) **before importing any plugin
  code**, so a plugin built for an incompatible contract is cleanly rejected and
  reported in `/api/plugins/diagnostics` instead of failing with an opaque import
  error. Pre-1.0 the contract makes **no** backward-compatibility promise — a plugin
  must target the backend's exact `major.minor`; from 1.0 on, minors become additive.
  The backend's contract version is exposed as `plugin_api_version` in diagnostics,
  and `ciaren plugin manifest` stamps `api_version` (override with `--api-version`).
  See [Contract versioning](docs/specs/plugin-manifest.md#contract-versioning).
- **Plugin API (`0.1.0-alpha.1`)** — the initial plugin contract surface:
  - **Plugin ML model types** — a `ModelProvider` contributes trainable model
    types that appear inside the core Train nodes' model picker and train, log
    to MLflow, and export code through the core pipeline.
  - **Typed model references** — `ModelRef` freezes the model-wire frame layout
    as a public contract; plugin train nodes can declare `model` output ports
    that backend graph validation, the executor, and both code generators now
    honor, and persist fitted models through a permission-gated, MLflow-backed
    `ModelStore` (`NodeContext.models`) instead of passing raw estimators.
  - **Executable plugin connectors** — `ConnectorRuntime` implementations back
    the connections API (test, list tables/objects) and the SQL/storage flow
    nodes (read/write with parquet snapshots), with the SSRF guard applied
    before any plugin runtime call and env-var-only secrets resolved per call.
  - **Schema-driven forms** — `config_schema` on node and connector specs (and
    `hyperparameter_schema` on model types) renders real sidebar and connection
    forms; plugin nodes without a schema get fields inferred from their default
    config instead of "No configuration for this node type".
  - Model loading by plugins is enforced-permission gated (`local_model_load` /
    `joblib_load` plus artifact-root confinement; pickles always refused).
- **Built-in REST API connector**: read HTTP JSON/CSV endpoints like database
  tables, with the connection options commercial tools offer — auth (none /
  API-key header / bearer / basic, secret from an env var), custom headers,
  default query params, endpoints-as-tables, response format + records path,
  page-number pagination with a page cap, timeout, and TLS verification.
  Endpoints read through SQL Input (including a custom-request-path mode);
  API connections are read-only, SSRF-guarded, and size-capped.
- The MLP Classifier example plugin (0.2.0) now demonstrates both ML extension
  paths and ships signed in the bundled Explore catalog.
- New docs: ML Model Plugins and Connector Plugins guides, plus model-reference
  and plugin-connector sections in the ML and Connections guides.
- Developer Certificate of Origin (DCO) policy: contributors must sign off
  commits (`git commit -s`), enforced by a new CI check
  (`.github/workflows/dco.yml`) and a Preflight checkbox on the PR template.
- Versioning and release-tag guidance in `MAINTAINERS.md` (alpha semver,
  `vX.Y.Z` tag convention, and a note that PyPI publishing is not yet
  automated).
- `development` integration branch, matching the branching strategy already
  documented in `CONTRIBUTING.md`/`MAINTAINERS.md` and already targeted by
  CI workflow triggers.
- `release/x.y.z` and `hotfix/*` branch types added to the branching strategy,
  plus a new `MAINTAINERS.md#branch-protection` section documenting who can
  push where and the GitHub branch protection each branch should have.
- Public GitHub issue templates, pull request template, CODEOWNERS, support
  guidance, maintainer guidance, and community Discussions.
- Open-core positioning across public documentation: Ciaren Core remains open
  and useful, while premium plugins and hosted services can be commercial.
- Dual licensing documentation: Ciaren Core is AGPL-3.0-only, and the public
  Plugin API/SDK in `backend/app/plugin_api/` is Apache-2.0.
- Local-only Claude context guidance via ignored `local.claude.md`.
- Docker and Docker Compose documentation for single-container local/self-hosted
  use.

### Changed

- **Stricter flow-parameter names** — parameter names may no longer start
  with an underscore (the code generators reserve the `_` namespace for
  their helper temps) or match a generated dataframe variable (`df_1`,
  `df_2`, …); either would be silently clobbered in exported scripts. The
  editor rejects these (and Python keywords) inline. Existing flows with
  such names keep loading but fail save/run/import with a clear message.
- **Breaking: plugin commands moved to a new `ciaren-plugin` console script.**
  `ciaren plugin {list,install,uninstall,verify,enable,disable,keygen,pack,
  manifest,sign,search,index,license,licenses}` are now top-level subcommands
  of `ciaren-plugin` (e.g. `ciaren plugin install x.ciarenplugin` becomes
  `ciaren-plugin install x.ciarenplugin`) — same distribution, same install,
  just a separate entry point so the everyday `ciaren` CLI (`serve`/`init`/
  `info`/`check`/`db`/`transformations`/`flow`) stays free of the plugin
  install/authoring surface. Running the old `ciaren plugin ...` form prints
  a pointer to the new command instead of an "invalid choice" error. See the
  [Plugin CLI Reference](docs/plugins/cli-reference.md).
- Exported Python scripts now reuse a single dataframe variable along straight
  chains (`df_1 = df_1.dropna()` instead of minting `df_2`, `df_3`, …), reading
  like hand-written code. Steps feeding several consumers (fan-outs, join
  inputs) keep their own variable. The polars floor rose from `>=1.0` to
  `>=1.21` (rolling windows now use the `min_samples` kwarg that replaced the
  deprecated `min_periods`).
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
  evaluate, MLflow tracking). The `ml` extra is narrowed to just XGBoost and
  LightGBM (`pip install "ciaren[ml]"`), since those are the two
  native-compiled, optional model choices. `CIAREN_ML_ENABLED` still exists as
  an on/off switch for the feature as a whole.
- Moved internal, pre-launch planning docs (`PLUGIN_ARCHITECTURE_PLAN.md`,
  `PLUGIN_MARKETPLACE_PAGE_PROPOSAL.md`) out of `docs/` into a new `internal/`
  folder, since VitePress builds every `.md` file under `docs/` into a public
  route regardless of nav linkage.

### Fixed

- **The API stays responsive during heavy work** — dataset upload parsing
  and profiling (up to the upload size limit), on-demand profile backfills,
  run-output registration, SQL/storage parquet snapshots, MLflow registry
  calls, and plugin marketplace verification/hashing all ran on the event
  loop, freezing every other request (and the scheduler) while they worked.
  They now run in worker threads; runs and previews already did. A
  regression test asserts /health answers while a slow upload parses.
- **Editor: changing an input's dataset wiped valid downstream config** — the
  stale-column cleanup validated every downstream reference against the new
  dataset's raw schema, clearing references to derived columns (Calculated
  Column and friends) and to a join's other, unchanged branch even when the
  schema was identical. Each node is now checked against its own propagated
  input columns, column propagation covers every column-adding transform,
  and unknown schemas are left alone instead of wiped.
- **Editor performance on large flows** — validation, column propagation, and
  edge styling no longer recompute on every drag frame (they re-run only
  when the graph's structure actually changes), and several quadratic graph
  helpers are linear now.
- **Previews are sliced, off-thread, and fail clearly** — previewing a node
  now computes only that node's upstream ancestors (a failing assertion or a
  typo'd column on an unrelated branch no longer breaks it), runs off the
  event loop so a heavy preview can't stall the API, and a node failing on
  the user's data returns a 400 naming the node instead of a bare 500.
- **Flow import dropped `parameters` and `engine`** — importing an exported
  flow document rebuilt only nodes and edges, silently losing the flow's
  declared parameters and its pandas/polars engine choice. Both now survive
  the round-trip, and imported parameter specs are validated at import time
  (clear 400) instead of failing at first run.
- **Exported fill-nulls scripts crashed where app runs succeeded** — the
  mean/median/mode fill strategies now skip non-applicable columns in the
  generated pandas and polars code exactly like the engines do (string
  columns for mean/median, all-null columns for mode), and tied modes now
  deterministically pick the smallest value on both engines so runs are
  reproducible.
- **Polars-lazy exports crashed for several node kinds** — three bundled demo
  flows exported lazy scripts that failed at runtime. `fillNulls`
  median/mode emitted series subscripts a `LazyFrame` doesn't support (they
  now emit pure, mode-agnostic expressions), and Remove Outliers, Bin Column,
  and all assertion nodes — which must compute concrete numbers from the
  frame — are now materialized around in lazy mode like pivot/sample already
  were. Every previously broken node kind is covered by a new lazy-vs-eager
  equivalence test, and all demo flows now generate and run in every
  engine/mode combination.
- Plugin API audit fixes (second iteration over the new extension points):
  - A plugin model type's `default_hyperparameters` were advertised in the
    catalog but never applied — an untouched hyperparameter form trained with
    `{}`. They now merge under the user's values before the builder runs, and
    surface in exported code.
  - `ModelTypeSpec.import_lines` were documented but never consumed; exported
    training scripts now use them for the estimator import when declared
    (deriving from the estimator's class module otherwise). The unused
    `seed_param` field was removed before the 1.1 contract ships.
  - Model references logged through the plugin `ModelStore` now record the
    full model-wire training config (model type, target, features,
    hyperparameters, preprocessing, seed) like core train nodes, so core
    Cross-Validate can rebuild plugin-trained estimators.
  - A required plugin connector field with a valid falsy value (`False` for a
    boolean, `0` for a number) was rejected as missing.
  - A plugin node runtime returning handles that don't match its declared
    `NodeSpec` outputs (or non-DataFrame values, or a model port without a
    model reference) now fails with a clear plugin-shaped error instead of an
    opaque engine error downstream.
  - The running-version lookup now falls back on any metadata-backend
    failure, so a source checkout without installed package metadata can
    still load plugins.

- Code export fidelity — the exported script must behave exactly like the
  in-app run, verified by a new equivalence harness that executes every
  emitted pandas/polars snippet and compares the result frame against
  `execute()` per engine:
  - Exported polars scripts crashed with `SchemaError` on date operations
    downstream of parsed dates (and vice versa): `dateDifference`,
    `extractDateParts`, `parseDates`, and `castDtypes` now dispatch on the
    column's dtype at runtime like the in-app engine does.
  - `concatRows` polars export now uses `vertical_relaxed` like the engine,
    so mixed int/float columns concatenate instead of raising.
  - `fillNulls` mode-strategy polars export no longer crashes when nulls are
    present, and leaves all-null columns untouched like the engine.
  - `filterRows` string operators stringify non-string search values like
    the engines, and the polars export uses literal (not regex) `contains`
    to match in-app behavior.
- `README.md`/`CONTRIBUTING.md` linked to a deleted root-level `architecture.md`;
  both now point to `docs/architecture/current-architecture-map.md`.
- A stale test assertion in `test_graph_validation.py` expected an old
  validation error message ("needs a trained model") after the message was
  reworded to "needs a model reference"; updated to match.
- Docker image failed to build: `hatch_metadata.py` (the custom metadata hook
  that inlines the root README as the PyPI description) wasn't copied into the
  build context, and once added, the hook's `Path(self.root).parent /
  "README.md"` lookup still failed because `.dockerignore`'s `*.md` rule
  excluded the README. Both are now copied in; verified with a local
  `docker build` + container smoke test against `/health`.
- `MAINTAINERS.md` documented pushing a `vX.Y.Z` release tag, but
  `package.yml`'s tag trigger only matches the unprefixed `X.Y.Z` pattern — a
  tag following the documented convention would never trigger a release.
  Corrected, and updated the section to reflect that PyPI publishing (added
  this cycle for both `ciaren` and `ciaren-client` via trusted publishing) is
  no longer manual.

### Security

- The connector SSRF guard now also covers plugin connector **options**: any
  option carrying a URL or sitting under a host/url/endpoint-like key (e.g.
  `base_url`) is checked before the plugin runtime is invoked, not only the
  connection's `host` column.
- The REST API connector's response-size cap now applies cumulatively across
  the pages of one paginated read, not only per request.
- Security posture documentation now says Ciaren has not yet completed a
  formal independent third-party security audit, while keeping guidance practical
  for controlled internal workflows.
- Plugin loading now enforces required plugin license metadata.

### Known Limitations

- Ciaren is alpha software; APIs, data models, and generated code may change
  before a stable release.
- Docker build verification should be run before public launch on a machine with
  Docker Desktop or Docker Engine running.
- The project is not a distributed or streaming data engine.

## [0.1.0-alpha] - Pending

Initial public alpha release candidate.
