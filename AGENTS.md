# Ciaren — Agent Instructions

This is the single shared instruction file for coding agents. The product,
Python package and CLI are **Ciaren**; FlowFrame is the legacy checkout name.
Read `README.md` and `CONTRIBUTING.md` for product and contributor context.

## Stack and repository map

- Python 3.12+, FastAPI, SQLAlchemy and SQLite by default; dependencies use `uv`.
  Optional database configuration uses `CIAREN_DATABASE_URL` and `CIAREN_*`
  environment variables. See `backend/.env.example`.
- React 19, TypeScript, Vite and React Flow in `frontend/`; use Node.js 22.13+ and
  `npm ci`, matching CI. This application is not Next.js.
- `backend/app/main.py`: API; `backend/app/cli.py`: CLI;
  `backend/app/engine/`: execution and code generation;
  `backend/app/engine/registry.py`: registered nodes;
  `backend/app/engine/node_metadata.py`: catalog served at `/api/catalog/nodes`.
- `backend/app/plugin_api/`: public Apache-2.0 SDK; `backend/app/plugins/`:
  runtime; `backend/app/bundled_plugins/`: official plugins.
- `client/`: Python SDK; `docs/`: VitePress source; `examples/plugins/`:
  starter plugins. The separate `ciaren-labs/website` repository renders the
  public marketing site and imports these docs.

## Development and verification

Run commands from the indicated directory. Use focused checks for each change;
the full backend suite is for a release, merge or explicit request.
For that full gate, use `uv run python tools/run_tests.py` in `backend/`.
It records the complete pytest inventory, executes one module per process and
enforces combined 87% coverage. Use a fresh output directory; never hand-pick
modules to represent a full run.

| Directory | Command | Purpose |
| --- | --- | --- |
| `backend/` | `uv sync --all-groups --extra ml` | CI test dependencies |
| `backend/` | `uv run --no-sync pytest tests/<affected-file>.py` | Focused tests |
| `backend/` | `uv run --no-sync ruff check app tests tools` | Lint |
| `backend/` | `uv run --no-sync ruff format --check app tests tools` | Formatting |
| `backend/` | `uv run --no-sync mypy app` | Types |
| `frontend/` | `npm ci` | Install locked dependencies |
| `frontend/` | `npm test -- <affected-test>` | Focused Vitest checks |
| `frontend/` | `npm run lint` / `npm run type-check` / `npm run build` | Static gates |
| `docs/` | `npm ci` / `npm test` | Markdown, build and link checks |

The installed wheel serves the bundled editor and API on port 8055. Source
development uses `uv run ciaren serve --reload` and `npm run dev` on port 5173.
On Windows, persistent servers must use the repository-owned
`.agents/scripts/restart-dev.ps1` with a unique owner token; read
`.agents/references/process-lifecycle.md` first. If the helper is absent,
establish it before starting a server. Never terminate unowned processes. Run
one heavy test, build or browser process at a time on memory-constrained hosts.

## Implementation rules

- Search for and extend existing patterns before introducing code. Keep diffs
  focused; avoid speculative abstractions, options, dependencies and refactors.
- Every behavior change needs an observable regression test. For bugs, record
  the test failing before the fix. Extend existing fixtures and parametrize
  related cases. Never hide failures with broad catches or silent defaults.
- Review the diff for duplicated or orphaned code, CSS, tests and imports.
  When adding or renaming tests, run any tree-wide test guards as well.
- New nodes follow `.claude/skills/add-node/SKILL.md`: both pandas and Polars
  execution and runnable exports, registry and catalog, frontend form and
  validation, and the existing node/catalog contract tests.
- Files in `backend/app/` start with `# SPDX-License-Identifier: AGPL-3.0-only`;
  files in `backend/app/plugin_api/` use `Apache-2.0`. Do not mix licenses.
- Keep long-tail integrations in plugins. The core remains local-first;
  hosted services and commercial infrastructure belong in separate projects.

## Documentation and public copy

Edit user documentation in `docs/`, then import it into the website using its
sync pipeline. Never hand-edit generated `content/docs/` in the website or
change frozen release snapshots. Read `docs/PUBLISHING.md` for supported
components, navigation, assets and publishing constraints. Keep code examples
runnable and navigation linked. Validate new UI in a browser, including
keyboard interactions, mobile states, console errors and resolving links.

Use plain, specific copy with honest alpha framing. Do not claim security
audits, certifications, traffic guarantees or unshipped features. Request
GitHub stars only as an optional expression of usefulness; never require a
star for support, access or contribution.

## Git, contributors and durable state

- Inspect `git status`, fetch and reconcile the remote before editing. Preserve
  other sessions' work; never stash, reset or rewrite shared history.
- Local commits are the default. Push only on explicit request after the
  installed `preflight` passes. Stage explicit paths, inspect the staged diff,
  respect hooks, and check status after committing for formatter changes.
- Use the configured Git identity; omit AI attribution and extra author trailers.
- GitHub issues/PRs are this project's current backlog. Read contributor
  conversations before taking ownership. Keep active contributors on their
  issues; inactivity alone does not establish abandonment.
- Close issues only with verified implementation and honest delivery status.
  Do not duplicate a configured Jira backlog; Confluence, when configured,
  holds durable project knowledge rather than execution logs.

## Autonomous engineering workflow

For multi-step, unattended, high-risk, or mockup-driven implementation, invoke
`$autonomous-run` and follow its companion-skill graph.

- Build atomic, falsifiable acceptance criteria before material code changes.
  Use `acceptance-contract` when installed; otherwise use the CONTRACT table
  defined by `autonomous-run`.
- Use `$verification-loop` for every material behavior change.
- For visual requirements, apply the local design rules and verify viewport and
  interaction states in a real browser through `verification-loop`. Use
  `visual-fidelity` when installed; never claim a missing gate ran.
- Use `$security-domain-review` for auth, payments, permissions, tenancy, secrets,
  entitlements, sensitive data, webhooks, or destructive migrations.
- The implementer cannot be the sole reviewer. No evidence means not complete.
- When Jira exists, Jira is the canonical work/backlog/status source. Do not maintain a second backlog locally.
- When Confluence exists, persist only long-lived project knowledge there; do not store execution logs or temporary agent state.
- Long sessions may use `.agent-runs/<task>/SESSION.md` plus optional evidence as ephemeral memory only. Do not commit it.
- Prefer `.git/info/exclude` for local exclusion of `.agent-runs/`.
- At normal session finalization, synchronize durable state to canonical systems and delete the run directory automatically.

Check skill availability rather than assuming every companion is installed.

### Precedence with this repository's own skills

The global skills supply the *method* (acceptance IDs, evidence gates, independent
review, finding IDs). This repository's local skills supply the *rules*. Where the
two disagree on a repo-specific rule, the local skill wins; the global gate still
has to be satisfied.

- `add-node` is unaffected and keeps its existing trigger.
