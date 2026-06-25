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
_w = df_1.reset_index(drop=True)
_w = _w.sort_values(by=['date'], ascending=[True], kind='stable')
_w = _w.assign(**{'running_total': _w.groupby(['region'], sort=False)['amount'].cumsum()})
df_2 = _w.sort_index().reset_index(drop=True)
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
