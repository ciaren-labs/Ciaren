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

## Run the paid DeepSeek smoke locally

Use the wheel built from this branch. The script opens Chromium against a new, token-protected loopback server with its own empty database. It uses `ciaren serve` and the native DeepSeek adapter with `deepseek-flash`. In paid mode, each invocation can spend up to four API calls on synthetic examples. It makes no automatic retries. Running it again starts a new budget.

On Windows, run the following in PowerShell from the repository root. These setup commands contain no credentials.

```powershell
Push-Location frontend
npm ci --engine-strict
npm run build
Pop-Location
$qa = Join-Path $env:TEMP ("ciaren-qa-" + [guid]::NewGuid())
uv venv --python 3.12 "$qa/env"
uv build backend --wheel --out-dir "$qa/wheels"
$python = "$qa/env/Scripts/python.exe"
$wheel = (Get-ChildItem "$qa/wheels/ciaren-*.whl").FullName
uv pip install --python $python $wheel playwright pillow
& $python -m playwright install chromium
```

Have the local credential manager inject the **direct DeepSeek API key** into the process variable `CIAREN_ASSISTANT_DEEPSEEK_API_KEY` for the following command. Keep the value off the command line and out of shell history, configuration files, screen recordings and build jobs. This smoke does not import OpenCode credentials. An OpenCode Go key requires an OpenCode adapter that supports the desired DeepSeek model. Ciaren's current OpenCode allowlist does not include one.

```powershell
& $python qa/assistant/provider_walkthrough.py --paid-deepseek
```

The run asks the packaged editor to build a two-input flow, cite the Join guide, decline a scheduling request and repair a missing order. It checks the saved graph, activity, runs and schedules before and after each proposal. A separate manual sort edit invalidates a reversal preview. A fresh confirmation must restore only the Join setting. Assertions use the typed graph, citation URL and server state. A wrong proposal, refusal on a supported task or invalid response fails the smoke. The report prints the mode, provider, model and check outcomes. The paid path produces no screenshots, GIF, request traces or response dumps.

### Reproduce the README recording without an account

Use the same test environment as above. The following command uses a simulated provider, the packaged editor and the same synthetic CSVs and assertions. It records selected moments from Chromium starting at the repair request and ending at the confirmed reversal. The output omits browser chrome and credential settings.

```powershell
& $python qa/assistant/provider_walkthrough.py --demo-gif docs/public/screenshots/flow-assistant-join.gif
```

On Linux, substitute the test environment's `bin/python` for `$python`. The database bootstrap regression runs with that environment using `python qa/assistant/test_database_bootstrap.py`.
