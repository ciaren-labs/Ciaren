---
title: Write Custom Python Transforms in Both Engines
description: Write custom Ciaren dataframe transforms with explicit returns. Compare runnable pandas and Polars exports, engine names and script limitations.
search: python transform script custom code exec pandas polars escape hatch
---

# Python transform — `pythonTransform`

Run arbitrary Python code on the input dataframe and return a transformed one.

## Use cases

- One-off transformations too complex or unusual to express with built-in nodes.
- Applying a custom business rule that mixes multiple pandas/polars operations
  in a single logical step.
- Prototyping a transformation before it becomes a permanent node in the
  registry.
- Using an installed library (`scikit-learn`, `faker`, a proprietary package)
  directly inside the pipeline.

## What it does

You write the **body** of a `transform(df)` function. The node wraps it, calls
it, and routes the returned dataframe to the next node in the graph. You must
`return` the result. The function receives the incoming frame; with pandas,
copy it before assignment when you want to avoid modifying it in place.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `script` | string | Yes | Body of `def transform(df): …` — must contain a `return` statement |

## Pre-injected names

The script runs in a namespace with the dataframe engine already imported:

| Engine | Available names |
| --- | --- |
| polars (default) | `pl`, `polars` |
| pandas | `pd`, `pandas` |

These aliases are available inside a Ciaren run. Portable exports import `pd`
or `pl`; use those names in the body, or import another name explicitly. Import
other installed libraries with a standard `import` statement inside the script.
Strict mode permits data and computation imports such as `math` and `numpy`,
while blocking known capability imports such as `os`, `subprocess` and `socket`.

## Syntax validation

The node checks syntax before **preview and execution**. It wraps your script
body in a function definition and runs `compile()` on it, so invalid indentation
and `return` placement are caught before the body runs. Preview reports a syntax
error as a validation error (HTTP 400).

Saving a flow does not perform this node syntax check. Preview the node after
editing; a successful save alone does not mean the Python body is valid.

## Generated Python code

These separate File Input → Python Transform → File Output flows read `source.csv` and
write `result.parquet`. Both keep `amount > 0` and add `margin = revenue - cost`; zero,
negative and missing amounts are excluded. The pandas body copies the selected rows
before assignment. Choose the body for your flow engine: Ciaren embeds it as written and
does not translate pandas operations into Polars. Put the original CSV beside the script
and run in an environment with Ciaren and its file-format dependencies installed. These
complete exports use `pd` or `pl` and eager frames.

### pandas

#### Transform

```python
import pandas as pd

df_source = pd.read_csv('source.csv')
def _transform(df):
    df = df[df['amount'] > 0].copy()
    df['margin'] = df['revenue'] - df['cost']
    return df

df_source = _transform(df_source)
df_source.to_parquet('result.parquet', index=False)
```

### Polars

#### Transform

```python
import polars as pl
import pandas as pd

df_source = pl.read_csv('source.csv')
def _transform(df):
    df = df.filter(pl.col("amount") > 0)
    df = df.with_columns((pl.col("revenue") - pl.col("cost")).alias("margin"))
    return df

df_source = _transform(df_source)
df_source.write_parquet('result.parquet')
```

## Examples

**Filter and add a column (polars):**

```python
df = df.filter(pl.col("amount") > 0)
df = df.with_columns(
    (pl.col("revenue") - pl.col("cost")).alias("margin")
)
return df
```

**Call an installed library (pandas):**

```python
from sklearn.preprocessing import StandardScaler
import pandas as pd

scaler = StandardScaler()
df[['price_scaled']] = scaler.fit_transform(df[['price']])
return df
```

**Multi-step string cleaning (pandas):**

```python
df = df.copy()
df['email'] = df['email'].str.strip().str.lower()
df = df[df['email'].str.contains('@', na=False)]
return df
```

## Security note

::: warning No sandboxing
The script runs with the **same permissions as the Ciaren server process** —
full access to the filesystem, network, and any installed packages. This is
intentional: Ciaren is local-first and sandboxing would break legitimate use
cases (file access, custom library calls).

Only run scripts from sources you trust, and never expose the Ciaren API
publicly without authentication when Python Transform nodes are in use.
:::

Setting `CIAREN_PYTHON_TRANSFORM_STRICT=true` adds two opt-in, defense-in-depth
checks: an AST scan that rejects dangerous imports (`os`, `sys`, `subprocess`,
`socket`, `ctypes`, `importlib`, …), exec-style builtins, and dunder-attribute
traversal; and a restricted `__builtins__` at execution time with `open` and
`eval` removed. Import statements use a guarded importer that enforces the
same module policy as the AST scan; direct calls to `__import__` are rejected
by the scan. It's off by default so existing scripts
(e.g. `import numpy`) keep working, and it is **not a sandbox** — a determined
attacker can still find a bypass — so the real controls remain network auth
and running Ciaren as an unprivileged user.

This setting protects validation and execution inside Ciaren. The exported
Python file contains your script body and normal imports; it does not include
the server's AST checks or restricted builtins. Review exported code before
running it under your own account.

## Tips & common mistakes

- **You must `return` the dataframe.** Forgetting the `return` causes a runtime
  error: `pythonTransform: script returned None`. The preview will catch this
  before a full run.
- **Use the selected engine's operations.** `pd` and `pl` refer to different
  dataframe libraries. Switching engines does not translate a saved body; use
  `pd` for pandas and `pl` for Polars in scripts you also plan to export.
- **Do not call `.collect()` inside Polars scripts** unless you know the frame
  is lazy. In lazy Polars exports, the exporter materializes this node's inputs
  and returns its result to the lazy plan.
- For complex transformations that you'll reuse across flows, consider
  [contributing a new node](https://github.com/ciaren-labs/Ciaren/blob/main/CONTRIBUTING.md)
  to the registry so it gains a proper config UI, validation, and test coverage.

## See also

- [Calculated column](./calculated-column.md) · [Conditional column](./conditional-column.md)
- [Window function](./window-function.md) · [Transformations overview](./overview.md)
