.PHONY: install dev-backend dev-frontend test lint type-check check build clean

install:
	cd backend && uv sync --all-groups
	cd frontend && npm ci

dev-backend:
	cd backend && uv run ciaren serve --reload

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest tests --cov=app --cov-report=term-missing

lint:
	cd backend && uv run ruff check app tests
	cd backend && uv run ruff format --check app tests

type-check:
	cd backend && uv run mypy app
	cd frontend && npm run type-check

check: lint type-check test

build:
	cd frontend && npm run build

clean:
	rm -rf backend/dist backend/.pytest_cache backend/htmlcov backend/coverage.xml
	rm -rf frontend/dist
