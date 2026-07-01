# Changelog

All notable changes to FlowFrame will be documented in this file.

FlowFrame follows the spirit of [Keep a Changelog](https://keepachangelog.com/)
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
- Public GitHub issue templates, pull request template, CODEOWNERS, support
  guidance, maintainer guidance, and community Discussions.
- Open-core positioning across public documentation: FlowFrame Core remains open
  and useful, while premium plugins and hosted services can be commercial.
- Dual licensing documentation: FlowFrame Core is AGPL-3.0-only, and the public
  Plugin API/SDK in `backend/app/plugin_api/` is Apache-2.0.
- Local-only Claude context guidance via ignored `local.claude.md`.
- Docker and Docker Compose documentation for single-container local/self-hosted
  use.

### Changed

- README now starts with a demo-first public launch flow, badges, screenshot,
  quick-start instructions, and contributor paths.
- GitHub repository metadata now presents FlowFrame as a data and ML workflow
  platform, not only a visual ETL tool.
- Docker image metadata now uses the core AGPL license and aligns with the
  `flowframe db upgrade` + `flowframe serve` CLI path.
- `all-connectors` now includes `asyncpg` so PostgreSQL app database URLs work
  with `postgresql+asyncpg://`.

### Fixed

- `README.md`/`CONTRIBUTING.md` linked to a deleted root-level `architecture.md`;
  both now point to `docs/architecture/current-architecture-map.md`.
- A stale test assertion in `test_graph_validation.py` expected an old
  validation error message ("needs a trained model") after the message was
  reworded to "needs a model reference"; updated to match.

### Changed

- Moved internal, pre-launch planning docs (`PLUGIN_ARCHITECTURE_PLAN.md`,
  `PLUGIN_MARKETPLACE_PAGE_PROPOSAL.md`) out of `docs/` into a new `internal/`
  folder, since VitePress builds every `.md` file under `docs/` into a public
  route regardless of nav linkage.

### Security

- Security posture documentation now says FlowFrame has not yet completed a
  formal independent third-party security audit, while keeping guidance practical
  for controlled internal workflows.
- Plugin loading now enforces required plugin license metadata.

### Known Limitations

- FlowFrame is alpha software; APIs, data models, and generated code may change
  before a stable release.
- Docker build verification should be run before public launch on a machine with
  Docker Desktop or Docker Engine running.
- The project is not a distributed or streaming data engine.

## [0.1.0-alpha] - Pending

Initial public alpha release candidate.
