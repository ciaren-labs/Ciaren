# FlowFrame — Security Audit

Date: 2026-06-29
Scope: backend (`backend/app/`), with emphasis on the plugin system, custom
Python execution, ML model loading, connectors, webhooks, and the API/middleware
layer.

This document records the findings of a manual security review. Some low-risk,
backward-compatible hardenings were applied directly on this branch (marked
**Fixed**); the rest are documented as recommendations because they touch the
product's trust model or deployment posture and are judgment calls for the
maintainers (marked **Open**).

---

## Threat model note

FlowFrame is **local-first and unauthenticated by design** — the entire REST API
has no auth layer (`app/api/deps.py` injects only DB-backed services; `app/main.py`
adds CORS + GZip + a couple of security headers, no auth middleware). The CLI binds
to `127.0.0.1` by default and CORS defaults to `http://localhost:5173`, which is a
safe single-operator posture. **The trust model assumes the API caller is the
trusted local operator.** Most findings below are about what happens when that
assumption breaks — primarily when the API is exposed on a network.

---

## What is well implemented (no action needed)

- **Plugin signing** (`app/plugin_api/signing.py`, `app/plugins/package.py`):
  Ed25519 over a canonical payload that binds `digest` + `key_id` + `publisher`;
  trust is keyed strictly by `key_id` (a previous publisher-name fallback that
  allowed trust-anchor confusion was removed). `verify()` never raises on a bad
  signature.
- **Package extraction** (`app/plugins/install.py`): layered anti zip-slip
  (lexical name check + resolved-path containment), symlink-entry rejection, and
  zip-bomb guards (per-entry, total, and entry-count caps). `_safe_target_name`
  rejects unsafe plugin ids rather than rewriting them (injective mapping).
- **Webhook auth** (`app/api/routes/webhooks.py`): constant-time secret compare
  (`hmac.compare_digest`); endpoint returns 404 until a secret is configured.
- **Connection secrets** (`app/core/secrets.py`): passwords are never persisted
  (only the *name* of an env var is stored), resolved at call time, and scrubbed
  from driver error strings; cloud SDK loggers are pinned to CRITICAL.
- **SQL identifiers** (`app/connectors/base.py`): table/collection names are regex
  validated and quoted via SQLAlchemy; URLs built with `URL.create` (no DSN
  concatenation), so a user can't smuggle extra driver params.

---

## Findings

### #1 — Unauthenticated API + arbitrary code execution when network-exposed — **Mitigated**

The API has no authentication. Several paths reach arbitrary code execution:

- `pythonTransform` runs user code via `exec()`
  (`app/engine/transformations/script.py`), reachable through
  `POST /api/transformations/preview`, `POST /api/flows/{id}/preview`, and runs.
  This is documented and legitimate *locally*.
- Plugin install + grant + enable (`POST /api/plugins/install` → `/grant` →
  `/enable`) imports and runs plugin code in-process.

The CLI default (`127.0.0.1`) is safe, but **the Docker image starts the server
with `--host 0.0.0.0`** (`Dockerfile`), exposing the unauthenticated API on all
interfaces in the documented container deployment.

**Applied:** Added an optional shared-secret gate, `FLOWFRAME_API_TOKEN`
(`app/core/auth.py`, wired as a global FastAPI dependency in `create_app`). Unset
(default) preserves the local-first, no-auth posture; when set, every `/api/*`
request must present the token as `Authorization: Bearer <token>` or
`X-FlowFrame-Token` (constant-time compared). Exempt: CORS preflight, the static
web UI / SPA shell, health/readiness/OpenAPI, and the webhook trigger (which keeps
its own `X-FlowFrame-Secret`). The CLI prints a startup warning when binding to a
non-loopback host with no token (`flowframe serve`), and the Dockerfile documents
the posture. The web UI sends the token automatically (stored in `localStorage`,
seedable once via a `?api_token=…` URL). Tests: `tests/api/test_api_auth.py`.

