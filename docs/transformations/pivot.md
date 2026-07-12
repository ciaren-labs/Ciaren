---
title: Pivot
search: pivot wide long reshape pivot_table index columns values aggfunc crosstab
description: Reshape long to wide, spreading a column's values into new columns
---

# Pivot — `pivot`

Reshape long → wide.

## Use cases

- Turn `month` rows into `Jan`/`Feb`/… columns of totals.
- Build a cross-tab of category × metric.

## What it does

Pivot spreads the **unique values** of one column (`columns`) out into new columns,
filling each cell by aggregating the `values` column for that row key.

<DataTransform
  transform="Pivot (index=region, columns=month, values=amount, aggfunc=sum)"
  :before='{
    "columns":["region","month","amount"],
    "rows":[
      ["North","Jan",100],["North","Feb",150],
      ["South","Jan",80],["South","Feb",200]
    ]
  }'
  :after='{
    "columns":["region","Jan","Feb"],
    "rows":[
      ["North",100,150],
      ["South",80,200]
    ]
  }'
  :highlight='["Jan","Feb"]'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `index` | string \| string[] | Yes | Row key(s) |
| `columns` | string | Yes | Column whose values become new columns |
| `values` | string | Yes | Column to aggregate into the cells |
| `aggfunc` | string | No | Aggregation (default `sum`): one of `sum`, `mean`, `min`, `max`, `median`, `first`, `last`, `count` — restricted to functions both the pandas and polars exports support |

## Generated Python code

```python
df_2 = df_1.pivot_table(index='region', columns='month', values='amount', aggfunc='sum').reset_index()
```

## Tips & common mistakes

- **`aggfunc` resolves collisions.** When multiple rows share the same
  index/column pair, they're combined with this function (sum, mean, count, …).
- New column names come from the **values** found in `columns` at run time.
- To go the other way (wide → long), use [Unpivot](./unpivot.md).

## See also

- [Unpivot](./unpivot.md) · [Group by + aggregate](./group-by-aggregate.md)
