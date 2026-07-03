---
title: Plugin Security & Permissions
description: How Ciaren gates, verifies, and isolates plugins
search: plugin security permissions signature verification approve enable disable
---

# Plugin Security & Permissions

Plugins extend Ciaren with real Python code. Ciaren's job is to make that
**explicit and consensual**: you see what a plugin wants, you approve it, and you
can verify where it came from. It is a trust/consent boundary, **not** an OS
sandbox — read the [local-first trust model](/security/local-first-trust-model)
for what that does and doesn't guarantee.

::: danger Only install plugins you trust
A plugin is ordinary Python that runs on your machine with your account's access
and is **not sandboxed**. A malicious or buggy plugin can read or delete your
files, use your saved credentials, run other programs, or send data over the
network — and the permission list is a heads-up, **not** an enforced limit.
Install only plugins from sources you trust and whose code you can review (prefer
signed packages from a [trusted key](#signature-verification)). Ciaren cannot
vet third-party plugins and is **not responsible** for what they do once you
install and approve them. You install plugins at your own risk.
:::

## Permissions

A plugin declares the permissions it needs in its [manifest](/specs/plugin-manifest):

```json
{ "permissions": ["network", "credentials", "filesystem_read"] }
```

Recognised permissions include: `filesystem_read`, `filesystem_write`, `network`,
`credentials`, `subprocess`, `shell`, `docker`, `local_model_load`, `joblib_load`,
`database_access`, `cloud_access`, `llm_access`, `telemetry`.

### Enforced permissions for model loading

Most permissions are disclosure — surfaced before you approve, not enforced at
runtime (see the honest-boundary note above). Two are **actively enforced** by
the host's plugin ModelStore, because deserializing a model executes pickled
code:

- `local_model_load` (or `joblib_load`) — required for a plugin to load a model
  from an MLflow `runs:/` / `models:/` URI;
- `joblib_load` — required for a plugin to load a local `.joblib` file, which
  must additionally live **inside the server's artifact directory** (path
  traversal is refused). Bare `.pkl` / `.pickle` files are always refused.

Persisting a model (training) needs no grant — it writes to the server-managed
MLflow store, the same place core train nodes log to.

### Opt-in runtime enforcement

By default the other permissions are disclosure-only. You can turn on a second,
**opt-in** layer that actively checks a plugin's *granted* permissions against its
own code while a plugin node runs, using a CPython audit hook. Set
`CIAREN_PLUGIN_PERMISSION_ENFORCEMENT`:

| Mode | Behaviour |
| --- | --- |
| `off` *(default)* | No hook installed, zero overhead. Permissions stay advisory. |
| `warn` | Logs when a plugin performs a `network` / `filesystem_write` / `subprocess` / `shell` action it wasn't granted — an audit trail; nothing is blocked. |
| `enforce` | Additionally raises `PermissionError`, so the ungranted action fails and the node reports an error. |

Turn it on for shared or less-trusted setups where you run third-party plugins
and want a real signal (or block) when one reaches beyond what it declared.

::: warning Still not a sandbox
This raises the bar and gives you an audit trail — it does **not** contain a
determined plugin. A plugin can still escape the check via a thread it spawns, a
child process, or native code, and filesystem *reads* are never blocked (the
import system and pandas open files constantly). For untrusted code that needs
network access, use OS/network-level egress control; for sensitive IP, keep the
logic in a remote service (see [thin-client plugins](#thin-client-plugins)). The
`enforcement` mode in effect is reported as `permission_enforcement` in
`GET /api/plugins/diagnostics`.
:::

### Plugin connectors

A plugin connector's runtime (test / list / read / write) only exists once the
plugin is approved — a gated plugin's connectors appear nowhere. The host also
applies its [SSRF guard](/guide/advanced-setup#environment-variables) to the
connection's host field before invoking a plugin runtime, and connection
secrets keep the env-var-only rule: the resolved value is passed into a single
call and never stored.

### Approval gating

For **drop-in** plugins (those discovered from a plugin directory with a
`ciaren-plugin.json`):

- A plugin that declares permissions starts **pending** — *its entry point is
  never imported* — until you grant those permissions.
- You approve via the API or UI; the registry rebuilds and the plugin loads live.
- Revoking a required permission sends it back to pending (its code stops loading).
- Any plugin can be disabled; a disabled plugin is never loaded.

Entry-point packages (ones you deliberately `pip install`) load without this gate —
installing the package was the consent step.

### Managing permissions

| Surface | How |
| --- | --- |
| UI | The **Plugins** page shows each plugin's status; clicking a plugin opens its details with requested vs. granted permissions and the Approve / Revoke / Enable / Disable actions. A loaded plugin shows its permissions as active; revoking the ones you granted sends it back to pending. Status and signature badges explain themselves on hover. |
| API | `POST /api/plugins/{id}/enable\|disable\|grant\|revoke` — see [Catalog & Plugins API](/api/catalog). |
| CLI | `ciaren-plugin enable\|disable <id>` — see [Plugin CLI reference](/plugins/cli-reference). |

State (enabled + granted permissions) persists in `plugin_state.json` under the
data dir (override with `CIAREN_PLUGIN_STATE_FILE`).

## Signature verification

Plugins distribute as signed [`.ciarenplugin`](/plugins/packaging-and-distribution)
packages. Ciaren verifies a detached Ed25519 signature against your **trusted
keys** before installing:

| Outcome | Meaning | Installable |
| --- | --- | --- |
| `trusted` | Valid signature from a key you trust | ✅ |
| `untrusted` | Valid signature, key not in your trusted set | ✅ (warned) |
| `unsigned` | No signature (typical for community plugins) | ✅ (warned) |
| `invalid` | Digest mismatch or bad signature | ❌ always refused |

Require a trusted signature with `ciaren-plugin install pkg.ciarenplugin --trusted`.
Trusted keys come from three sources: keys **pinned into the app itself** (the
official marketplace publisher keys — these verify as trusted out of the box and
can never be overridden by configuration), plus your own additions via
`CIAREN_TRUSTED_PLUGIN_KEYS` and `~/.ciaren/trusted_keys.json`.
Signing/verifying needs `ciaren[signing]`.

What signatures protect against: tampered packages, swapped downloads, and
unofficial builds presented as official. What they **don't**: a signed-but-buggy
plugin, or someone copying already-installed files.

The signature covers the package digest **and** the signer metadata (`key_id`,
`publisher`, `algorithm`), and trust is matched strictly by `key_id` — a
package-supplied `publisher` name can never select which trusted key is checked.
So a validly-signed package can't be relabelled to impersonate a trusted key.

### Reinstalls re-gate on identity change (TOFU)

Plugin ids are claimable, so approval is pinned to the **signer**, not the id:
Ciaren records which key signed a plugin at install time, and a reinstall that is
signed by a *different* key, arrives *unsigned* where the previous install was
signed, or drops from `trusted` sends the plugin back to **pending** — its new
code stays un-imported until you approve the new publisher. A normal update
(same key) keeps your approval.

### Marketplace trust badges are earned, not claimed

The `trust` tier shown for an Explore catalog entry is **derived by verifying
the artifact's signature against your trusted keys** — a `trust` value written
into the index or manifest by the publisher is ignored. Likewise, a catalog
entry without a `digest` is refused at install rather than skipped: the digest
is what binds the entry to the artifact bytes.

### Install-time hardening

Installation extracts a `.ciarenplugin` defensively: entry names are validated
lexically (absolute paths, `..`, and `\`/drive-qualified paths are rejected) and
again after path resolution, **symlink entries are refused**, and per-entry/total
uncompressed size and entry-count caps bound a decompression bomb. Plugin ids that
aren't filesystem-injective (anything outside `[A-Za-z0-9._-]`) are rejected rather
than silently rewritten, so one plugin can't clobber another's install directory.

## Dangerous capabilities

Some operations execute code or touch credentials. Ciaren already enforces:

- **Pickle model files are refused** — loading a pickle runs arbitrary code; only
  `.joblib` / native `.json` artifacts load, and only from inside the artifact root.
- **Connection secrets are referenced, not stored** — passwords live in environment
  variables (`password_env`); they never enter the flow graph, `.flow` files, or
  exported code.
- **Custom SQL / Python** runs with local-process privileges — fine for local use;
  for shared environments add read-only connections and audit logging (roadmap).

## Thin-client plugins

Because an installed plugin's code runs on the user's machine, its logic can be
read (a `.ciarenplugin` is a zip; compiled `.pyc` only deters casual inspection)
and its local license check can be patched out. The robust pattern for **paid or
sensitive** plugins is therefore a *thin client*: keep the valuable logic on your
own server, and ship a small plugin that calls it. A node receives its plugin's
own signed license token via `NodeContext.license_token` and forwards it with each
request; your server validates the token (signature, expiry, revocation, quota)
and does the work — the enforcement lives where the user cannot patch it. See the
[API reference](/plugins/api-reference#nodecontext) and the marketplace plan for
the full pattern.

## Known limitations

Ciaren is honest about what the plugin system does and doesn't guarantee:

- **Not a sandbox.** An enabled plugin runs unsandboxed Python with your full
  account access. Permissions are a disclosure/consent boundary; only model-load is
  enforced by the host, and the opt-in [runtime enforcement](#opt-in-runtime-enforcement)
  above is a bar-raiser, not containment.
- **You are the reviewer.** Ciaren cannot vet third-party plugin code. Signatures
  prove *who* published a package and that it wasn't altered — not that it is safe.
  Install only plugins whose source you trust and can inspect (`.ciarenplugin` files
  are plain zips; unzip and read them, or read the installed files under
  `~/.ciaren/plugins/<id>`).
- **Compatibility is checked, safety is not.** Install refuses a package whose
  declared `ciaren`/`api_version` is incompatible with this build (before it can
  replace a working install), and extraction is hardened against zip-slip / symlink
  / zip-bomb packages — but none of that judges what approved code *does*.
- **Local licensing is soft.** A cached license token can't be forged (it's signed)
  but the local gate can be bypassed by editing the code that runs on your machine.
  Treat local licensing as UX; put real entitlement/quota enforcement server-side.
- **Bytecode is not protection.** `--compile` (ship `.pyc`) deters casual reading
  only; bytecode decompiles.

When in doubt, don't approve a plugin — a gated plugin's code never runs.

## Recommendations

- Prefer signed plugins from trusted publishers; use `--trusted` in shared setups.
- Review a plugin's requested permissions **and its code** before approving.
- In shared/less-trusted deployments, set `CIAREN_PLUGIN_PERMISSION_ENFORCEMENT=warn`
  (or `enforce`) and, for plugins that need outbound access, add network-level
  egress control.
- Keep `cryptography` installed (`ciaren[signing]`) so signatures are verified
  rather than skipped.
- Run a dependency license/vulnerability scan before distributing builds (the repo
  ships CodeQL + dependency-audit CI workflows).

## See also

- [Local-first trust model](/security/local-first-trust-model)
- [Packaging & Distribution](/plugins/packaging-and-distribution)
- [Plugin manifest](/specs/plugin-manifest)
