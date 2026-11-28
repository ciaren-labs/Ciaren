---
title: Local-First Trust Model
description: "Ciaren's local-first security model: what the app trusts, what is not a hard boundary, where boundaries are enforced, and notes for shared use."
search: security trust model local-first sandbox permissions secrets
---

# Local-First Trust Model

Ciaren runs on **your** machine and executes **your** flows against **your**
data. That shapes the security model: the primary trust boundary is "code and data
you chose to run," not a multi-tenant server.

## What Ciaren assumes

- A single, trusted local user operates the app.
- The user owns the data, the database, and the execution environment.
- No Ciaren-hosted service is required to run flows.

Under those assumptions some power-user features (custom Python nodes, custom SQL)
are intentionally available. They run with the privileges of the local process.

## What is *not* a hard boundary

- **Plugins and `pythonTransform` are not sandboxed.** Python code a plugin or a
  custom node runs has the same access as the Ciaren process. The
  [permission model](/security/plugin-security) is a *trust and consent* boundary
  (what loads, after you approve it), not an OS-level sandbox.
- **Local license checks are not unbreakable DRM.** They deter casual misuse of
  premium plugins; a determined user can bypass them.
- **Signatures prove integrity and origin, not safety.** A validly signed plugin
  can still be poorly written; signing only proves it wasn't tampered with and came
  from a key you trust.

## Where Ciaren *does* enforce boundaries

