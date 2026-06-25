# Contributing to FlowFrame

Thank you for your interest in FlowFrame! We're excited to have you help us build a simpler ETL tool for everyone.

This document explains how to contribute — whether you're fixing bugs, adding features, improving docs, or helping with design.

---

## ✨ What We Need

### Code Contributions

- **New transformation nodes** — filters, aggregations, joins, reshaping operations
- **Bug fixes** — we track these in [Issues](https://github.com/yourusername/flowframe/issues)
- **Performance improvements** — especially in the execution engine and preview system
- **Frontend improvements** — better UX, accessibility, responsive design
- **Backend improvements** — better error handling, validation, API design

### Non-Code Contributions

- **Documentation** — tutorials, examples, troubleshooting guides
- **Testing** — try FlowFrame with real datasets, report edge cases
- **Design feedback** — UI/UX improvements, workflow suggestions
- **Community** — answer questions in discussions, mentor new contributors

---

## 🚀 Getting Started

### 1. Fork & Clone

```bash
git clone https://github.com/YOUR_USERNAME/FlowFrame.git
cd FlowFrame
```

### 2. Set Up Development Environment

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Start server
uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (runs on port 5173)
npm run dev

# Run linting
npm run lint

# Build for production
npm run build
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

Use descriptive branch names:
- `feature/add-pivot-transformation`
- `fix/null-handling-bug`
- `docs/setup-guide`

---

## 📝 Code Standards

### Backend (Python)

- **Type hints required** — use them everywhere (`def transform(data: pd.DataFrame) -> pd.DataFrame`)
- **Follow PEP 8** — we use [Black](https://github.com/psf/black) for formatting
- **Tests for new code** — especially transformations and services
- **Pydantic schemas for API inputs/outputs** — no raw dicts
- **Keep route handlers thin** — put logic in services
- **No pandas directly in routes** — encapsulate in `app/engine`

#### Example:

```python
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

#### Example:

```typescript
// features/flows/hooks/useFlowQuery.ts
import { useQuery } from '@tanstack/react-query';
import { getFlow } from '@/lib/api';

export function useFlowQuery(flowId: string) {
  return useQuery({
    queryKey: ['flows', flowId],
    queryFn: () => getFlow(flowId),
  });
}
```

---

## ✅ Testing

### Backend Tests

```bash
cd backend

# Run all tests
pytest

# Run specific test file
pytest tests/test_flows.py

# Run with coverage
pytest --cov=app
```

**Guidelines:**
- Test new transformations with real data edge cases
- Test API endpoints with integration tests (use SQLite for speed)
- Test graph validation and topological sorting
- Aim for >80% coverage on critical paths

### Connector Integration Tests

The default `pytest` run is **infra-free**: the cloud/database connector tests
self-skip unless their service is reachable, so a normal test run never needs
Docker. They live in `backend/tests/integration/` under the `connectors` marker
and exercise the real driver I/O paths against local emulators. CI runs them in
the **Connectors Integration** workflow
(`.github/workflows/connectors-integration.yml`).

To run one locally: start its emulator, install the matching extra, set the
service's env var(s), then run the marked tests.

| Connector  | Emulator        | Extra   | Activating env var             |
|------------|-----------------|---------|--------------------------------|
| S3         | MinIO           | `s3`    | `FLOWFRAME_TEST_S3_ENDPOINT`   |
| MongoDB    | `mongo`         | `mongo` | `FLOWFRAME_TEST_MONGO_HOST`    |
| Azure Blob | Azurite         | `azure` | `FLOWFRAME_TEST_AZURE_ENDPOINT`|
| GCS        | fake-gcs-server | `gcs`   | `STORAGE_EMULATOR_HOST`        |

```bash
cd backend
pip install -e ".[dev,s3,mongo,azure,gcs]"   # or just the extra you need
```

**S3 (MinIO):**

```bash
docker run -d -p 9000:9000 -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin minio/minio server /data
FLOWFRAME_TEST_S3_ENDPOINT=http://127.0.0.1:9000 \
FLOWFRAME_TEST_S3_ACCESS_KEY=minioadmin \
FLOWFRAME_TEST_S3_SECRET_KEY=minioadmin \
  pytest tests/integration/test_s3_connector.py -m connectors
```

**MongoDB:**

```bash
docker run -d -p 27017:27017 mongo:7
FLOWFRAME_TEST_MONGO_HOST=127.0.0.1 \
  pytest tests/integration/test_mongo_connector.py -m connectors
```

**Azure Blob (Azurite):**

```bash
docker run -d -p 10000:10000 mcr.microsoft.com/azure-storage/azurite \
  azurite-blob --blobHost 0.0.0.0 --skipApiVersionCheck
FLOWFRAME_TEST_AZURE_ENDPOINT=http://127.0.0.1:10000/devstoreaccount1 \
  pytest tests/integration/test_azure_connector.py -m connectors
```

**GCS (fake-gcs-server):**

```bash
docker run -d -p 4443:4443 fsouza/fake-gcs-server \
  -scheme http -port 4443 -public-host 127.0.0.1:4443
STORAGE_EMULATOR_HOST=http://127.0.0.1:4443 \
  pytest tests/integration/test_gcs_connector.py -m connectors
```

To run every suite at once, start all four emulators, export all the env vars,
then `pytest -m connectors`.

**Notes:**
- Azurite needs `--skipApiVersionCheck` — the SDK speaks a newer API version than the emulator pins.
- The endpoints and Azurite credentials shown are the emulators' well-known defaults, not secrets.
- On **Windows PowerShell**, the inline `VAR=value cmd` prefix doesn't work — set each variable first with `$env:VAR = "value"`, then run `pytest`.
- Coverage from these tests lands in the merged Codecov report (the `connectors-integration` flag), not the infra-free `--cov-fail-under` gate.

### Frontend Tests

```bash
cd frontend

# Vitest (component/hook tests)
npm run test

# E2E tests (Playwright)
npm run test:e2e
```

**Guidelines:**
- Test form validation and error states
- Test flow editor interactions
- Test API error handling and retries

---

## 🔄 Submitting a Pull Request

### Before You Start

1. **Check existing issues/PRs** — search [open issues](https://github.com/rodrigo-arenas/FlowFrame/issues) to avoid duplicate work
2. **Open an issue first for big features** — [start a discussion](https://github.com/rodrigo-arenas/FlowFrame/discussions) before coding
3. **Keep PRs focused** — one feature or fix per PR, not multiple unrelated changes

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

### Create the PR

1. Push your branch to your fork
2. Open a PR against `main`
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
- [x] Updated CLAUDE.md if architecture changed
- [x] No new security warnings
```

### Review Process

- At least one maintainer will review within 2-3 days
- Address feedback in new commits (don't force-push)
- Re-request review when you've made changes

---

## 🎯 Good First Issues

New to the project? Check out [issues labeled `good-first-issue`](https://github.com/rodrigo-arenas/FlowFrame/labels/good-first-issue) or [`help-wanted`](https://github.com/rodrigo-arenas/FlowFrame/labels/help-wanted):

- Adding a new transformation node (self-contained)
- Improving error messages
- Adding missing type hints
- Writing tests for untested code
- Documentation improvements

---

## 🐛 Reporting Bugs

1. **Check if it's already reported** — [search existing issues](https://github.com/rodrigo-arenas/FlowFrame/issues)
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
- Python: 3.11.8
- Browser: Chrome 121
```

---

## ✍️ Improving Documentation

Documentation lives in:
- **[architecture.md](architecture.md)** — system design
- **[CLAUDE.md](CLAUDE.md)** — vision, tech stack, coding standards
- **[README.md](README.md)** — project overview and quick start
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

This project includes code generated or assisted by AI. When contributing:

1. **Review all code carefully** — even AI-generated code needs human verification
2. **Test edge cases** — AI tools can miss subtle bugs
3. **Comment non-obvious logic** — especially if you had to fix AI-generated code
4. **Don't blindly trust generated tests** — validate they actually test the behavior

### Security & Performance

- **Security first** — validate all user inputs at system boundaries
- **Test with real data** — sample data doesn't catch edge cases
- **Consider performance** — test with larger datasets before merging
- **No secrets in code** — use environment variables for credentials

---

## 🚫 What We Won't Accept

- PRs that add **enterprise features** (scheduling, multi-tenant, cloud sync) — use CLAUDE.md to understand MVP scope
- **Breaking changes** without discussion — file an issue first
- **Unmaintained code** — if you add a feature, help maintain it
- **Security vulnerabilities** — see [SECURITY.md](SECURITY.md) for responsible disclosure

---

## 💬 Questions?

- **Setup issues?** Open a discussion in [GitHub Discussions](https://github.com/rodrigo-arenas/FlowFrame/discussions)
- **Design questions?** [Open an issue](https://github.com/rodrigo-arenas/FlowFrame/issues) or [discussion](https://github.com/rodrigo-arenas/FlowFrame/discussions) — we love early feedback
- **Stuck on a PR?** Ask in comments — we're here to help

---

## 🙏 Thank You

Whether it's a one-line docs fix or a major feature, every contribution matters. You're helping build a tool that makes data work simpler for thousands of people.

**Welcome to FlowFrame! 🚀**
