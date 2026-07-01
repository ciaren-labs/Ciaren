---
title: Plugins Overview
description: Ciaren is plugin-first — nodes, connectors, storage, execution engines, exporters, validators, and AI capabilities are all extension points you can build, package, sign, and share.
search: plugins extensibility providers nodes connectors engines exporters validators ai marketplace ciarenplugin
---

# Plugins & Extensibility

Ciaren is **plugin-first**. Almost every capability — the nodes on the canvas,
the databases you connect to, the engine your flow runs on, the code it exports —
is defined as a **stable provider contract** that a plugin can implement. A plugin
is a small Python package that depends only on the public plugin API
(`app.plugin_api`), never on Ciaren's internals.

That means the core stays lean and open, while the community can extend it
from the outside — without forking.

:::tip In one sentence
If Ciaren doesn't do something you need, you can add it as a plugin — and ship
it as a portable, optionally **signed** package.
:::

## What you can extend

Each row below is a real interface in `app.plugin_api`. A single plugin can
implement one or several of them.

| Extension point | Provider contract | What a plugin can add |
|-----------------|-------------------|------------------------|
| **Nodes** | `NodeProvider` | New canvas nodes that run end-to-end — preview, run, and Python code export |
| **Connectors** | `ConnectorProvider` | New database / API sources and sinks |
| **Storage** | `StorageProvider` | New object/file storage backends |
| **Execution engines** | `ExecutionProvider` | New dataframe engines beyond the built-in polars and pandas |
| **Exporters** | `ExporterProvider` | New code/artifact export targets (e.g. notebooks) |
| **Validators** | `ValidatorProvider` | New data-quality / contract checks |
| **AI capabilities** | `AIProvider` | Pipeline builders, debuggers, optimizers |
| **Authentication** | `AuthProvider` | New authentication methods |

> **Status note.** The built-in catalog ships **nodes**, **connectors**,
> **storage**, and the **polars / pandas** engines. The remaining contracts
> (engines beyond the defaults, custom exporters/validators, AI capabilities, and
> auth methods) are stable extension points designed for plugins — they are how
> Ciaren grows without bloating the core. Always check the
> [API reference](/api/catalog) for what the running instance currently exposes.

## How a plugin is discovered

Ciaren finds plugins two ways:

1. **Local directory** — point `CIAREN_PLUGINS_DIR` at a folder of plugins
   (great for development, no install needed).
2. **Installed package** — a plugin that declares the `ciaren.plugins` entry
   point is discovered automatically once `pip install`-ed.

Fresh installs also include a small **bundled Explore catalog** with a Hello
Plugin package. Bundled catalog entries are not loaded automatically: they are
shown as installable examples so users can try the install and approval flow.
Set `CIAREN_MARKETPLACE_INDEX=none` to hide Explore, or point it at your own
marketplace JSON.

```bash
# Develop against a local folder
export CIAREN_PLUGINS_DIR=/path/to/your/plugins
ciaren serve

# Inspect what's loaded
ciaren plugin list
```

Disabled plugins and plugins with ungranted permissions are **not imported** until
you approve them — code never runs behind your back. See
[Plugin Security & Permissions](/security/plugin-security).

## Packaging & signing

Plugins can be packaged as portable `.ciarenplugin` files and **cryptographically
signed** (Ed25519). Installing with `--trusted` refuses any package not signed by
a key you trust.

```bash
# Publisher: generate a key, package, and sign
ciaren plugin keygen
ciaren plugin pack ./my-plugin ./my-plugin.ciarenplugin
ciaren plugin sign ./my-plugin.ciarenplugin

# Consumer: install only trusted, signed packages
ciaren plugin install ./my-plugin.ciarenplugin --trusted
ciaren plugin verify  ./my-plugin.ciarenplugin
```

See [Packaging & Distribution](/plugins/packaging-and-distribution) for the full
publisher workflow.

## A complete, runnable example

The smallest possible plugin — it adds one catalog node that runs end-to-end —
lives in the repository at
[`examples/plugins/hello-node-plugin/`](https://github.com/ciaren-labs/Ciaren/tree/main/examples/plugins/hello-node-plugin),
with a pre-built **signed** package in
[`examples/plugins/dist/`](https://github.com/ciaren-labs/Ciaren/tree/main/examples/plugins/dist).

## Where this is heading

These contracts are the foundation for a community ecosystem of nodes, connectors,
execution engines, exporters, AI assistants, templates, and integrations. The core
stays open and useful on its own; extensions install from the outside.

## Next steps

- **[Build Your First Plugin](/plugins/first-plugin)** — a 10-minute, step-by-step tutorial
- **[Writing a Plugin](/plugins/writing-a-plugin)** — the full contract, events, and rules
- **[Plugin API Reference](/plugins/api-reference)** — every provider, spec, and method
- **[Packaging & Distribution](/plugins/packaging-and-distribution)** — package and sign
- **[Plugin Manifest](/specs/plugin-manifest)** — the manifest schema
- **[Plugin Security & Permissions](/security/plugin-security)** — the trust model
- **[Catalog & Plugins API](/api/catalog)** — inspect what an instance exposes

---

**Built something useful?** Open a
[Discussion](https://github.com/ciaren-labs/Ciaren/discussions) to share it
with the community.
