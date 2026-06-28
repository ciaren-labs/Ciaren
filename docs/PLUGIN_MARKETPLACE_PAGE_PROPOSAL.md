# Plugin Marketplace / Install Page — Validation & Proposal

> **Status: design proposal, not implemented.** This document validates the idea
> of a marketing/marketplace web page where people can browse and install
> FlowFrame plugins (including paid ones), and recommends the safest architecture.
> No marketplace web page, hosted index, in-app URL install, or license-issuing
> service exists in the codebase yet. Nothing here describes shipped behaviour.

The request: *"a marketing-type page where people can install plugins, and this
reads our private configuration, so paid plugins really stay private."*

The key tension to resolve up front: **a web page must never hold the secrets
that make the trust model work.** The signing private key, the license-issuing
private key, and the user's trusted-key set / license cache are all things the
browser must not see. The proposal below keeps every privileged operation either
in the **local FlowFrame app** (which already holds trusted keys and the license
cache) or in a **server-side signing service** (which holds the private keys),
and lets the marketing page be a thin, public catalog.

---

## 1. What already exists (validated against the code)

| Building block | Where | Reusable as-is? |
| --- | --- | --- |
| `.ffplugin` package + deterministic digest | `app/plugins/package.py` | ✅ |
| Detached Ed25519 signature, metadata-bound, trust by `key_id` | `app/plugins/package.py`, `app/plugin_api/signing.py` | ✅ |
| Verify before install; refuse tampered; `--trusted` policy | `app/plugins/install.py` | ✅ |
| Hardened extraction (zip-slip, symlink, zip-bomb) | `app/plugins/install.py` | ✅ |
| Permission gating (code not imported until approved) | `app/plugins/loader.py`, `state.py` | ✅ |
| Marketplace **index** data contract (`schemaVersion`, entries, `downloadUrl`, `digest`, `keyId`, `licenseRequired`) | `app/plugins/marketplace.py` | ✅ (parsed; not yet fetched) |
| Signed **license token** + offline grace + local cache + `TokenLicenseProvider` | `app/plugins/licensing.py` | ✅ |
| In-app Plugins page (approve / enable / disable / revoke) | `frontend/src/features/plugins/` | ✅ |

**What is missing for an install page:**

1. No code fetches anything over the network. `load_index` reads a **local** file
   only (`app/plugins/marketplace.py`); there is no download path for a
   `downloadUrl` and no hosted index client.
2. No backend endpoint installs a plugin from a URL — install is CLI-only today
   (`flowframe plugin install <file>`), and the API exposes only
   enable/disable/grant/revoke (`app/api/routes/plugins.py`).
3. No license-issuing service and no authenticated "download my license token"
   flow.
4. The plugin-management API has **no authentication** (consistent with the
   local-first, single-user app) — adding any "install from the web" path makes
   that gap load-bearing (see §5).

So the install page is **feasible and well-supported by the existing contracts**,
but it requires net-new network + auth surface that must be designed carefully.

---

## 2. Recommended architecture

Three tiers, with secrets isolated to where they belong:

```text
┌────────────────────────────┐     public, no secrets
│  Marketing / Marketplace   │  ← static site: reads a PUBLIC marketplace.json
│  web page (browser)        │    (name, version, capabilities, permissions,
│                            │     downloadUrl, digest, keyId, licenseRequired)
└─────────────┬──────────────┘
              │  "Install in FlowFrame" handoff (no secrets cross here)
              ▼
┌────────────────────────────┐     holds trusted keys + license cache
│  Local FlowFrame app        │  ← fetches the signed .ffplugin, RE-VERIFIES
│  (backend + Plugins page)   │    digest+signature against trusted keys,
│                            │    gates permissions, installs locally
└─────────────┬──────────────┘
              │  authenticated "give me my license token"
              ▼
┌────────────────────────────┐     holds the PRIVATE signing keys
│  Licensing / signing service│  ← after purchase, signs a license token bound
│  (server-side, optional)    │    to (userId, pluginId, expiry); never exposes
│                            │     the private key to the browser or the app
└────────────────────────────┘
```

### 2.1 The marketing page is a thin, public catalog

- It renders entries from a **public** `marketplace.json` (the existing
  `MarketplaceIndex` shape). Everything in the index is non-secret metadata.
- For each plugin it shows: name, publisher, version, capabilities, the exact
  **permissions** it will request (reuse the in-app permission copy), trust tier,
  price, and whether a license is required.
- It does **not** verify signatures, hold trusted keys, or hold license secrets.
  The browser is an untrusted display surface.

### 2.2 "Install in FlowFrame" hands off to the local app

The page should not push a package into the app silently. Two handoff mechanisms,
pick by product form factor:

- **Local web app / CLI product (today): a deep link to the running app.** The
  button opens `http://127.0.0.1:8055/plugins?install=<id>&index=<indexUrl>` (or
  POSTs to a new `POST /api/plugins/install-from-url`). The local app then:
  1. fetches the index entry and the `.ffplugin` from `downloadUrl`,
  2. checks the downloaded artifact's digest against the index `digest`,
  3. runs `verify_package` against the user's **trusted keys**,
  4. shows an **in-app confirm dialog** (publisher, trust outcome, the permission
     list) — the user approves in the local UI, not on the web page,
  5. installs via the existing hardened `install_ffplugin`, then permission-gates
     as usual.
