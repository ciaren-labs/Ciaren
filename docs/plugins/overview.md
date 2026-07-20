---
title: Plugins Overview
description: Ciaren is plugin-first — nodes, connectors, storage, execution engines, exporters, validators, and AI capabilities are all extension points you can build, package, sign, and share.
search: plugins extensibility providers nodes connectors engines exporters validators ai marketplace ciarenplugin
---

# Plugins & Extensibility

Ciaren is **plugin-first**. Almost every capability — the nodes on the canvas,
the databases you connect to, the engine your flow runs on, the code it exports —
is defined as a **versioned provider contract** that a plugin can implement. A plugin
is a small Python package that depends only on the public plugin API
(`app.plugin_api`), never on Ciaren's internals.

That means the core stays lean and open, while the community can extend it
from the outside — without forking.

Ciaren's open core intentionally ships a focused set of built-in capabilities.
Long-tail connectors, SaaS-specific integrations, and organization-specific
workflow nodes should live as plugins maintained by their authors or community,
not as ever-growing core surface area.

:::tip In one sentence
If Ciaren doesn't do something you need, you can add it as a plugin — and ship
it as a portable, optionally **signed** package.
:::

## What you can extend

Each row below is a real interface in `app.plugin_api`. A single plugin can
implement one or several of them.

| Extension point | Provider contract | What a plugin can add |
|-----------------|-------------------|------------------------|
| **Nodes** | `NodeProvider` | New canvas nodes that run end-to-end — preview, run, and Python code export. Sidebar forms render from the node's `config_schema` |
| **Connectors** | `ConnectorProvider` | New database / API / storage sources and sinks, **with runtime behavior**: test, list tables/objects, and read/write through the SQL & storage nodes. Connection forms render from the connector's metadata + `config_schema` |
| **ML model types** | `ModelProvider` | New trainable model types that appear inside the core Train nodes' model picker and train/log/export through the core ML pipeline |
| **Storage** | `StorageProvider` | New object/file storage backends |
| **Execution engines** | `ExecutionProvider` | New dataframe engines beyond the built-in polars and pandas |
| **Exporters** | `ExporterProvider` | New code/artifact export targets (e.g. notebooks) |
| **Validators** | `ValidatorProvider` | New data-quality / contract checks |
| **AI capabilities** | `AIProvider` | Pipeline builders, debuggers, optimizers |
| **Authentication** | `AuthProvider` | New authentication methods |

Plugin **train nodes** get first-class ML support too: a node can declare typed
`model` output handles, persist fitted models through the host's MLflow-backed
**ModelStore**, and emit **model references** that the core Predict / Feature
Importance nodes consume — see [ML Model Plugins](/plugins/ml-model-plugins).

> **Status note.** The built-in catalog ships **nodes**, **connectors**,
> **storage**, the **polars / pandas** engines, and the ML **model catalog**;
> plugins can execute nodes, connectors, and model types end-to-end. The
> remaining contracts (engines beyond the defaults, custom exporters/validators,
> AI capabilities, and auth methods) are defined extension points designed for
> plugins — they are how Ciaren grows without bloating the core. The plugin API
> is versioned but still **alpha**: contracts may change between releases until
> 1.0.0 (a plugin declares the `api_version` it targets, and the loader rejects
> incompatible ones before import). Always check
> the [API reference](/api/catalog) for what the running instance currently
> exposes.

## How a plugin is discovered

Ciaren finds plugins two ways:

1. **Local directory** — point `CIAREN_PLUGINS_DIR` at a folder of plugins
   (great for development, no install needed).
2. **Installed package** — a plugin that declares the `ciaren.plugins` entry
   point is discovered automatically once `pip install`-ed.

Fresh installs also include a small **bundled Explore catalog** with the Hello
Plugin and MLP Classifier example packages. Bundled catalog entries are not
loaded automatically: they are shown as installable examples so users can try the
install and approval flow.
Set `CIAREN_MARKETPLACE_INDEX=none` to hide Explore, or point it at your own
marketplace JSON.

![Plugins page — no plugins installed, permissions warning banner, and the Explore catalog showing installable example plugins with trust tier and license](/screenshots/plugins.png)

Once installed and approved, plugins show what they contribute — nodes, ML model
types, connectors — with trust and signature badges:

