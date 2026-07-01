# Hello Plugin — example Ciaren plugin

The smallest possible Ciaren plugin. It contributes a single catalog node
(`hello.greeting`) so you can see the full discovery → manifest → registry →
catalog pipeline working end to end.

## What it shows

- A `Plugin` that registers a `NodeProvider` (`ciaren_hello/plugin.py`).
- A manifest (`ciaren-plugin.json`) the loader validates **before** importing
  any plugin code.
- A `pyproject.toml` declaring the `ciaren.plugins` entry point, so an
  installed copy is discovered automatically.

The plugin depends only on the Ciaren plugin contract (`app.plugin_api`,
publishing later as `ciaren-plugin-api`) — never on Ciaren internals.

## Try it

**Local directory (no install):** point Ciaren at the parent directory:

```bash
export CIAREN_PLUGINS_DIR=/path/to/examples/plugins
ciaren serve
```

`GET /api/plugins` then lists `community.hello`, and `hello.greeting` appears in
`GET /api/catalog/nodes`.

**Installed package:** `pip install .` inside this folder; the entry point is then
discovered without setting `CIAREN_PLUGINS_DIR`.

## Execution

The node ships a `NodeRuntime` (`HelloGreetingRuntime`), so it runs end-to-end:
it executes in previews and runs and exports to Python code, exactly like a
built-in node. The runtime works on pandas; Ciaren bridges it to the active
engine (polars/pandas) automatically.

## Signed `.ciarenplugin` package

A pre-built, **signed** package ships at
[`../dist/community.hello-0.1.0-alpha.1.ciarenplugin`](../dist/). It's signed with a throwaway
**demo** key (committed in [`../build_hello_ciarenplugin.py`](../build_hello_ciarenplugin.py)
so the artifact is reproducible — a real publisher keeps their key secret and uses
`ciaren plugin keygen`).

Trust the demo key, then verify and install:

```bash
export CIAREN_TRUSTED_PLUGIN_KEYS='{"ciaren-demo": "b827f3795467a701b018a0d57ab5900af43669d3622340905559d86ae2ec4bdd"}'

ciaren plugin verify  examples/plugins/dist/community.hello-0.1.0-alpha.1.ciarenplugin   # -> trusted
ciaren plugin install examples/plugins/dist/community.hello-0.1.0-alpha.1.ciarenplugin --trusted
```

`--trusted` refuses anything not signed by a key you trust. Rebuild the package
after editing the plugin with:

```bash
python examples/plugins/build_hello_ciarenplugin.py
```

See [Packaging & Distribution](../../../docs/plugins/packaging-and-distribution.md)
for the full publisher workflow.
