---
title: Python transform
description: Run arbitrary Python code on a dataframe inside a flow node
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
it, and routes the returned dataframe to the next node in the graph. The original
dataframe is not modified in place — you must `return` the result.

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

No other imports are available by default. Import anything else with a standard
`import` statement inside the script.

## Syntax validation

The script is validated at **save time** — a syntax error becomes a clean 400
response rather than a runtime failure. The check wraps your script body in a
function definition and runs `compile()` on it, so indentation and `return`
placement are caught early.

## Generated Python code (pandas)

```python
def _ff_transform(df):
    # your script body — e.g.:
    df = df[df['amount'] > 0].copy()
    df['margin'] = df['revenue'] - df['cost']
    return df

df_2 = _ff_transform(df_1)
```

The polars export is identical in structure (the script body is inlined as-is;
`pl`/`polars` are in scope).

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
The script runs with the **same permissions as the FlowFrame server process** —
full access to the filesystem, network, and any installed packages. This is
intentional: FlowFrame is local-first and sandboxing would break legitimate use
cases (file access, custom library calls).

Only run scripts from sources you trust, and never expose the FlowFrame API
publicly without authentication when Python Transform nodes are in use.
:::

## Tips & common mistakes

- **You must `return` the dataframe.** Forgetting the `return` causes a runtime
  error: `pythonTransform: script returned None`. The preview will catch this
  before a full run.
- **The engine name is `pl`/`pd`, not `polars`/`pandas`** (though both names
  are available). Pick one and be consistent.
- **Do not call `.collect()` inside polars scripts** unless you know the frame
  is lazy — the engine handles materialization. For complex polars pipelines,
  the polars executor wraps this node's output automatically.
- For complex transformations that you'll reuse across flows, consider
  [contributing a new node](https://github.com/rodrigo-arenas/FlowFrame/blob/main/CONTRIBUTING.md)
  to the registry so it gains a proper config UI, validation, and test coverage.

## See also

- [Calculated column](./calculated-column.md) · [Conditional column](./conditional-column.md)
- [Window function](./window-function.md) · [Transformations overview](./overview.md)