![Plugins page with the MLP Classifier example installed — Active status and Trusted signature badges](/screenshots/plugins-installed-extensions.png)

![Plugin details — the MLP Classifier plugin's contributed node and ML model type, license, trust tier, compatibility, and install location](/screenshots/plugin-details-mlp.png)

```bash
# Develop against a local folder
export CIAREN_PLUGINS_DIR=/path/to/your/plugins
ciaren serve

# Inspect what's loaded
ciaren-plugin list
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
ciaren-plugin keygen
ciaren-plugin pack ./my-plugin ./my-plugin.ciarenplugin
ciaren-plugin sign ./my-plugin.ciarenplugin \
  --key <private_hex> --key-id acme-2026 --publisher acme

# Consumer: install only trusted, signed packages
ciaren-plugin install ./my-plugin.ciarenplugin --trusted
ciaren-plugin verify  ./my-plugin.ciarenplugin
```

See [Packaging & Distribution](/plugins/packaging-and-distribution) for the full
publisher workflow.

## Complete, runnable examples

Three example plugins live in the repository, shipped as pre-built **signed**
packages in [`examples/plugins/dist/`](https://github.com/ciaren-labs/Ciaren/tree/main/examples/plugins/dist)
and bundled into the Explore catalog so a fresh install lists them ready to install:

- **[Hello plugin](https://github.com/ciaren-labs/Ciaren/tree/main/examples/plugins/hello-node-plugin)** —
  the smallest node that runs end-to-end. Start here → [Build Your First Plugin](/plugins/first-plugin).
- **[Validator plugin](https://github.com/ciaren-labs/Ciaren/tree/main/examples/plugins/validator-plugin)** —
  a practical data-quality check: validates a column against a regex or allowed-value
  set and adds a boolean pass/fail column. Shows `config_schema` with `column`,
  `select`, `string`, and `string_list` fields — the editor renders the form
  automatically.
- **[MLP Classifier plugin](https://github.com/ciaren-labs/Ciaren/tree/main/examples/plugins/mlp-classifier-plugin)** —
  neural-network classification both ways: a **model type** inside the core Train
  Classifier picker, and a standalone **train node** that persists to MLflow and
  emits a typed model reference. Walk through it →
  [Build an Advanced Plugin](/plugins/advanced-plugin-sklearn) and
  [ML Model Plugins](/plugins/ml-model-plugins).

Reading plain HTTP APIs needs no plugin at all — that's the built-in
[REST API connector](/guide/connections#web-apis). Build a
[connector plugin](/plugins/connector-plugins) for sources beyond it.

## Where this is heading

These contracts are the foundation for a community ecosystem of nodes, connectors,
execution engines, exporters, AI assistants, templates, and integrations. The core
stays open and useful on its own; extensions install from the outside.

If you want Ciaren to support a new external system, start by building a plugin.
If the Plugin API blocks that work, open an issue for the SDK gap rather than a
request to add the system directly to core.

## Next steps

- **[Installing & Managing Plugins](/plugins/managing-plugins)** — install, approve, disable, and uninstall
- **[Build Your First Plugin](/plugins/first-plugin)** — a 10-minute, step-by-step tutorial
- **[Writing a Plugin](/plugins/writing-a-plugin)** — the full contract, events, and rules
- **[ML Model Plugins](/plugins/ml-model-plugins)** — model types, train nodes, and model references
- **[Connector Plugins](/plugins/connector-plugins)** — database/API/storage connectors with runtime behavior
- **[Packaging & Distribution](/plugins/packaging-and-distribution)** — package and sign
- **[Build an Advanced Plugin (scikit-learn)](/plugins/advanced-plugin-sklearn)** — hyperparameters, validation, and code export
- **[Plugin API Reference](/plugins/api-reference)** — every provider, spec, and method
- **[Plugin Manifest](/specs/plugin-manifest)** — the manifest schema
- **[Plugin Security & Permissions](/security/plugin-security)** — the trust model
- **[Catalog & Plugins API](/api/catalog)** — inspect what an instance exposes

---

**Built something useful?** Open a
[Discussion](https://github.com/ciaren-labs/Ciaren/discussions) to share it
with the community.
