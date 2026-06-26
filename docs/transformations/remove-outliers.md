---
title: Remove outliers
search: remove outliers iqr zscore percentile drop clip threshold factor
description: Drop or clip outliers in numeric columns using IQR, z-score, or percentiles
---

# Remove outliers — `removeOutliers`

Drop or clip outliers in numeric columns.

## Use cases

- Strip data-entry spikes before averaging.
- Winsorize (clip) extreme values to a sane range instead of deleting rows.

## What it does

Computes per-column bounds (IQR, z-score, or percentile), then either **drops** rows
that fall outside the bounds or **clips** their values to the boundary.

<DataTransform
  transform="Remove outliers (columns=[age], method=iqr, action=drop, factor=1.5)"
  :before='{
    "columns":["name","age"],
    "rows":[["Alice",28],["Bob",250],["Carol",35],["Dave",-5],["Eve",42]]
  }'
  :after='{
    "columns":["name","age"],
    "rows":[["Alice",28],["Carol",35],["Eve",42]]
  }'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `columns` | string[] | Yes | Numeric columns to scan |
| `method` | string | No | `iqr` (default), `zscore`, or `percentile` |
| `action` | string | No | `drop` (default) or `clip` to the bounds |
| `factor` | float | No | IQR multiplier (default `1.5`) |
| `threshold` | float | No | z-score threshold (default `3.0`) |
| `lower` / `upper` | float | No | Percentile bounds (default `1.0` / `99.0`) |

Each method has its own parameter: `iqr` uses `factor`, `zscore` uses
`threshold`, `percentile` uses `lower`/`upper` (0–100).

## Generated Python code

```python
# method: iqr, action: drop
df_2 = df_1
for _col in ['amount']:
    s = df_2[_col]
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    df_2 = df_2[s.between(lo, hi) | s.isna()]
```

## Tips & common mistakes

- **`drop` removes rows; `clip` keeps them** and pulls outliers to the bound —
  choose based on whether row counts must stay stable.
- **Match the parameter to the method.** Setting `threshold` while using `iqr`
  has no effect.
- Inspect the effect with a [histogram](/guide/visualizations) on the node's
  output.

## See also

- [Round numbers](./round-numbers.md) · [Filter rows](./filter-rows.md) · [Visualizations](/guide/visualizations)
