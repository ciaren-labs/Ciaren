---
title: Packaging & Distribution
description: Build, sign, verify, install, and distribute FlowFrame plugins
search: plugin package ffplugin sign signature verify install marketplace license
---

# Packaging & Distribution

FlowFrame plugins distribute as **`.ffplugin`** packages — a plain zip containing
the plugin's manifest, its Python package, and an optional detached Ed25519
signature. The same format works for free community plugins and signed premium
plugins; the open-source core never needs to change to support either.

::: warning Install only plugins you trust
A plugin runs unsandboxed Python on your machine with your access. Install only
plugins from sources you trust and whose code you can review — prefer signed
packages from a trusted key. FlowFrame cannot vet third-party plugins and is not
responsible for their behaviour. See [Plugin Security](/security/plugin-security).
:::

> Signing/verifying needs the optional `cryptography` dependency:
> `pip install "flowframe[signing]"`. Hashing and unsigned packages work without it.

## The `.ffplugin` format

A zip archive with:

| Entry | Required | Purpose |
| --- | --- | --- |
| `flowframe-plugin.json` | ✅ | The [manifest](/specs/plugin-manifest). |
| your package (e.g. `acme_hello/…`) | ✅ | The code the manifest `entrypoint` points at. |
| `flowframe-signature.json` | optional | Detached signature `{algorithm, publisher, key_id, digest, signature}`. |

The **digest** is a deterministic SHA-256 over every entry except the signature
file, so a tampered package never matches its signature.

## Build and sign (publishers)

```bash
# 1. Generate a signing keypair once; keep the private key secret.
flowframe plugin keygen

# 2. Package a plugin source directory into an unsigned .ffplugin.
flowframe plugin pack ./my-plugin ./my-plugin-1.0.0.ffplugin

# 3. Sign it in place.
flowframe plugin sign ./my-plugin-1.0.0.ffplugin \
  --key <private_hex> --key-id acme-2026 --publisher acme
```

Publish the **public** key so users can trust it:

```bash
export FLOWFRAME_TRUSTED_PLUGIN_KEYS='{"acme-2026": "<public_hex>"}'
```

Trusted keys are read from `FLOWFRAME_TRUSTED_PLUGIN_KEYS` (a JSON object) and
`~/.flowframe/trusted_keys.json`. The signature covers the package digest **and**
the signer metadata (`key_id`, `publisher`, `algorithm`), so a valid signature
can't be relabelled to impersonate a different key.

### Shipping compiled bytecode (paid plugins)

By default a `.ffplugin` carries your `.py` source — anyone can unzip and read it.
For a paid plugin you can ship compiled bytecode instead:

```bash
flowframe plugin pack ./my-plugin ./my-plugin-1.0.0.ffplugin --compile
```

With `--compile`, every `.py` is compiled to optimized `.pyc` (docstrings and
`assert`s stripped) and only the bytecode ships — the source is omitted. The
loader imports the bare `.pyc` transparently, so the plugin still runs.

