# Maintainers

This file documents how Ciaren is maintained and how project decisions are
made as the contributor base grows.

## Current Maintainer

- Rodrigo Arenas — GitHub: [@rodrigo-arenas](https://github.com/rodrigo-arenas)

## Maintainer Responsibilities

- Triage new issues and route questions to Discussions when appropriate.
- Keep `main` stable and releasable at all times via CI — it's the only integration branch.
- Review pull requests for correctness, tests, security, maintainability, and
  fit with the local-first product scope.
- Keep public documentation aligned with implemented behavior.
- Apply security fixes and coordinate responsible disclosure.

## Review Policy

- Pull requests should target `main`.
- Maintainers may close duplicate, stale, unsupported, or out-of-scope issues.
- Large features, breaking changes, plugin API changes, and security-sensitive
  changes should have an accepted issue or discussion before implementation.
- New contributors are encouraged to start with focused fixes, docs, tests, or
  `good-first-issue` tasks.

## Branch Protection

See [CONTRIBUTING.md#-branching-strategy](CONTRIBUTING.md#-branching-strategy)
for the contributor-facing branch diagram. This section covers who can push
where and what GitHub branch protection should enforce.

| Branch | Direct pushes | Required for merge | Force-push / delete |
|---|---|---|---|
| `main` | Nobody — PR only, from `feature/*`/`fix/*`/`docs/*`/`chore/*` | Passing CI (all workflows), 1 approving review from a CODEOWNER, branch up to date with `main` | Blocked |
| `release/x.y` | Maintainers, via PR (cherry-picks from `main`) | Passing CI | Blocked while a version is still supported |
| `feature/*`, `fix/*`, `docs/*`, `chore/*` | Anyone, on their own branch/fork | N/A | Allowed — contributor's own branch |

**Release flow:** every merge to `main` goes through the full CI suite, so
`main` is releasable at any point — tag directly from `main` when cutting a
release (see [Versioning and Tags](#versioning-and-tags)). There's no
intermediate integration branch to promote through.

**Patching an older release:** if `main` has moved on but an already-shipped
minor version still needs a fix, cut `release/x.y` from that version's tag,
cherry-pick the fix (and its tests) from `main`, then tag a patch release from
the branch. This is the same pattern Airflow (`vX-Y-stable`) and MLflow
(`branch-2.x`) use to keep old versions maintainable without blocking `main`.
Ciaren doesn't have supported parallel versions yet, so you likely won't need
this until there's a real backport request.

## Release Policy

Ciaren is currently alpha software. Releases should include:

- A short changelog or release notes.
- Passing CI for backend, frontend, docs, packaging, and security checks.
- Clear notes for breaking changes, migration steps, or known limitations.

### Versioning and Tags

- Pre-1.0, versions are `0.MINOR.PATCH` with an `-alpha`/`-beta` suffix as
  needed (e.g. `0.1.0-alpha`); breaking changes can happen between them.
  Semantic versioning applies strictly from `1.0.0` onward.
- Two packages are versioned in lockstep: `backend/pyproject.toml` (`ciaren`)
  and `client/pyproject.toml` (`ciaren-client`). Bump both together before
  tagging — the `Package` workflow verifies each independently against the
  tag and fails the corresponding build job if either is out of sync.
- Cutting a release: on `main`, bump both `pyproject.toml` versions, update
  `CHANGELOG.md`, then push a bare `X.Y.Z` tag (e.g. `0.1.0`,
  or a pre-release like `0.1.0-alpha.1`) on `main` — **no `v` prefix**; the
  `Package` workflow's tag trigger only matches the unprefixed pattern. The
  tag builds both wheels/sdists and publishes both to PyPI via trusted
  publishing (OIDC), no API token needed.
- PyPI trusted publishing must be configured once per package on pypi.org
  (Owner `ciaren-labs`, Repository `Ciaren`, Workflow `package.yml`,
  Environment `pypi` for `ciaren` / `pypi-client` for `ciaren-client`) before
  the first tag push — until then, `publish-server`/`publish-client` will
  fail with an OIDC/permission error even though the build jobs succeed.

## Becoming a Maintainer

Maintainer access may be granted to contributors who consistently make high
quality contributions, review others' work constructively, understand the
project's security posture, and help keep the community healthy.
