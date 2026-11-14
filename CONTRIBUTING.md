# Contributing to Ciaren

Thank you for your interest in Ciaren! We're excited to have you help build a local-first visual builder for data and ML workflows that exports clean Python.

This document explains how to contribute — whether you're fixing bugs, adding features, improving docs, or helping with design.

---

## ✨ What We Need

### Project Philosophy

Ciaren is an **open-core** project with a deliberately small built-in surface.
The core should stay lightweight, local-first, and easy to understand. It will
include a focused set of broadly useful connectors and transformations, but it
is not meant to collect every database, SaaS API, proprietary storage system, or
organization-specific integration.

Use the public Plugin API/SDK for long-tail integrations. If you need a niche
connector, a product-specific node, or a company-specific workflow, the expected
path is to build and maintain it as a plugin. Core changes are reserved for
capabilities that benefit many users, improve the SDK, fix bugs, or unblock
plugin authors.

### Code Contributions

- **New transformation nodes** — filters, aggregations, joins, reshaping operations
- **Bug fixes** — we track these in [Issues](https://github.com/ciaren-labs/Ciaren/issues)
- **Performance improvements** — especially in the execution engine and preview system
- **Frontend improvements** — better UX, accessibility, responsive design
- **Backend improvements** — better error handling, validation, API design
- **Plugin SDK improvements** — extension points, docs, tests, and examples that
  make community plugins easier to build

### Non-Code Contributions

- **Documentation** — tutorials, examples, troubleshooting guides
- **Testing** — try Ciaren with real datasets, report edge cases
- **Design feedback** — UI/UX improvements, workflow suggestions
- **Community** — answer questions in discussions, mentor new contributors

---

## 🌿 Branching Strategy

Ciaren uses **trunk-based development**, the same model as scikit-learn,
Apache Airflow, and MLflow: one long-lived branch, kept releasable at all
times by CI.

```
main            ← stable, continuously integrated; always releasable
  └── feature/your-feature   ← your work

release/x.y     ← cut from a released tag to backport fixes once main has
                  moved past that version (maintainers, only when needed)
```

| Branch | Purpose | Who pushes | Lives on GitHub as |
|---|---|---|---|
| `main` | Integration branch; CI runs according to workflow triggers and changed paths | Merged via PR only, from `feature/*`/`fix/*`/etc. | Protected |
| `release/x.y` | Backport bugfixes to an already-shipped minor version after `main` has moved on | Maintainers, via PR | Protected, long-lived per supported version |
| `feature/*`, `fix/*`, `docs/*`, `chore/*` | Your daily work | You (freely, usually from your fork) | Unprotected |

**The flow for most contributions:**

1. Branch off `main`
2. Open a PR targeting `main` — CI selects checks by changed paths and event.
   Backend, frontend, Docker and connector jobs have separate triggers; see
   `.github/workflows/` for the current matrices.
3. Once it's green and reviewed, it merges straight into `main`. `main` is
   tagged directly for releases — there's no separate integration branch to
   promote through first.

There is no `development` branch and no bugfix-only staging period before a
merge lands on `main` — CI on `main` is the gate. `release/x.y` branches only
get created later, and only if an older shipped version needs a patch after
`main` has already moved forward (the same pattern Airflow's `vX-Y-stable` and
MLflow's `branch-2.x` follow). You won't normally create one yourself.
Maintainer responsibilities and branch protection rules are documented in
[MAINTAINERS.md](MAINTAINERS.md#branch-protection).

---

## 🚀 Getting Started

Before starting work, check existing issues and PRs to avoid duplicate effort.
For questions, setup help, or early design ideas, use
[GitHub Discussions](https://github.com/ciaren-labs/Ciaren/discussions)
instead of opening a free-form issue.

### 1. Fork & Clone

```bash
git clone https://github.com/YOUR_USERNAME/Ciaren.git
cd Ciaren
```

### 2. Set Up Development Environment

Use Python 3.12+ and `uv`. For the frontend, use a Node version allowed by
`frontend/package.json` and tested in `.github/workflows/frontend-tests.yml`.
Run each setup block from the repository root, in a separate terminal.

#### Backend

```powershell
cd backend

# Create/sync the environment with the CI test dependencies
uv sync --all-groups --extra ml

# Run one existing test module; select the module relevant to your change
uv run --no-sync pytest tests/api/test_flows.py

# Start the source-development API (port 8055)
uv run --no-sync ciaren serve --reload
```

`uv` manages the virtual environment; manual activation is not required.
On macOS, the ML dependencies also need the OpenMP runtime (`libomp`), as
configured in `.github/workflows/backend-tests.yml`.

#### Frontend

```powershell
cd frontend

# Install the locked dependencies and enforce supported Node versions
npm ci --engine-strict

# Start dev server (port 5173)
npm run dev
```

Keep development servers in dedicated terminals and stop them, including child
processes, when finished. Agents must follow the process ownership rules in
[AGENTS.md](AGENTS.md); local Windows lifecycle helpers are not shipped in clones.

### 3. Create a Branch

Branch from `main`:

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feature/your-feature-name
```

Use descriptive branch names:

- `feature/add-pivot-transformation`
- `fix/null-handling-bug`
- `docs/setup-guide`

---

## 📝 Code Standards

### Product and Architecture Guardrails

- Ciaren is local-first visual ETL for small and medium datasets.
- Keep the core lightweight; it is not an Airflow, dbt, Spark, or SaaS replacement.
- Keep built-in connectors selective. New database, SaaS, API, or storage
  integrations should usually be plugins unless maintainers explicitly accept
  the integration as core.
- Prefer improving the Plugin API/SDK over adding long-tail integrations to the
  open core.
- The backend is the source of truth for validation, execution, persistence, and code export.
- Every visual node should map to one clear dataframe operation.
- Generated Python must be readable and runnable outside Ciaren.
- Do not document, demo, or claim a feature unless it is implemented in code.
- Avoid enterprise-only scope creep such as multi-tenant permissions, cloud sync, distributed execution, or real-time collaboration unless maintainers have accepted the proposal first.

Authoritative places to check:

- Transformations: `backend/app/engine/registry.py`
- I/O node kinds: `backend/app/engine/node_kinds.py`
- API routes: `backend/app/api/routes/`
- Frontend features: `frontend/src/features/`
- Backend architecture: `backend/app/README.md`

### Backend (Python)

- **Type hints required** — use them everywhere (`def transform(data: pd.DataFrame) -> pd.DataFrame`)
- **Lint and format with Ruff** — use the configuration in `backend/pyproject.toml`
- **Tests for new code** — especially transformations and services
- **Pydantic schemas for API inputs/outputs** — no raw dicts
- **Keep route handlers thin** — put logic in services
- **No pandas directly in routes** — encapsulate in `app/engine`

#### Example

```python
import pandas as pd
from pydantic import BaseModel, Field

class RenameColumnsConfig(BaseModel):
    mapping: dict[str, str] = Field(..., description="Old name -> New name")

def rename_columns(df: pd.DataFrame, config: RenameColumnsConfig) -> pd.DataFrame:
    return df.rename(columns=config.mapping)
```

### Frontend (TypeScript/React)

- **TypeScript always** — no `any` without a comment explaining why
- **Feature-based folder structure** — components grouped by feature, not type
- **Use TanStack Query for server state** — centralized cache management
- **Use Zustand for UI state only** — lightweight, local UI state
- **shadcn/ui for components** — consistent design system
- **Zod for form validation** — same validation as backend when possible
- **No inline styles** — use Tailwind CSS classes

### Documentation

- Keep documentation user-focused, concrete, and example-driven.
- Update docs in the same PR as user-facing behavior changes.
- For UI changes, check whether screenshots in `docs/public/screenshots/` are stale.
- Use active voice, clear headings, and tested examples.
- Every new transformation should include or update its docs page under `docs/transformations/`.
- Do not copy internal notes or tool-specific agent instructions into public docs.

---

## ✅ Testing

### Backend Tests

Run focused checks for the changed behavior and adjacent flows:

```powershell
cd backend
uv run --no-sync pytest tests/api/test_flows.py
uv run --no-sync ruff check app tests tools
uv run --no-sync ruff format --check app tests tools
uv run --no-sync mypy app
```

Replace the test path with the affected existing module. For a release, merge or
explicitly requested full run, use the sequential runner from `backend/`:

```powershell
uv run --no-sync python tools/run_tests.py --output .test-results/contribution-check
```

Choose a new, empty output directory for each run. The runner records the complete
test inventory, runs one module per process and enforces **87% combined coverage**.
Do not substitute selected modules for the full gate or run the entire backend
suite in one pytest process. Run one heavy test/build process at a time.

**Guidelines:**

- For a bug fix, demonstrate a failing regression test before applying the fix.
- Test observable behavior and relevant data edge cases using synthetic fixtures.
- Test API endpoints with isolated SQLite storage, graph validation and execution.
- For transformations, verify pandas/Polars execution and runnable code exports.
- Report commands, results and skipped checks; skips do not verify behavior.

### Connector Integration Tests

The default backend suite is **infra-free**: live connector tests self-skip
when their activating environment variables or optional drivers are absent.
Once enabled, the configured service must be available; an unreachable service
is a test failure, not a reason to assume a skip. They live in `backend/tests/integration/` under the `connectors` marker
and exercise the real driver I/O paths against local emulators. CI runs them in
the **Connectors Integration** workflow
(`.github/workflows/connectors-integration.yml`).

To run one locally: start its emulator, install the matching extra, set the
service's env var(s), then run the marked tests.

| Connector  | Emulator        | Extra   | Activating env var             |
|------------|-----------------|---------|--------------------------------|
| S3         | Moto server     | `s3`    | `CIAREN_TEST_S3_ENDPOINT`   |
| MongoDB    | `mongo`         | `mongo` | `CIAREN_TEST_MONGO_HOST`    |
| Azure Blob | Azurite         | `azure` | `CIAREN_TEST_AZURE_ENDPOINT`|
| GCS        | fake-gcs-server | `gcs`   | `STORAGE_EMULATOR_HOST`        |

Install only the extra for the connector you are checking, for example from
`backend/`:

```powershell
uv sync --all-groups --extra s3
```

Connector extras are intentionally absent from the standard backend CI setup:
some tests cover missing-driver behavior. Restore the standard environment with
`uv sync --all-groups --extra ml` before running that suite.

The following examples use PowerShell and local disposable services. Run one
connector at a time from `backend/`, installing its matching extra first. Choose
an unused container name and port; do not stop another contributor's container.
Wait for the emulator to be ready before testing. Use `docker logs <name>` to
inspect startup if necessary. Remove your container and unset its test environment
variables after the check, including when a test fails.

**S3 (Moto, matching CI):**

```powershell
docker run -d --name ciaren-test-s3 -p 9000:5000 motoserver/moto:5.2.3
$env:CIAREN_TEST_S3_ENDPOINT = "http://127.0.0.1:9000"
$env:CIAREN_TEST_S3_ACCESS_KEY = "testing"
$env:CIAREN_TEST_S3_SECRET_KEY = "testing"
uv run --no-sync pytest tests/integration/test_s3_connector.py -m connectors
docker rm -f ciaren-test-s3
Remove-Item Env:CIAREN_TEST_S3_ENDPOINT, Env:CIAREN_TEST_S3_ACCESS_KEY, Env:CIAREN_TEST_S3_SECRET_KEY
```

**MongoDB (`uv sync --all-groups --extra mongo`):**

```powershell
docker run -d --name ciaren-test-mongo -p 27017:27017 mongo:7
$env:CIAREN_TEST_MONGO_HOST = "127.0.0.1"
uv run --no-sync pytest tests/integration/test_mongo_connector.py -m connectors
docker rm -f ciaren-test-mongo
Remove-Item Env:CIAREN_TEST_MONGO_HOST
```

**Azure Blob (`uv sync --all-groups --extra azure`):**

```powershell
docker run -d --name ciaren-test-azure -p 10000:10000 mcr.microsoft.com/azure-storage/azurite azurite-blob --blobHost 0.0.0.0 --skipApiVersionCheck
$env:CIAREN_TEST_AZURE_ENDPOINT = "http://127.0.0.1:10000/devstoreaccount1"
uv run --no-sync pytest tests/integration/test_azure_connector.py -m connectors
docker rm -f ciaren-test-azure
Remove-Item Env:CIAREN_TEST_AZURE_ENDPOINT
```

**GCS (`uv sync --all-groups --extra gcs`):**

```powershell
docker run -d --name ciaren-test-gcs -p 4443:4443 fsouza/fake-gcs-server -scheme http -port 4443 -public-host 127.0.0.1:4443
$env:STORAGE_EMULATOR_HOST = "http://127.0.0.1:4443"
uv run --no-sync pytest tests/integration/test_gcs_connector.py -m connectors
docker rm -f ciaren-test-gcs
Remove-Item Env:STORAGE_EMULATOR_HOST
```

**Notes:**

- Bash equivalents and CI readiness checks are in `.github/workflows/connectors-integration.yml`.
- Azurite needs `--skipApiVersionCheck` for the SDK's newer API version.
- The example credentials are for local emulators, never production services.
- Connector coverage is uploaded separately to Codecov; this subset does not enforce the full backend coverage gate.

### Frontend Tests

```powershell
cd frontend

# Focused Vitest run; replace with the affected test file
npm test -- src/lib/__tests__/catalogMerge.test.ts

# Static checks and production build
npm run lint
npm run type-check
npm run build
```

`npm test` runs the complete frontend Vitest suite when required. There is no
`test:e2e` script in the current package. For UI changes, also verify the affected
flow in a browser, including keyboard interactions, mobile states, links and
console errors; report what you checked.

**Guidelines:**

- Test form validation and error states
- Test flow editor interactions
- Test API error handling and retries

---

## 🔄 Submitting a Pull Request

### Before You Start

1. **Check existing issues/PRs** — search [open issues](https://github.com/ciaren-labs/Ciaren/issues) to avoid duplicate work
2. **Open an issue first for big features** — [start a discussion](https://github.com/ciaren-labs/Ciaren/discussions) before coding
3. **Use plugins for niche integrations** — if your idea is a new connector or
   product-specific integration, start with the Plugin SDK docs and open a
   discussion if the SDK blocks you
4. **Keep PRs focused** — one feature or fix per PR, not multiple unrelated changes

### Commit Messages

Use clear, descriptive commit messages:

```
feat: add pivot table transformation

- Implement pivot transformation node
- Add Pydantic schema validation
- Add 8 tests covering edge cases
- Update docs with pivot example
```

Format:

- `feat:` — new feature
- `fix:` — bug fix
- `refactor:` — code restructuring (no behavior change)
- `docs:` — documentation only
- `test:` — tests only
- `chore:` — dependencies, config, tooling

### Licensing of contributions

By opening a pull request, you agree that your contribution is licensed under
the license of the files you change: AGPL-3.0-only for the core and Apache-2.0
for the public Plugin API/SDK in `backend/app/plugin_api/` (see
[Licensing](README.md#licensing)). Only submit code you have the right to
contribute. No sign-off or CLA is required.

### Create the PR

1. Push your branch to your fork
2. Open a PR targeting **`main`**
3. Fill out the PR template (auto-generated)
4. Reference any related issues

**Good PR description:**

```
## Summary
Add pivot table transformation to enable reshaping data by column values.

## Changes
- New `PivotTransformation` class in `app/engine/transformations/reshape.py`
- API endpoint: `POST /api/transformations/preview` supports `pivot` type
- 8 tests covering 1D pivot, aggregation, margins

## Testing
- Tested with real-world sales data (1M rows)
- Verified null handling and data type preservation
- No performance regression (< 500ms for typical use)

## Checklist
- [x] Tests pass
- [x] Type hints on all functions
- [x] Updated architecture or docs if behavior changed
- [x] No new security warnings
```

### Review Process

- A maintainer will review as soon as possible — Ciaren currently has a single
  maintainer, so please allow up to a week for a first review
- Address feedback in new commits (don't force-push)
- Re-request review when you've made changes

---

## 🎯 Good First Issues

New to the project? Check out [issues labeled `good-first-issue`](https://github.com/ciaren-labs/Ciaren/labels/good-first-issue) or [`help-wanted`](https://github.com/ciaren-labs/Ciaren/labels/help-wanted):

- Adding a new transformation node (self-contained)
- Improving error messages
- Adding missing type hints
- Writing tests for untested code
- Documentation improvements

---

## 🐛 Reporting Bugs

1. **Check if it's already reported** — [search existing issues](https://github.com/ciaren-labs/Ciaren/issues)
2. **Include reproduction steps** — exactly how to trigger the bug
3. **Share your environment** — OS, Python version, browser, etc.
4. **Attach sample data** — anonymized CSV/Excel if possible
5. **Expected vs actual behavior** — what should happen vs what did

**Example:**

```
## Description
Null values not properly filled when using the "Fill Nulls" node with mean strategy.

## Steps to Reproduce
1. Upload attached `sales.csv` (100 rows, 3 columns)
2. Create flow with single "Fill Nulls" node
3. Set column to "amount", strategy to "mean"
4. Click Preview
5. Notice "amount" column still has NaN values

## Expected
All null values in "amount" should be replaced with column mean.

## Actual
Nulls remain unchanged.

## Environment
- OS: macOS 14.2
- Python: 3.12.4
- Browser: Chrome 121
```

---

## ✍️ Improving Documentation

Documentation lives in:

- **[backend/app/README.md](backend/app/README.md)** — backend architecture and layering rules
- **[README.md](README.md)** — project overview and quick start
- **[docs/](docs/)** — user guides, API reference, examples, and plugin docs
- **Code comments** — explain the "why", not the "what"

Help by:

- Writing tutorials for new transformations
- Clarifying ambiguous explanations
- Adding examples to docstrings
- Fixing typos and broken links
- Creating troubleshooting guides

---

## ⚠️ Important Notes

### About AI-Generated Code

For AI-assisted contributions, load [AGENTS.md](AGENTS.md) in your agent.
The contributor remains responsible for understanding and verifying the result.
When contributing:

1. **Review all code carefully** — even AI-generated code needs human verification
2. **Test edge cases** — AI tools can miss subtle bugs
3. **Comment non-obvious logic** — especially if you had to fix AI-generated code
4. **Don't blindly trust generated tests** — validate they actually test the behavior

### Security & Performance

- **Security first** — validate all user inputs at system boundaries
- **Test representative data shapes** — use synthetic fixtures covering realistic edge cases; never use private or production datasets without authorization
- **Consider performance** — test with larger datasets before merging
- **No secrets in code** — use environment variables for credentials

---

## 🚫 What We Won't Accept

- PRs that add **enterprise features** such as multi-tenant auth, cloud sync, distributed execution, or real-time collaboration without prior maintainer agreement
- PRs that add **long-tail connectors or product-specific integrations to core**
  without prior maintainer agreement. Build these as plugins instead, or propose
  an SDK improvement if the plugin path is blocked.
- **Breaking changes** without discussion — file an issue first
- **Unmaintained code** — if you add a feature, help maintain it
- **Security vulnerabilities** — see [SECURITY.md](SECURITY.md) for responsible disclosure

---

## 💬 Questions?

- **Setup issues?** Open a discussion in [GitHub Discussions](https://github.com/ciaren-labs/Ciaren/discussions)
- **Design questions?** [Open an issue](https://github.com/ciaren-labs/Ciaren/issues) or [discussion](https://github.com/ciaren-labs/Ciaren/discussions) — we love early feedback
- **Stuck on a PR?** Ask in comments — we're here to help

---

## 🙏 Thank You

Whether it's a one-line docs fix or a major feature, every contribution matters. You're helping build a tool that makes data work simpler for thousands of people.

Welcome to Ciaren! 🚀
