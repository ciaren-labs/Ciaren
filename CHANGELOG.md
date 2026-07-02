# Changelog

All notable changes to Ciaren will be documented in this file.

Ciaren follows the spirit of [Keep a Changelog](https://keepachangelog.com/)
and uses semantic versioning once public releases begin. Until the first stable
release, breaking changes may still happen between alpha versions.

## [Unreleased]

### Added

- **Plugin API 1.1** (additive; 1.0 plugins keep working unchanged):
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
