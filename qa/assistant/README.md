# Packaged editor acceptance on PostgreSQL and MySQL

The browser exercises the installed Ciaren wheel with real metadata storage, HTTP requests, CSVs and execution engines. The inference provider and OS keychain are test doubles. The test starts a separate, unprivileged database process for each invocation. It creates its own data directory, loopback port and random authentication credentials. It never accepts a database URL or uses an existing server.

## Prerequisites

Use a Linux checkout with the example CSVs, a dedicated Python environment, Chromium, and local database server binaries. PostgreSQL needs `initdb` and `postgres` from the same installation. MySQL needs Oracle MySQL Community Server 8.4 with its character sets, error messages and runtime libraries.

Build the wheel from the checkout, including the editor, and install it in the test environment. Run the harness with that environment’s Python. An editable Ciaren install cannot verify packaging.

```sh
(cd frontend && npm ci && npm run build)
(cd backend && uv build --wheel --out-dir /tmp/ciaren-review-wheels)
uv venv /tmp/ciaren-review-env
uv pip install --python /tmp/ciaren-review-env/bin/python /tmp/ciaren-review-wheels/ciaren-*.whl asyncpg aiomysql cryptography playwright
export CIAREN_TEST_CHROMIUM=/path/to/chromium
```

## Run the browser scenarios

```sh
/tmp/ciaren-review-env/bin/python qa/assistant/database_smoke.py postgresql \
  --pg-bindir /usr/lib/postgresql/17/bin --screenshots /tmp/ciaren-postgresql-shots

/tmp/ciaren-review-env/bin/python qa/assistant/database_smoke.py mysql \
  --mysqld /usr/sbin/mysqld --screenshots /tmp/ciaren-mysql-shots
```

For unpacked distributions, supply `--pg-share`, or `--mysql-basedir` and `--mysql-messages`, with paths to the matching installation. Set `LD_LIBRARY_PATH` only if the database binaries require local shared libraries. No administrative OS privileges are needed.

The harness upgrades an empty database to Alembic revision `c9d0e1f2a3b4` with the installed CLI, seeds a pinned CSV input and a flow, then upgrades to the activity revision. It checks the storage dialect, revision, table and graph directly before starting Ciaren. Chromium executes the original flow, then creates, repairs and reverts the orders audit. It exercises stale Save and Run actions, execution admission, editing during an actual run, and concurrent confirmations. Separate connections inspect the complete audit JSON, the winning graph and the linked event IDs. Temporary server state is removed on exit. Screenshots and downloaded fixture CSVs remain in the requested output directory.

For the source-checkout SQLite regression, run `python qa/assistant/editor_smoke.py --screenshots /tmp/ciaren-sqlite-shots` with Playwright installed, a built `frontend/dist`, and the backend environment at `backend/.venv`.
