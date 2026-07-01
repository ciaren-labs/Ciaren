# Changelog

All notable changes to Ciaren will be documented in this file.

Ciaren follows the spirit of [Keep a Changelog](https://keepachangelog.com/)
and uses semantic versioning once public releases begin. Until the first stable
release, breaking changes may still happen between alpha versions.

## [Unreleased]

### Added

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

### Fixed

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

### Changed

- Moved internal, pre-launch planning docs (`PLUGIN_ARCHITECTURE_PLAN.md`,
  `PLUGIN_MARKETPLACE_PAGE_PROPOSAL.md`) out of `docs/` into a new `internal/`
  folder, since VitePress builds every `.md` file under `docs/` into a public
  route regardless of nav linkage.

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