::: warning Bytecode is a deterrent, not real protection
A `.pyc` can still be decompiled back to near-original logic, and it is **locked to
the Python version it was built with** (a 3.12 build won't load on 3.13) — build
one artifact per supported Python version. For genuinely sensitive IP (an AI
optimizer, a proprietary algorithm), keep the logic in a remote service the plugin
calls, rather than shipping it to the user's disk at all. See the architecture plan
§15 — "do not assume Python source can be fully hidden."
:::

## Verify and install (users)

```bash
flowframe plugin verify ./my-plugin-1.0.0.ffplugin   # trusted | untrusted | unsigned | invalid
flowframe plugin install ./my-plugin-1.0.0.ffplugin  # extracts to ~/.flowframe/plugins/<id>
flowframe plugin install ./my-plugin-1.0.0.ffplugin --trusted   # refuse unless signed by a trusted key
flowframe plugin list
flowframe plugin uninstall acme.myplugin
```

Verification outcomes:

- **trusted** — valid signature from a key you trust.
- **untrusted** — valid signature, but the key isn't in your trusted set.
- **unsigned** — no signature (fine for community plugins).
- **invalid** — digest mismatch or bad signature → **install is always refused**.

Installation extracts into `~/.flowframe/plugins` (override with
`FLOWFRAME_PLUGIN_INSTALL_DIR`), a directory the loader scans, so the plugin loads
on the next start. Path-traversal entries are rejected. A drop-in plugin that
declares permissions still starts **pending** until you approve it — see
[plugin security](/security/plugin-security).

## Install from the app

The **Plugins** page has an **Install plugin** button that uploads a local
`.ffplugin` (`POST /api/plugins/install`). It runs the same verification and
permission gating as the CLI — a tampered/invalid package is refused, and a
plugin that declares permissions stays pending until you approve it. Set
`FLOWFRAME_REQUIRE_TRUSTED_PLUGINS=true` to refuse unsigned/untrusted uploads.

## Marketplace index

A marketplace is just a JSON index of installable plugins (no hosted compute, no
billing in the core):

```json
{
  "schemaVersion": "1.0.0",
  "plugins": [
    {
      "id": "acme.databricks",
      "name": "Databricks Connector",
      "version": "1.2.0",
      "publisher": "acme",
      "license": "commercial",
      "capabilities": ["connector.databricks"],
      "nodes": ["databricks.query"],
      "nodeCategories": { "databricks.query": "input" },
      "permissions": ["network", "credentials"],
      "downloadUrl": "https://example/acme-databricks-1.2.0.ffplugin",
      "keyId": "acme-2026",
      "licenseRequired": true
    }
  ]
}
```

Author an index by adding packed plugins to it — the digest and signing key id
are recorded automatically, and the artifact is referenced relative to the index
file so the catalog stays portable:

```bash
flowframe plugin index add ./acme-databricks-1.2.0.ffplugin --index ./marketplace.json
flowframe plugin search databricks --index ./marketplace.json
```

### The "Explore" catalog

By default, FlowFrame ships a small bundled **Explore** catalog with an installable
Hello Plugin so users can try the plugin installation flow without downloading
anything. Point `FLOWFRAME_MARKETPLACE_INDEX` at a local `marketplace.json` to
replace that catalog, or set it to `none` to hide Explore. The Plugins page lists
catalog entries
(`GET /api/marketplace`), marking which are already installed. Entries whose
artifact is available locally install in one click
(`POST /api/marketplace/{id}/install`) — FlowFrame re-checks the advertised
digest and verifies the signature before installing. Catalog entries also expose
the manifest's `ui.nodes` as `nodes` and `ui.nodeCategories` as `node_categories`,
so users can see which editor node types and palette subgroups will appear after
install and approval. Missing or invalid categories default to `plugins`. Entries that point at a
remote URL must be downloaded and installed manually for now; a hosted index with
network download is a drop-in later (same setting accepts an `https://` URL, same
API contract).

## Premium licensing (optional)

Premium plugins can require a signed **license token** that runs locally and keeps
working offline until an expiry/grace date:

```json
{
  "userId": "u-123",
  "pluginId": "acme.databricks",
  "licenseType": "pro",
  "expiresAt": "2027-01-01T00:00:00Z",
  "offlineGraceUntil": "2027-01-15T00:00:00Z",
  "signature": "…"
}
```

A premium plugin registers its own `TokenLicenseProvider` (from
`app.plugins.licensing`) pointed at the issuer's public key; the core's
`ServiceRegistry.validate_license` then consults it. The open-source core ships no
premium licensing of its own — this is reusable infrastructure for plugin authors.
Local licensing deters casual misuse; it is not unbreakable DRM.

The token lifecycle is fully local — no license server is required to *use* a
token, only to *issue* it:

```bash
# Publisher mints a signed token (after a purchase, server-side):
flowframe plugin license issue --key <private_hex> --user u-123 --plugin acme.databricks \
  --expires 2027-01-01T00:00:00Z --grace 2027-01-15T00:00:00Z --out token.json

# User caches it locally; the plugin's provider then validates it offline:
flowframe plugin license import token.json
flowframe plugin license status acme.databricks --key <issuer_public_hex>
```

`GET /api/plugins/{id}/license` reports the resolved status, and the Plugins page
shows a **license badge** for plugins whose provider answers. It also shows a
**signature badge** (`Trusted` / `Untrusted key` / `Unsigned`) recording how each
installed package verified.

## See also

- [Writing a plugin](/plugins/writing-a-plugin)
- [Plugin manifest](/specs/plugin-manifest)
- [Catalog & Plugins API](/api/catalog)
