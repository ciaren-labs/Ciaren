# Which orders are ready to fulfill?

A discontinued product and a SKU missing from the catalog should **stay in the
order queue**, visibly flagged for review. An inner join would silently lose
the missing SKU. This example performs a left join, checks the joined status
with the [validator plugin contributed by @tusharui](https://github.com/ciaren-labs/Ciaren/pull/120),
and sorts the result by order ID. It writes data locally; it does not place or
fulfill actual orders.

## Run the exported code first

From this directory, with Python 3.12+ and [uv](https://docs.astral.sh/uv/),
run any of these. Each writes **audit.csv** in the working directory,
replacing a previous copy. The scripts are the actual editor exports,
not reimplementations; you need neither Ciaren, its database, nor the plugin.

```sh
uv run --no-project --isolated --with pandas==2.3.3 python exported/audit_pandas.py
uv run --no-project --isolated --with pandas==2.3.3 --with polars==1.41.2 --with pyarrow==24.0.0 python exported/audit_polars.py
uv run --no-project --isolated --with pandas==2.3.3 --with polars==1.41.2 --with pyarrow==24.0.0 python exported/audit_polars_lazy.py
```

The five rows and all six columns are in [expected.csv](expected.csv). Orders
**103** (retired item) and **104** (unknown SKU) are false; **101, 102, 105**
are true. The repeated CABLE SKU is intentional: two different orders must
survive. The catalog's unordered DOCK should not appear. CSV writers differ
in boolean capitalization, not in the typed values.

**What “standalone Polars” means here:** the reads, join, sort and output use
Polars. The plugin supplies a pandas implementation, inlined in the script;
conversion needs pandas and PyArrow. The lazy variant collects at the plugin
boundary and resumes a lazy plan afterward. It is not fully streaming or
Polars-only. The fixture has one catalog row per SKU; duplicate catalog keys
would multiply order lines. This is a catalog-status check, not an inventory
or stock-quantity check.

## Recreate it on the canvas

1. In a Ciaren source checkout, run from `backend/` (POSIX shell):

   ```sh
   export CIAREN_PLUGINS_DIR="$(cd ../examples/plugins && pwd)"
   uv run ciaren serve
   ```

   For source development, start the [frontend](../../CONTRIBUTING.md) too if
   the editor is not bundled. On PowerShell set
   `$env:CIAREN_PLUGINS_DIR = (Resolve-Path ../examples/plugins).Path`.
   Under **Plugins**, review **Validator Plugin** (`community.validator`)
   and choose **Approve** to load it before importing the flow.
2. Under **Datasets**, choose the **Default** project and upload both
   [orders.csv](orders.csv) and [catalog.csv](catalog.csv) with their original
   names. The built-in **Demo** project has a different `orders.csv`.
   Under **Flows → Import**, import [orders-audit.flow.json](orders-audit.flow.json)
   into the **Default** project.
3. Open **Order lines** and select `orders.csv`. Open **Product catalog** and
   select `catalog.csv`. Portable flow files intentionally omit local dataset IDs.
4. Choose **Run**. On the run page, select the **Fulfillment audit** output
   node and choose **Download output** to inspect all five orders. Return to
   the flow editor and choose **Export**. Compare the code in the
   **pandas**, **polars** and **polars (lazy)** tabs with the
   [standalone scripts](exported/). Copy an export beside the two CSVs or
   run it from their directory.

## Reproduce the parity test

From `backend/`, in a POSIX shell, create fresh, independent export environments.
The application and plugins run in the backend environment only.

```sh
uv sync --frozen
work=$(mktemp -d)
uv venv "$work/pandas"
uv pip install --python "$work/pandas/bin/python" pandas==2.3.3
uv venv "$work/polars"
uv pip install --python "$work/polars/bin/python" pandas==2.3.3 polars==1.41.2 pyarrow==24.0.0
CIAREN_DEMO_PANDAS_PYTHON="$work/pandas/bin/python" CIAREN_DEMO_POLARS_PYTHON="$work/polars/bin/python" \
  uv run --no-sync pytest tests/api/test_orders_audit_example.py -o addopts= -q
```

The test approves the real plugin, imports the shared JSON through the editor's
HTTP endpoint, uploads and binds the sample files, runs the pandas and
Polars engines, downloads their results, and requests the Python export.
It checks all three scripts against their checked-in copies, runs each in a
fresh directory with only the two inputs, and compares typed values, column
order, row order and null positions with both the actual run and the expected
table. Lazy Polars is an export target, not a third app engine.
