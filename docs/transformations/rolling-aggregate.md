---
title: Rolling aggregate
search: rolling moving average window mean sum std time series smoothing
description: Moving aggregate over a window of N rows
---

# Rolling aggregate — `rollingAggregate`

Compute a moving aggregate (mean, sum, min, max, std, median) over a window of N
rows, within an optional partition and order. Ideal for smoothing time series.

## Use cases

- A 7-day moving average of sales.
- A rolling sum of usage per customer (partitioned by customer).
- Rolling volatility (std) of a price series.

## What it does

Rows are ordered by the **order by** columns, then a window of `window` rows is
aggregated with the chosen function. With **partition by**, the window restarts
within each group. The original row order is preserved in the output.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `target` | string | Yes | Numeric column to aggregate |
| `function` | string | Yes | `mean`, `sum`, `min`, `max`, `std`, `median` |
| `window` | int | Yes | Number of rows per window (≥ 1) |
| `min_periods` | int | No | Min rows required; empty = full window |
| `order_by` | string[] | No | Order rows within the window (e.g. a date) |
| `partition_by` | string[] | No | Restart the window within each group |
| `descending` | boolean | No | Order descending |
| `new_column` | string | Yes | Name of the result column |

## Generated Python code

```python
df_2 = df_1.assign(sales_ma=lambda _d: _d.sort_values('date', kind='stable')['sales'].rolling(7).mean())
```

## Tips & common mistakes

- Set **min periods** to 1 to get partial windows at the start; otherwise the
  first `window − 1` rows are null.
- Always set **order by** for time series — otherwise the window follows input
  order, which may not be chronological.

## See also

- [Window function](./window-function.md) · [Row difference](./row-difference.md)
