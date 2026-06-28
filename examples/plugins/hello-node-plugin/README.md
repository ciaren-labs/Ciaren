# Hello Plugin — example FlowFrame plugin

The smallest possible FlowFrame plugin. It contributes a single catalog node
(`hello.greeting`) so you can see the full discovery → manifest → registry →
catalog pipeline working end to end.

## What it shows

- A `Plugin` that registers a `NodeProvider` (`flowframe_hello/plugin.py`).
- A manifest (`flowframe-plugin.json`) the loader validates **before** importing
  any plugin code.
- A `pyproject.toml` declaring the `flowframe.plugins` entry point, so an
  installed copy is discovered automatically.

The plugin depends only on the FlowFrame plugin contract (`app.plugin_api`,
publishing later as `flowframe-plugin-api`) — never on FlowFrame internals.

## Try it

**Local directory (no install):** point FlowFrame at the parent directory:

```bash
export FLOWFRAME_PLUGINS_DIR=/path/to/examples/plugins
flowframe serve
```

`GET /api/plugins` then lists `community.hello`, and `hello.greeting` appears in
`GET /api/catalog/nodes`.

**Installed package:** `pip install .` inside this folder; the entry point is then
discovered without setting `FLOWFRAME_PLUGINS_DIR`.

## Scope

In Phase 1 a plugin node appears in the catalog (so the UI can render it). Wiring
a plugin-supplied node into the **execution engine** is a later phase — this
provider returns no implementation.
