---
title: Window function
search: window function row_number rank dense_rank cumsum cumcount cummax cummin lag lead partition order analytics
description: Compute a window/analytics value into a new column, scoped to a partition and order
---

# Window function — `windowFunction`

Compute a window/analytics value into a new column, optionally scoped to a
partition and ordered within it. Row order is preserved; the result is added as a
new column.

## Use cases

- Rank rows within each group (top product per region).
- Running totals, cumulative max/min over an ordered key.
- Compare a row to the previous/next one with `lag`/`lead`.

## What it does

A window function adds a **new column** computed from a window of rows — scoped to a
partition (group) and ordered within it. The original row order is preserved; the
calculation happens internally and the result is added alongside the existing columns.

Below: `cumsum` partitioned by `region` and ordered by `date` adds a per-region
running total without collapsing rows.

<DataTransform
  transform="Window: cumsum (partition_by=region, order_by=date, target=amount) → running_total"
  :before='{
    "columns":["region","date","amount"],
    "rows":[
      ["North","2024-01-01",100],
      ["North","2024-01-02",150],
      ["South","2024-01-01",80],
      ["South","2024-01-02",200]
    ]
  }'
  :after='{
    "columns":["region","date","amount","running_total"],
    "rows":[
      ["North","2024-01-01",100,100],
      ["North","2024-01-02",150,250],
      ["South","2024-01-01",80,80],
      ["South","2024-01-02",200,280]
    ]
  }'
  :highlight='["running_total"]'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `function` | string | Yes | `row_number`, `rank`, `dense_rank`, `cumcount`, `cumsum`, `cummax`, `cummin`, `lag`, `lead` |
| `new_column` | string | Yes | Name of the column to add |
| `partition_by` | string[] | No | Restart the window within each group (empty = whole table) |
| `order_by` | string[] | Conditional | Row order within the window; required for `rank`/`dense_rank` |
| `target` | string | Conditional | Value column; required for `cumsum`/`cummax`/`cummin`/`lag`/`lead` |
| `offset` | int | No | Shift distance for `lag`/`lead` (default 1) |
| `descending` | bool | No | Order descending (default `false`) |

## Generated Python code

```python
# function: cumsum, partition_by: ['region'], order_by: ['date'], target: 'amount'
df_2 = df_1.assign(running_total=lambda _d: _d.sort_values('date', kind='stable').groupby('region', sort=False)['amount'].cumsum())
```

## Tips & common mistakes

- **Each function needs its own inputs:** ranking needs `order_by`; value
  functions (`cumsum`, `cummax`, `cummin`, `lag`, `lead`) need a `target`.
- `rank`/`dense_rank` rank by the **first** `order_by` column.
- For `lag`/`lead`, rows at the window edge with no neighbor are null.
- Use `partition_by` to restart the calculation per group; leave it empty to run
  across the whole table.

::: tip
Row order in the output is preserved — the window sorts internally and restores
the original order, so this node is safe to place anywhere.
:::

## See also

- [Group by + aggregate](./group-by-aggregate.md) · [Sort rows](./sort-rows.md)
