# CI/CD Pipeline

Ciaren uses GitHub Actions to automate testing, linting, coverage, and
documentation deployment.

## Backend Testing

### Workflow: `backend-tests.yml`

Runs on every pull request and push to `main` that touches `backend/**`.

- **Python versions:** 3.12, 3.13 (matrix, run in parallel)
- **Operating systems:** Ubuntu, Windows, and macOS (matrix, run in parallel)
- **Checks:**
  - Linting (Ruff)
  - Type checking (mypy)
  - Unit + API tests with pytest
  - Coverage enforced at 87% (`--cov-fail-under=87`)

### Database

The test suite runs against **in-memory SQLite**
(`sqlite+aiosqlite:///:memory:`), configured directly in
`backend/tests/conftest.py`. CI does not start an external database service, and
the tests do not read `DATABASE_URL`. At runtime the app itself supports other
databases through `DATABASE_URL` (using async drivers such as
`postgresql+asyncpg://`).

### Local Testing

Run the same checks CI does:

```bash
cd backend

# Install dev dependencies
uv sync --all-groups

# Lint and type-check
uv run ruff check app tests
uv run mypy app

# Run tests with coverage
uv run pytest tests --cov=app --cov-report=term-missing --cov-fail-under=87
```

### Coverage

- **Minimum:** 87% (`--cov-fail-under=87`) for the infra-free suite; the
  connector I/O paths are gated separately on the merged Codecov report.
- Excluded lines are configured under `[tool.coverage.report]` in
  `backend/pyproject.toml` (e.g. `pragma: no cover`, `if TYPE_CHECKING:`).
- Coverage is uploaded to Codecov when a `CODECOV_TOKEN` secret is set
  (optional — CI does not fail without it).

## Docker

### Workflow: `docker.yml`

Runs on every pull request and push to `main` that touches `Dockerfile`,
`docker-compose.yml`, `.dockerignore`, `backend/**`, or `frontend/**`.

#### Jobs

| Job | When | What it tests |
| ----- | ------ | --------------- |
| `build` | PRs + push to main | Base image (no extras) |
| `build-ml` | Push to main only | Image with `EXTRAS=ml` |
| `summary` | Always | Gate check |

#### `build` job (base image)

1. Builds the image with Docker BuildKit (GitHub Actions cache)
2. Verifies `/app/app/web/index.html` is present inside the image (frontend bundled)
3. Starts a container and waits up to 90 s for `/health` to respond
4. Hits `GET /` and checks for an HTML response (frontend served)
5. Runs `ciaren info` inside the live container (settings resolve correctly)
6. Runs `ciaren check` inside the live container (DB reachable, engines available)

#### `build-ml` job (ML extras, push only)

Rebuilds with `--build-arg EXTRAS=ml` and verifies:

- `scikit-learn`, `xgboost`, `lightgbm`, `mlflow` are importable
- `ciaren check` passes with ML enabled

#### Local equivalent

```bash
# build
docker compose build

# run
docker compose up

# smoke-test
curl http://localhost:8055/health
docker compose exec ciaren ciaren check
```

## Security Scanning

### Workflow: `codeql.yml`

[CodeQL](https://codeql.github.com/) static analysis for both languages, on pull
request and push to `main`/`development`, plus a weekly scheduled scan.

- **Languages:** Python (backend) and TypeScript/JavaScript (frontend), analyzed
  in parallel with the `security-extended` query pack.
- **Results:** appear under the repository's **Security → Code scanning** tab and
  annotate the diff on pull requests.

### Workflow: `security-audit.yml`

Dependency vulnerability auditing, on changes to the lockfiles/manifests and
weekly. Complements Dependabot: Dependabot opens scheduled version-bump PRs,
while this **fails CI** when a currently pinned dependency has a known CVE.

| Job | Tool | Scope |
| ----- | ------ | ------- |
| `backend` | `pip-audit` | The frozen, fully-resolved dependency set (all groups + the `ml` extra), `--strict` |
| `frontend` | `npm audit` | `--audit-level=high` (moderate/low transitive advisories don't block PRs) |

Dependabot itself is configured in `.github/dependabot.yml` (pip, npm for
`frontend` and `docs`, and GitHub Actions — all weekly).

#### Local equivalent

```bash
# backend — audit the locked dependency set
cd backend
uv export --frozen --all-groups --extra ml --no-emit-project --no-hashes \
  --format requirements-txt | uvx pip-audit --requirement /dev/stdin --strict

# frontend
cd frontend && npm audit --audit-level=high
```

## Documentation

### Workflow: `docs-deploy.yml`

Runs on changes to `docs/**`.

- **Lint:** `npm run lint` (markdownlint)
- **Build & test:** `npm run build`, then validates the build output and checks
  for broken internal links
- **Deploy:** on push to `main`, publishes the built site to GitHub Pages

Run locally:

```bash
cd docs
npm ci
npm run lint
npm run build
npm run test:links
```

## Frontend Testing

The React frontend lives in `frontend/` and has a Vitest unit-test suite
(`npm run test`). The `frontend-tests.yml` workflow (lint → type-check → test →
build, plus a Playwright E2E job) is currently **manual only**
(`workflow_dispatch`) while the test suite is being filled out; it is not yet wired
to run automatically on every push. Run the checks locally with:

```bash
cd frontend
npm ci
npm run build      # type-check + production build
npm run test       # Vitest unit tests
```

## Secrets

- **`CODECOV_TOKEN`** (optional) — enables Codecov uploads. CI passes without it.

## Troubleshooting

### Tests pass locally but fail in CI

- **Python version mismatch** — CI runs 3.12 and 3.13; test against each.
- **OS-specific behavior** — CI runs on Ubuntu, Windows, and macOS; watch for
  path separators, line endings, and temp-dir differences.
- **Dependencies** — run `uv sync --all-groups` to match CI.

### Coverage drops below the threshold

Add tests for new code (services, API routes, and engine transformations), or
mark genuinely unreachable lines with `# pragma: no cover`.

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [VitePress Documentation](https://vitepress.dev/)
