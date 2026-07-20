# Validator Plugin — example Ciaren plugin

A practical data-quality plugin. It contributes a single catalog node
(`validator.checkColumn`) that validates a column's values against a rule and
adds a boolean pass/fail column.

## What it shows

- A `Plugin` that registers a `NodeProvider` (`ciaren_validator/plugin.py`).
- A `config_schema` with `column`, `select`, `string`, and `string_list` fields
  — the editor renders the form automatically, no frontend code needed.
- Two built-in validation rules: **regex** (pattern match) and **allowed_set**
  (value membership).
- A `validate_config` that rejects bad input before execution.
- `to_python_code` so the check exports to a runnable Python script.

## Validation rules

| Rule | Config keys | Behaviour |
|------|-------------|-----------|
| `regex` | `column`, `pattern` | Every value in the column must match the regular expression. |
| `allowed_set` | `column`, `allowed_values` | Every value must appear in the supplied list. |

Both rules add a boolean column (default name `passed`) that is `True` when the
row passes and `False` otherwise.

## Try it

**Local directory (no install):** point Ciaren at the parent directory:

```bash
export CIAREN_PLUGINS_DIR=/path/to/examples/plugins
ciaren serve
```

`GET /api/plugins` then lists `community.validator`, and `validator.checkColumn`
appears in `GET /api/catalog/nodes` under the **quality** category.

**Installed package:** `pip install .` inside this folder; the entry point is
then discovered without setting `CIAREN_PLUGINS_DIR`.

## Execution

The node ships a `NodeRuntime` (`_CheckColumnRuntime`), so it runs end-to-end:
it executes in previews and runs and exports to Python code, exactly like a
built-in node. The runtime works on pandas; Ciaren bridges it to the active
engine (polars/pandas) automatically.

## Signed `.ciarenplugin` package

A pre-built, **signed** package ships at
[`../dist/community.validator-0.1.0-alpha.1.ciarenplugin`](../dist/). It's
signed with a throwaway **demo** key (committed in
[`../build_validator_ciarenplugin.py`](../build_validator_ciarenplugin.py)
so the artifact is reproducible — a real publisher keeps their key secret and
uses `ciaren-plugin keygen`).

Trust the demo key, then verify and install:

```bash
export CIAREN_TRUSTED_PLUGIN_KEYS='{"ciaren-demo": "b827f3795467a701b018a0d57ab5900af43669d3622340905559d86ae2ec4bdd"}'

ciaren-plugin verify  examples/plugins/dist/community.validator-0.1.0-alpha.1.ciarenplugin   # -> trusted
ciaren-plugin install examples/plugins/dist/community.validator-0.1.0-alpha.1.ciarenplugin --trusted
```

`--trusted` refuses anything not signed by a key you trust. Rebuild the package
after editing the plugin with:

```bash
python examples/plugins/build_validator_ciarenplugin.py
```

See [Packaging & Distribution](../../../docs/plugins/packaging-and-distribution.md)
for the full publisher workflow.
