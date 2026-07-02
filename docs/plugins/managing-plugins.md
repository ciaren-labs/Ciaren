---
title: Installing & Managing Plugins
description: Install, approve, disable, and uninstall Ciaren plugins from the Plugins page or the CLI — and understand the approval gate that keeps plugin code from running until you say so.
search: install plugin uninstall enable disable approve permissions manage plugins ciarenplugin marketplace explore
---

# Installing & Managing Plugins

This page is the **user's** guide to the plugin lifecycle: getting a plugin onto
your machine, approving it, and removing it again. To *build* a plugin, see
[Build Your First Plugin](/plugins/first-plugin).

Everything here is available two ways — the **Plugins page** in the app
(<code>/plugins</code>) and the <code>ciaren plugin</code> CLI. Pick whichever fits;
they act on the same state.

::: warning Plugins run real code on your machine
A plugin is ordinary Python that runs with your account's access — it is **not
sandboxed**. Install only plugins from sources you trust and whose code you can
review. The permission list a plugin shows is a *heads-up*, not a security
boundary. See [Plugin Security & Permissions](/security/plugin-security).
:::

## The lifecycle at a glance

```
install ─▶ pending (needs approval) ─▶ approve ─▶ active
                                          │            │
                                    disable/enable ◀───┘
                                          │
                                     uninstall ─▶ gone
```

A freshly installed plugin is **never** loaded automatically. Its code stays
un-imported until you explicitly approve it — even a plugin that requests **zero**
permissions — because approving is really *"let this code run"*. This is the one
gate that protects you; the rest is convenience.

## Install a plugin

There are four ways a plugin gets onto your machine.

### 1. Upload a `.ciarenplugin` (Plugins page)

Click **Install plugin** on the Plugins page and pick a `.ciarenplugin` file. It
is verified (signature + integrity) before anything is written to disk, then lands
**pending** until you approve it.

### 2. From the Explore catalog

If a marketplace index is configured (`CIAREN_MARKETPLACE_INDEX`), the **Explore
plugins** section lists installable entries with their trust tier (earned by
verifying the artifact's signature, never copied from the catalog), license, the
Ciaren versions they support, and the pip dependencies they bring. **Install**
re-verifies the advertised digest against the artifact, then installs it — the
same gated path as an upload.

### 3. From the command line

```bash
ciaren plugin install ./acme.ciarenplugin            # verify + install
ciaren plugin install ./acme.ciarenplugin --trusted  # refuse unless signed by a trusted key
ciaren plugin list                                   # see what's installed
```

### 4. Drop-in directory (development)

Point `CIAREN_PLUGINS_DIR` at a folder of plugin directories, or drop one into
`~/.ciaren/plugins`. Great for local development — no packaging needed. These are
still gated: they appear as pending until you approve them.

## Approve, disable, and permissions

The Plugins page shows one compact card per plugin — name, version, status, and
the primary action right on the card (**Approve** for a pending plugin,
**Enable** for a disabled one). **Click a card to open its details**: the
permissions it requests and which you granted, the nodes it contributes, and its
manifest metadata — license, trust tier, compatible Ciaren versions, pip
dependencies, entry point, and install location. The remaining actions live in
that details view.

![Plugin details — a pending plugin with the approval warning, its contributed node, manifest metadata, and the Approve action](/screenshots/plugin-details.png)

| Action | Where | What it does |
|--------|-------|--------------|
| **Approve** | Card & details | Grants the requested permissions and lets the plugin's code load. A pending plugin becomes **active**. |
| **Disable** | Details | Stops loading the plugin on future startups. Its files stay on disk; re-enable any time. |
| **Enable** | Card & details | Re-loads a disabled plugin (re-applies its existing grants). |
| **Revoke** | Details | Withdraws permissions you granted. If it then lacks a required permission it drops back to pending and stops loading. |
| **Uninstall** | Details | Deletes the plugin's installed files after a confirmation (see below). |

From the CLI:

```bash
ciaren plugin enable  acme.hello
ciaren plugin disable acme.hello
```

Changes take effect **live** — the node catalog is rebuilt, so a plugin's nodes
appear in (or leave) the editor palette without a restart.

## Uninstall a plugin

Uninstalling **deletes the plugin's installed files** and forgets its saved state
(approval and permission grants). Its contributed nodes leave the palette
immediately; flows that use those nodes won't run until the plugin is reinstalled.

**Plugins page:** open the plugin's details, click **Uninstall**, and confirm
the destructive prompt.

**CLI:**

```bash
ciaren plugin uninstall acme.hello
```

::: tip Uninstall vs. Disable
**Uninstall** only applies to plugins installed into the managed directory
(`~/.ciaren/plugins`, or `CIAREN_PLUGIN_INSTALL_DIR`). A **drop-in** plugin (from
`CIAREN_PLUGINS_DIR`) or a **pip-installed** entry-point package has no managed
files to delete — the app shows **Disable** for those instead. Remove a drop-in by
deleting its folder, or a package with `pip uninstall`.
:::

## Trust badges

Each installed plugin shows how its package verified at install time — hover a
badge for a plain-language explanation of what it means:

- **Trusted** — a valid signature from a key you trust.
- **Untrusted key** — validly signed, but by a key not in your trusted set.
- **Unsigned** — no signature (allowed by default for community plugins).
- **Invalid signature** — tampered or a bad signature (installation is refused).

Reinstalling a plugin id under a **different** signing key (or downgrading from a
trusted signature) withdraws your approval automatically, so a swapped publisher
can't inherit the trust you gave the original. See
[Packaging & Distribution](/plugins/packaging-and-distribution) for the signing
model.

## Next steps

- **[Plugins Overview](/plugins/overview)** — every extension point
- **[Build Your First Plugin](/plugins/first-plugin)** — the 10-minute tutorial
- **[Plugin Security & Permissions](/security/plugin-security)** — the trust model
