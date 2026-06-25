---
title: Fill nulls
search: fill nulls missing na fillna mean median mode min max zero ffill bfill strategy
description: Replace missing values using a constant or a computed strategy
---

# Fill nulls — `fillNulls`

Replace missing values using a strategy.

## Use cases

- Backfill a constant like `"Unknown"` for a missing category.
- Impute a numeric column with its mean/median so rows aren't lost.
- Carry the last known value forward (`ffill`) in a time series.

## What it does

Replaces nulls in the target columns without removing rows — unlike
[Drop nulls](./drop-nulls.md), every row survives.

<DataTransform
  transform="Fill nulls (strategy=constant, value=Unknown, columns=[region])"
  :before='{
    "columns":["order_id","region","amount"],
    "rows":[
      [1001,"North",120.5],[1002,null,89.0],[1003,"South",null],[1004,null,42.25]
    ]
  }'
  :after='{
    "columns":["order_id","region","amount"],
    "rows":[
      [1001,"North",120.5],[1002,"Unknown",89.0],[1003,"South",null],[1004,"Unknown",42.25]
    ]
  }'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `strategy` | string | No | `constant` (default), `mean`, `median`, `mode`, `min`, `max`, `zero`, `ffill`, `bfill` |
| `value` | any | Conditional | Required when `strategy` is `constant` |
| `columns` | string[] | No | Limit to these columns (otherwise all) |

The `mean`, `median`, `min`, and `max` strategies are computed per column from
the non-null values; `mode` uses the most frequent value; `ffill`/`bfill`
propagate the previous/next value.

## Generated Python code

```python
# strategy: "constant", value: "Unknown", columns: ["region"]
df_2 = df_1.assign(**{c: df_1[c].fillna('Unknown') for c in ['region']})
```

## Tips & common mistakes

- **A `value` is only needed for `constant`.** Computed strategies (mean, median,
  …) ignore it.
- **`mean`/`median` need numeric columns.** Restrict `columns` so the strategy
  only touches columns it applies to.

## See also

- [Drop nulls](./drop-nulls.md) · [Cast types](./cast-types.md)