- **Future desktop app: a custom protocol handler** `flowframe://install?…` that
  the OS routes to the installed app, which runs the same 1–5 steps. Cleaner UX,
  but needs a registered desktop app.

The critical rule either way: **the local app re-fetches and re-verifies.** The
web page is never trusted to assert "this is safe/trusted" — it only names what to
install. Trust is decided locally against locally-held keys.

### 2.3 Paid plugins: license issuing stays server-side

- Purchase happens on the marketing site / a billing provider. On success, a
  **server-side licensing service** (holding the issuer **private** key) signs a
  `LicenseToken` bound to `userId` + `pluginId` + `expiresAt` + `offlineGraceUntil`
  (exactly the `app/plugins/licensing.py` shape).
- The local app, after the user signs in, calls an **authenticated** endpoint to
  download *their* token, caches it (`LicenseCache`), and the plugin's
  `TokenLicenseProvider` validates it locally — working offline until the grace
  date. The private key never leaves the service; the browser never holds it.
- The paid plugin's *code* is protected separately by shipping it as a
  **compiled (`--compile`) `.ffplugin`** (deters casual inspection) and/or keeping
  the sensitive logic in a remote API. License tokens gate *use*; bytecode/remote
  gates *source disclosure*. Neither is unbreakable DRM — that is by design
  (architecture plan §14/§15).

---

## 3. On "the page reads our private configuration"

Read literally, a public web page reading FlowFrame's private config would be the
**wrong** design and a security hole — signing keys and trusted-key sets must not
be exposed to a browser. The safe interpretation, which this proposal follows:

- **Trusted keys / license cache** are *the local app's* private configuration.
  The install flow uses them **locally** to decide trust and licensing.
- **Private signing keys** are the *service's* private configuration, used only
  server-side to sign packages and license tokens.
- The web page consumes only **public** outputs of that config: the marketplace
  index and already-signed artifacts/tokens delivered to the authenticated user.

If "our private configuration" instead means a **private/internal marketplace
index** (a curated, non-public catalog of first-party plugins), that is fine and
easy: serve a private `marketplace.json` from an authenticated URL; the local app
fetches it with the user's credentials. That keeps the *catalog* private without
ever putting *secrets* in the browser. **This is the one product decision worth
confirming with the owner** (public vs. authenticated index).

---

## 4. Suggested phasing (when this is greenlit)

1. **Index fetch (read-only, low risk).** Add an HTTP client to
   `marketplace.py` (`parse_index` already accepts a response body) and a
   `GET /api/marketplace` proxy. Validate scheme (https only); no install yet.
2. **In-app install-from-URL with confirm.** `POST /api/plugins/install-from-url`
   → download, digest-check against the index entry, `verify_package`, **explicit
   in-app confirm**, `install_ffplugin`. Gate behind the auth decision in §5.
3. **Marketing page** rendering the public index + "Install in FlowFrame" handoff.
4. **Licensing service + authenticated token download** for paid plugins.
5. **Compiled + signed premium artifact** as the first paid pilot.

---

## 5. Security prerequisites before any "install from the web" ships

These are the gaps a network install path turns from theoretical into real:

- **Authenticate state-changing plugin endpoints.** Today enable/grant/install
  have no auth (local-first). The moment a web page can trigger install/enable,
  a malicious page (CSRF against `127.0.0.1`) or any local process could turn a
  dropped package into code execution. Require a confirm step **and** a
  non-CORS-bypassable check (e.g. the `X-FlowFrame-Secret` pattern the webhook
  already uses), and never auto-grant *all* permissions without explicit consent.
- **Validate `downloadUrl` (SSRF).** Allow `https://` only; block `file://` and
  private/loopback IP ranges; enforce the advertised `digest` before install.
- **Keep `--trusted` the default for the marketplace path.** Unsigned/untrusted is
  acceptable for hand-installed community plugins, but a one-click web install of
  a *paid* plugin should require a trusted signature.
- **Re-verify locally, always.** The page's claims (trust tier, permissions) are
  display only; the local app re-computes digest, signature, and permission
  gating from the artifact itself.

---

## 6. Recommendation

Build it as a **thin public catalog + local-app handoff + server-side license
issuing**, never as a page that reads private keys. The data contracts
(`MarketplaceIndex`, `PackageSignature`, `LicenseToken`) and the local install +
permission machinery already exist and are sufficient; the net-new work is a
guarded index-fetch/install path, the marketing page, and a licensing service —
in that order. Before the first network install ships, close the auth/SSRF
prerequisites in §5. Confirm with the product owner whether the index is **public
or authenticated/private** — that single answer shapes the catalog tier.

## See also

- [Plugin Architecture Plan](./PLUGIN_ARCHITECTURE_PLAN.md) (§13 signatures, §14
  licensing, §15 distribution)
- [Packaging & Distribution](./plugins/packaging-and-distribution.md)
- [Plugin Security & Permissions](./security/plugin-security.md)
