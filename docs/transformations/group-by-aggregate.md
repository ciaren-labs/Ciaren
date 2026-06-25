---
title: Group by + aggregate
search: group by aggregate sum mean count min max median nunique std var first last
description: Group rows by columns and compute aggregates per group
---

# Group by + aggregate — `groupByAggregate`

Group rows and compute aggregates.

## Use cases

- Total sales per region, average order value per customer.
- Count distinct products per category (`nunique`).

## What it does

Collapses multiple rows that share the same group key(s) into a single summary row.
All non-grouped, non-aggregated columns are dropped from the result.

<DataTransform
  transform="Group By + Aggregate (group_by=region, sum amount, count order_id)"
  :before='{
    "columns":["region","amount","order_id"],
    "rows":[
      ["North",120,1001],["South",89,1002],
      ["North",210,1003],["South",42,1004]
    ]
  }'
  :after='{
    "columns":["region","amount","order_id"],
    "rows":[
      ["North",330,2],
      ["South",131,2]
    ]
  }'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `group_by` | string[] | Yes | Grouping columns |
| `aggregations` | object | Yes | `{ "col": "func" }` |

**Aggregation functions:** `sum`, `mean`, `count`, `min`, `max`, `median`,
`nunique`, `std`, `var`, `first`, `last`.

## Generated Python code

```python
df_2 = df_1.groupby(['region']).agg({'amount': 'sum'}).reset_index()
```

## Tips & common mistakes

- **The result has one row per group**; non-grouped, non-aggregated columns are
  dropped — list everything you need under `aggregations`.
- `count` counts non-null values in the column; `nunique` counts distinct values.
- To reshape grouped results into a matrix, use [Pivot](./pivot.md).

## See also

- [Pivot](./pivot.md) · [Window function](./window-function.md) · [Remove duplicates](./remove-duplicates.md)
