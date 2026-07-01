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
| UI | The **Plugins** page lists each plugin's status, requested vs. granted permissions, and Approve / Revoke / Enable / Disable actions. A loaded plugin shows its permissions as active; revoking the ones you granted sends it back to pending. |
| API | `POST /api/plugins/{id}/enable\|disable\|grant\|revoke` — see [Catalog & Plugins API](/api/catalog). |
| CLI | `ciaren plugin enable\|disable <id>` — see [CLI reference](/guide/cli). |

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

Require a trusted signature with `ciaren plugin install pkg.ciarenplugin --trusted`.
Trusted keys come from `CIAREN_TRUSTED_PLUGIN_KEYS` and
`~/.ciaren/trusted_keys.json`. Signing/verifying needs `ciaren[signing]`.

What signatures protect against: tampered packages, swapped downloads, and
unofficial builds presented as official. What they **don't**: a signed-but-buggy
plugin, or someone copying already-installed files.

The signature covers the package digest **and** the signer metadata (`key_id`,
`publisher`, `algorithm`), and trust is matched strictly by `key_id` — a
package-supplied `publisher` name can never select which trusted key is checked.
So a validly-signed package can't be relabelled to impersonate a trusted key.

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

## Recommendations

- Prefer signed plugins from trusted publishers; use `--trusted` in shared setups.
- Review a plugin's requested permissions before approving.
- Keep `cryptography` installed (`ciaren[signing]`) so signatures are verified
  rather than skipped.
- Run a dependency license/vulnerability scan before distributing builds (the repo
  ships CodeQL + dependency-audit CI workflows).

## See also

- [Local-first trust model](/security/local-first-trust-model)
- [Packaging & Distribution](/plugins/packaging-and-distribution)
- [Plugin manifest](/specs/plugin-manifest)