**Still recommended:** for untrusted networks, also front FlowFrame with an
authenticating reverse proxy; the single shared token is a baseline, not a
substitute for per-user auth. The token does not retrofit auth onto the SSE log
stream consumed via `EventSource` (browsers can't set headers there) — the bundled
UI doesn't use it, but a custom client would need a header-capable SSE reader.

### #2 — Plugin permission model is load-time only; runtime is not sandboxed — **Partially mitigated**

The permission "gate" (`app/plugins/loader.py` `_gate`) only decides **whether to
import** a plugin. Once imported, plugin code runs with full process privileges —
Python has no real sandbox, so this cannot be fully fixed. Two concrete issues
were addressed:

- **Silent load of zero-permission plugins (fixed).** Previously a drop-in /
  marketplace plugin declaring `permissions: []` loaded with **no approval prompt
  at all**. Now a discovered plugin requires an **explicit user opt-in before any
  of its code is imported**, even with zero declared permissions — approval means
  "let this code run", not merely "grant these capabilities". Implemented via a new
  `approved` flag on the persisted plugin state (`app/plugins/state.py`):
  `is_approved`/`set_approved`, with enabling or granting counting as approval. The
  loader keeps an unapproved plugin pending (`needs_permissions` → shown as "Needs
  approval"). Backward-compatible: state entries written before the flag are read
  as already-approved, so an upgrade never silently re-gates trusted plugins.
- **Honest disclosure (already strong, reinforced).** The plugins UI already warns
  prominently that plugins are *not sandboxed* and that "permissions are a heads-up,
  not a security boundary". The per-plugin approval notice now also covers the
  zero-permission case ("approving still runs its code on this machine with your
  access"). Backend docstrings (`state.py`, `loader.py`, install route) were
  corrected to stop implying the permission list is runtime-enforced.

Tests: `tests/plugins/test_state.py` (approval + legacy read),
`tests/plugins/test_loader_gating.py` (zero-permission stays pending until
approved), and updated API/run tests.

**Still inherent:** entry-point (pip-installed) plugins load deliberately and are
not gated; and no mechanism constrains what approved code does at runtime. Treat
enabling a plugin as running arbitrary code with your account's access.

### #3 — `.joblib` model loading treated as a "non-pickle / safe" format — **Fixed**

`app/ml/security.py` rejected `.pkl`/`.pickle` "because they execute code on load"
while allowing `.joblib`. But `joblib.load` **deserializes with pickle**, so a
crafted `.joblib` executes arbitrary code exactly like a raw pickle. The
`app/ml/loader.py` docstring claimed local files are a "non-pickle format" and that
"pickles are refused before any code can run" — both incorrect. The real protection
is the existing artifact-root confinement in `validate_model_uri`.

**Applied:** Corrected the misleading docstrings/comments to state plainly that
`.joblib` is pickle-backed and that artifact-root confinement (not the suffix
allowlist) is the control. Added a size guard (`ML_MAX_MODEL_SIZE_MB`) evaluated
**before** the deserializer runs to bound the resource-exhaustion case. Tests:
`tests/ml/test_security.py::test_load_model_rejects_oversized_joblib`.

### #4 — SSRF in connectors (no allowlist) — **Open (Medium)**

User-controlled connection fields are passed straight to clients with no
allowlist / internal-IP blocking: S3/Azure `endpoint_url`, and SQL/Mongo
`host`/`port`. With the API exposed, a connection can point the server at
`http://169.254.169.254/...` (cloud metadata) or internal hosts; `test_connection`
acts as a connectivity oracle.

**Recommendation:** Add an opt-in allow/deny list for connector endpoints/hosts
(block link-local `169.254.0.0/16` and RFC1918 by default for non-local
deployments).

### #5 — Local-storage connector root was unconfined — **Fixed**

`app/connectors/local_storage.py` correctly blocks path traversal *within* a root,
but the root itself (`conn.database`) was arbitrary — a Local Storage connection
could point at `/`, `/etc`, `~/.aws`, etc., enabling server-side file
read/write/enumeration.

**Applied:** Added an **opt-in** confinement setting
`FLOWFRAME_STORAGE_ALLOWED_ROOTS`. Empty (default) preserves historical behavior
(the connector's purpose is reading local folders); when set, a Local Storage
root must resolve inside one of the listed directories or the connection is
refused. Tests:
`tests/test_connectors.py::test_local_storage_root_*`.

### #6 — Plugin licensing fails open and `license_required` is never enforced — **Open (Medium)**

`ServiceRegistry.validate_license` returns *licensed* when no provider is registered
(fail-open), and the manifest `license_required` flag is parsed but never checked in
the load path. A plugin marked `license_required: true` still loads and runs without
a valid license. The token check itself (Ed25519) is sound, but the token cache is
local and user-writable, so it deters casual use rather than enforcing access.

**Not auto-changed:** Enforcing `license_required` is entangled with the licensing
product/business logic and would change the load path for the open-source default
(no provider registered). Left for a maintainer decision. The licensing mechanism
should not be relied on as a security boundary.

### #7 — Plugin upload buffered fully in memory before the size check — **Fixed**

`POST /api/plugins/install` did `await file.read()` (whole body into memory)
*before* checking `max_upload_bytes` — a cheap memory-exhaustion DoS.

**Applied:** The upload is now streamed to a temp file in bounded 1 MiB chunks and
aborted with 413 as soon as the limit is crossed. Test:
`tests/api/test_plugin_install_and_marketplace.py::test_install_rejects_oversized_upload`.

### #8 — API install force-overwrites an installed plugin of the same id — **Open (Low)**

`install_package_and_report` installs with `force=True`, so an upload silently
replaces an already-installed plugin sharing the same id. With the default
`REQUIRE_TRUSTED_PLUGINS=False`, an unsigned replacement is accepted. Gated by #1
(no auth) and the enable/grant step before the new code runs.

**Recommendation:** Consider requiring an explicit `force` flag from the API caller
to overwrite, and/or warn when replacing a previously-trusted plugin with an
unsigned package.

---

## Summary

| # | Area | Severity | Status |
|---|------|----------|--------|
| 1 | Unauthenticated API + RCE when exposed (Docker `0.0.0.0`) | High (contextual) | **Mitigated** (opt-in `FLOWFRAME_API_TOKEN`) |
| 2 | Plugin permissions are load-time only, no sandbox | High (design) | **Partially mitigated** (explicit approval + disclosure) |
| 3 | `.joblib` mislabeled as non-pickle/safe | Medium | **Fixed** |
| 4 | SSRF via connector endpoints/hosts | Medium | Open (recommendation) |
| 5 | Local-storage root unconfined | Medium | **Fixed** (opt-in) |
| 6 | Licensing fails open / `license_required` unenforced | Medium | Open (product decision) |
| 7 | Upload buffered before size check | Low | **Fixed** |
| 8 | API force-overwrite of installed plugin | Low | Open (recommendation) |

The cryptographic and archive-extraction defenses are solid. The dominant risk —
an unauthenticated API exposed by the Docker `0.0.0.0` bind (#1) — is now mitigated
by the opt-in `FLOWFRAME_API_TOKEN` gate plus a startup warning. The plugin trust
model (#2) is improved: no plugin code runs without an explicit user opt-in, and
the UI/docs are honest that there is no runtime sandbox. The remaining open items
are connector SSRF (#4) and the lower-severity install-overwrite (#8); licensing
(#6) is a product decision left to the maintainers.
