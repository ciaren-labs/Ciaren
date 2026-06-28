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

## Execution

The node ships a `NodeRuntime` (`HelloGreetingRuntime`), so it runs end-to-end:
it executes in previews and runs and exports to Python code, exactly like a
built-in node. The runtime works on pandas; FlowFrame bridges it to the active
engine (polars/pandas) automatically.

## Signed `.ffplugin` package

A pre-built, **signed** package ships at
[`../dist/community.hello-0.1.0.ffplugin`](../dist/). It's signed with a throwaway
**demo** key (committed in [`../build_hello_ffplugin.py`](../build_hello_ffplugin.py)
so the artifact is reproducible — a real publisher keeps their key secret and uses
`flowframe plugin keygen`).

Trust the demo key, then verify and install:

```bash
export FLOWFRAME_TRUSTED_PLUGIN_KEYS='{"flowframe-demo": "b827f3795467a701b018a0d57ab5900af43669d3622340905559d86ae2ec4bdd"}'

flowframe plugin verify  examples/plugins/dist/community.hello-0.1.0.ffplugin   # -> trusted
flowframe plugin install examples/plugins/dist/community.hello-0.1.0.ffplugin --trusted
```

`--trusted` refuses anything not signed by a key you trust. Rebuild the package
after editing the plugin with:

```bash
python examples/plugins/build_hello_ffplugin.py
```

See [Packaging & Distribution](../../../docs/plugins/packaging-and-distribution.md)
for the full publisher workflow.
