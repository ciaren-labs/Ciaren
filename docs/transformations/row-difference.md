---
title: Row difference
search: difference delta pct change growth rate diff consecutive rows
description: Difference or percent change between consecutive rows
---

# Row difference — `rowDifference`

Compute the difference (or percent change) between consecutive rows of a column,
within an optional partition and order. Great for deltas and growth rates.

## Use cases

- Day-over-day change in a metric.
- Percent growth between periods.
- Per-customer deltas (partitioned by customer).

## What it does

Rows are ordered by **order by**, then each value is compared against the value
`periods` rows earlier. `diff` returns the absolute difference; `pct_change`
returns the fractional change. With **partition by**, comparisons never cross a
group boundary. The original row order is preserved.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `target` | string | Yes | Numeric column to compare |
| `method` | string | No (default `diff`) | `diff` or `pct_change` |
| `periods` | int | No | Rows back to compare against (default 1) |
| `order_by` | string[] | No | Order rows first (e.g. a date) |
| `partition_by` | string[] | No | Compare only within each group |
| `descending` | boolean | No | Order descending |
| `new_column` | string | Yes | Name of the result column |

## Generated Python code

```python
df_2 = df_1.assign(delta=lambda _d: _d.sort_values('date', kind='stable').groupby('customer', sort=False)['amount'].diff())
```

## Tips & common mistakes

- The **first row of each partition** has no previous row, so its result is null.
- `pct_change` returns a fraction (`0.5` = +50%); multiply by 100 with a
  [Calculated column](./calculated-column.md) for a percentage.

## See also

- [Rolling aggregate](./rolling-aggregate.md) · [Window function](./window-function.md)
