---
title: Plugin CLI Reference
description: The ciaren-plugin command — install, inspect, sign, and license plugins
search: cli ciaren-plugin install uninstall verify enable disable keygen pack sign manifest search index license licenses
---

# Plugin CLI Reference

Installing Ciaren (`pip install --pre ciaren`, or `pip install -e .` from a
source checkout) exposes a `ciaren-plugin` command —
a separate entry point from `ciaren` for the plugin lifecycle (install,
enable/disable) and, for publishers, authoring tooling (signing, packaging,
manifest generation, marketplace indexing, license issuance). It's split out
so the everyday [`ciaren`](/guide/cli) surface used to run the app stays
small. Publisher tooling (`keygen` / `sign`) additionally needs
`pip install ciaren[signing]`; everything else works with the base install.

```bash
ciaren-plugin --help
ciaren-plugin --version
```

::: tip Moved from `ciaren plugin`
Plugin commands used to live under `ciaren plugin ...`. Running that form now
prints a pointer to `ciaren-plugin` instead of failing with an opaque
"invalid choice" error.
:::

```bash
ciaren-plugin list                          # discovered plugins + status
ciaren-plugin install my-plugin.ciarenplugin    # verify + install
ciaren-plugin install ./src --dir           # install from a source directory
ciaren-plugin install my-plugin.ciarenplugin --trusted   # require a trusted signature
ciaren-plugin uninstall acme.myplugin
ciaren-plugin verify my-plugin.ciarenplugin     # trusted | untrusted | unsigned | invalid
ciaren-plugin enable acme.myplugin
ciaren-plugin disable acme.myplugin

# Publisher tooling (needs `ciaren[signing]`):
ciaren-plugin keygen                         # generate an Ed25519 keypair
ciaren-plugin pack ./src out.ciarenplugin        # build an unsigned package
ciaren-plugin pack ./src out.ciarenplugin --compile   # ship .pyc bytecode, not source
ciaren-plugin sign out.ciarenplugin --key <hex> --key-id acme-2026 --publisher acme

ciaren-plugin search databricks --index ./marketplace.json
ciaren-plugin index add out.ciarenplugin --index ./marketplace.json   # author the catalog
ciaren-plugin manifest ./src                 # generate ciaren-plugin.json from the plugin's code

ciaren-plugin licenses                       # scan installed dependency licenses
ciaren-plugin licenses --flagged-only --fail-on-flagged   # CI gate
```

| Subcommand | Description |
| --- | --- |
| `list` | List discovered plugins (loaded / disabled / pending) and load errors. |
| `install` | Verify and install a `.ciarenplugin` (or `--dir` source). `--trusted` requires a trusted signature; a tampered package is always refused. `--force` overwrites an existing install. |
| `uninstall` | Remove an installed plugin and forget its state. |
| `verify` | Report a package's signature/integrity outcome (exits non-zero if `invalid`). |
| `enable` / `disable` | Toggle whether a plugin loads. |
| `keygen` / `pack` / `sign` | Publisher tooling to create and sign packages. `pack --compile` ships `.pyc` bytecode instead of source. |
| `manifest` | Generate `ciaren-plugin.json` from a plugin's code (single source of truth); `--api-version` targets an older plugin-contract minor. |
| `search` | Search a local marketplace index file. |
| `index add` | Add/replace a packed plugin's entry in a marketplace index (records digest + signing key id). |
| `license issue` | Sign a license token for a user + plugin (publisher; needs the private key). |
| `license import` | Cache a received license token locally so the plugin validates it. |
| `license status` | Show a cached token's user/expiry; `--key <issuer public hex>` verifies the signature. |
| `licenses` | Scan installed Python dependency licenses for redistribution review; `--flagged-only` / `--fail-on-flagged` for CI. |

## See also

- [`ciaren` CLI Reference](/guide/cli) — the main command that runs the app
- [Installing & Managing Plugins](/plugins/managing-plugins)
- [Packaging & Distribution](/plugins/packaging-and-distribution) — the full publishing workflow
- [Plugin Security & Permissions](/security/plugin-security)