- **Secrets stay out of artifacts.** A connection stores a *reference* to its
  password (`password_env`): an environment variable name (`env:NAME` or bare
  `NAME`), `keyring:NAME` for the OS keychain, or `file:/path` for a mounted
  secret file. The value is never stored in the database, the flow graph,
  `.flow` documents, or generated code. Exported scripts read it at run time. A
  reference cannot name Ciaren's own configuration variables, and `file:` paths
  must sit inside the allowed secret folders. See the
  [connection security model](/guide/connections#security-model).
- **Model URIs can't escape the artifact root.** A local `model_uri` must resolve
  inside the configured artifact directory (no `..` traversal, no absolute paths
  elsewhere); otherwise an MLflow `runs:/` / `models:/` URI is required.
- **Pickle is refused outright; `.joblib` is allowed but is *not* format-safe —
  it's confined, not sandboxed.** Bare `.pkl`/`.pickle` model files are rejected
  because loading one executes arbitrary code. `.joblib` is allowed (sklearn
  pipelines need it) but serializes with pickle under the hood, so a crafted
  `.joblib` can execute code exactly like a raw pickle — the only thing making
  that path safe is the artifact-root confinement above, which guarantees a
  `.joblib` can only load from a location the server itself controls, never an
  arbitrary user-supplied path. `.json` (XGBoost's native format) is the one
  format that's genuinely code-free. See `app/ml/security.py`.
- **Plugin code is gated before import.** A drop-in plugin that declares
  permissions is not imported until you approve it, and the app upload flow adds a
  risk confirmation (an off-by-default acknowledgement toggle) before installing.
- **Tampered or incompatible packages are refused.** A `.ciarenplugin` whose
  contents don't match its signature digest never installs, and one whose declared
  `ciaren`/`api_version` is incompatible with this build is rejected before it can
  replace a working install.
- **Hand-edited manifests are caught after install, too.** Ciaren pins a SHA-256
  digest of a packaged plugin's `ciaren-plugin.json` at install time; if the file
  on disk no longer matches (e.g. someone strips `license_required` or widens
  `permissions` by hand) the loader refuses to import that plugin's code. This is
  best-effort defense in depth, not tamper-proof — the pinned baseline lives in
  the same user-writable state file, so it deters casual edits, not a determined
  local attacker.
- **Optional plugin permission enforcement.** `CIAREN_PLUGIN_PERMISSION_ENFORCEMENT=warn|enforce`
  logs or blocks ungranted network/file-write/subprocess/shell actions by plugin
  code at runtime (a bar-raiser, not a sandbox — see the caveat above).
- **Cross-site requests can't drive the local API.** Any website you visit can
  *send* requests to `http://127.0.0.1` — CORS only stops it from reading the
  responses. Ciaren therefore refuses state-changing `/api` requests whose
  browser `Origin` is not a `CORS_ORIGINS` entry or a local hostname
  (`localhost` / `127.0.0.1` / `::1`; extend with `CIAREN_TRUSTED_HOSTS`). This
  closes the CSRF/DNS-rebinding path where a malicious page installs and enables
  a plugin behind your back. Non-browser clients (CLI, curl) send no `Origin`
  and are unaffected; when `CIAREN_API_TOKEN` is set the token gate covers this
  instead.

## The flow assistant

The optional [flow assistant](/guide/flow-assistant) sends your request text and a
limited description of the flow to the AI provider you configure. It is off until
you add a provider key or an operator configures one on the server.

- **What leaves the server.** Your request, supported node types, wiring, turn-local
  column references with coarse types, and each dataset's row count with per-column
  null fraction, distinct count and uniqueness from the stored profile. Column names
  are sent only when you opt in for a request or type them in it. Rows, file contents, filenames, dataset IDs, connection details, scripts
  and raw logs stay on the server. The assistant checks its drafts on generated
  placeholder rows, not your data.
- **What it can change.** Its tools run inside the server against the same node
  validation as the editor. It cannot run a flow, edit data connections or file paths,
  write Python Transform nodes, or reach the network or filesystem. Nothing is saved
  until you choose **Apply and save**. Confirmed changes are listed in the flow's
  **Activity** and can be reversed.
- **Where the key lives.** A key saved on the Connections page goes into the OS
  keychain, not the database. Operators can use the environment or a mounted secret
  file instead. Ciaren removes assistant key variables from its environment at
  startup and from run workers.
- **What it is not.** A Python Transform node still runs with the server's
  privileges and can read the key wherever it is stored: server memory, a mounted
  secret file or the OS keychain. Process mode and strict Python checks do not stop
  that. On a shared installation, allow only trusted users to edit flows and use a
  provider key with a spending limit. Anyone with access to the API can manage
  the assistant, so deploy separate instances for separate trust boundaries.

## Opt-in guards for networked or shared use

The defaults are tuned for one trusted local user. These settings tighten them
when connection configs, flow authors or network reachability are less trusted.
All are environment-only, so changing them needs access to the server's
environment. See [Advanced Setup](/guide/advanced-setup#environment-variables).

| Setting | Guards against |
| --- | --- |
| `CIAREN_API_TOKEN` | Unauthenticated access to `/api/*` when bound beyond loopback |
| `CIAREN_CONNECTOR_BLOCK_PRIVATE_HOSTS` | Connections that reach loopback, link-local (cloud metadata) or private addresses |
| `CIAREN_STORAGE_ALLOWED_ROOTS` | A Local Storage or SQLite/DuckDB connection reading or writing arbitrary server files |
| `CIAREN_SECRET_ENV_ALLOWLIST`, `CIAREN_SECRET_FILE_DIRS` | A connection pointing its password reference at an unrelated environment variable or file |
| `CIAREN_PYTHON_TRANSFORM_STRICT` | Dangerous imports, builtins and dunder access in Python Transform scripts (static checks, not a sandbox) |
| `CIAREN_PLUGIN_PERMISSION_ENFORCEMENT` | Ungranted plugin network, file-write and process actions (not a sandbox) |
| `CIAREN_REQUIRE_TRUSTED_PLUGINS` | Installing unsigned plugins from the UI |

## Still out of scope: multi-user hardening

Ciaren has no user accounts, roles, per-user audit trail, read-only SQL connection
modes or per-plugin OS sandboxing. Before multi-user, team or enterprise use, add
those yourself or deploy one isolated instance per trust boundary. They are
deliberately out of scope for the local-first core.

## See also

- [Plugin security & permissions](/security/plugin-security)
- [Flow assistant](/guide/flow-assistant) — what leaves the server and how keys are stored
- [Packaging & Distribution](/plugins/packaging-and-distribution)
