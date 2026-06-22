# CI/CD Pipeline

FlowFrame uses GitHub Actions to automate testing, linting, and coverage verification across multiple Python versions and database backends.

## Backend Testing

### Workflows

#### 1. **backend-tests.yml** (Default - Fast)
Runs on every PR and push to `main` branch.

- **Python versions:** 3.11, 3.12, 3.13
- **Database backends:**
  - SQLite (all versions)
  - PostgreSQL (Python 3.11 only to save CI time)
- **Checks:**
  - Linting (Ruff)
  - Type checking (mypy)
  - Unit tests with pytest
  - Coverage enforced at 95%
- **Duration:** ~10-15 minutes total

#### 2. **backend-tests-full.yml** (Comprehensive - Optional)
Runs on schedule (nightly) or can be triggered manually.

Tests **all combinations** across:
- **Python versions:** 3.11, 3.12, 3.13
- **Database backends:** SQLite, PostgreSQL, MySQL 8.0
- **Coverage threshold:** 95%

This ensures compatibility across all supported databases.

### Test Execution

Tests run with:

```bash
pytest tests \
  --cov=app \
  --cov-fail-under=95 \
  --cov-report=xml
```

#### Database Configuration

Tests automatically detect the database backend via `DATABASE_URL` environment variable:

| Backend | URL Format |
|---------|-----------|
| SQLite | `sqlite+aiosqlite:///:memory:` (default) |
| PostgreSQL | `postgresql+asyncpg://user:pass@host:5432/db` |
| MySQL | `mysql+aiomysql://user:pass@host:3306/db` |

See `conftest.py` for database fixture configuration.

### Coverage Requirements

- **Minimum:** 95% code coverage
- **Target:** >95% for all commits
- **Exceptions:** Migrations and type-checking only blocks excluded

Covered in:
```python
[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

### Local Testing

Test locally the same way CI does:

```bash
cd backend

# Install dev dependencies
uv sync --all-groups

# Run all tests with coverage
uv run pytest tests --cov=app --cov-fail-under=95

# Test against specific database
DATABASE_URL=sqlite+aiosqlite:///:memory: uv run pytest tests

# Test against PostgreSQL (requires running postgres)
DATABASE_URL=postgresql+asyncpg://postgres:pass@localhost/flowframe_test uv run pytest tests
```

### Linting & Type Checking

```bash
# Format & lint
uv run ruff check app tests

# Type checking
uv run mypy app
```

## Frontend Testing

### Workflow: frontend-tests.yml

Runs on every PR and push to `main` branch.

- **Node versions:** 18.x, 20.x, 22.x
- **Checks:**
  - Linting (ESLint/Biome)
  - Type checking (TypeScript)
  - Unit tests (Vitest if configured)
  - Build success
  - E2E tests (Playwright if configured)
- **Duration:** ~15-20 minutes

### Local Testing

```bash
cd frontend

# Install dependencies
npm install

# Lint
npm run lint

# Type check
npm run type-check

# Run unit tests
npm run test

# Build
npm run build

# Run E2E tests (Playwright)
npm run test:e2e
```

## PR Checklist

Before pushing to GitHub, run locally:

```bash
# Backend
cd backend
uv sync --all-groups
uv run ruff check app tests
uv run mypy app
uv run pytest tests --cov=app --cov-fail-under=95

# Frontend
cd ../frontend
npm ci
npm run lint
npm run type-check
npm run build
```

## Secrets & Configuration

### Required Secrets

- **`CODECOV_TOKEN`** (optional) — Enable Codecov integration
  - Get from https://codecov.io after linking repo

### Environment Variables

Set in GitHub repo settings → Secrets and variables:

- None required for basic CI
- Optional: `CODECOV_TOKEN` for coverage reporting

## Troubleshooting

### Tests pass locally but fail in CI

Common causes:
1. **Python version mismatch** — CI uses 3.11, 3.12, 3.13; test on all
2. **Database differences** — SQLite vs PostgreSQL behavior
3. **Environment variables** — Ensure all secrets are set
4. **Dependencies** — Run `uv sync --all-groups` to ensure latest

### Coverage drops below 95%

Add tests for new code:
- Unit tests for functions in `app/services`
- Integration tests for API routes in `app/api/routes`
- Transformation tests in `app/engine/transformations`

Mark lines as intentionally untested:
```python
if never_happens:  # pragma: no cover
    ...
```

### Database service fails to start

For PostgreSQL/MySQL in Docker:
```bash
# Check if service is running
docker ps

# View logs
docker logs <container_id>

# Restart
docker restart <container_id>
```

## CI Performance Tips

1. **Use cache** — GitHub Actions caches `uv`, Python, npm
2. **Fail fast** — CI stops on first failure by default
3. **Parallel jobs** — Different Python versions run in parallel
4. **Conditional steps** — Skip expensive steps for unrelated changes
5. **Schedule heavy tests** — Full matrix runs nightly, not on every PR

## Future Improvements

- [ ] Add performance benchmarking
- [ ] Add security scanning (Trivy, Bandit)
- [ ] Add dependency vulnerability scanning
- [ ] Add code quality scoring (CodeFactor, CodeClimate)
- [ ] Multi-database end-to-end tests in CI
- [ ] Automated performance regression detection

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [SQLAlchemy Async Tutorial](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
