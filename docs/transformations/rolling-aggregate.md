---
title: Calculate Rolling Aggregates over Row Windows
search: rolling moving average window mean sum std time series smoothing
description: Calculate Ciaren rolling aggregates over ordered row windows with optional groups and minimum samples. Compare generated pandas and Polars exports.
---

# Rolling aggregate — `rollingAggregate`

Compute a moving aggregate (mean, sum, min, max, std, median) over a window of N
rows, within an optional partition and order. Ideal for smoothing time series.

## Use cases

- A seven-row moving average of sales (seven days only with one row per day).
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

These exports add `sales_ma` using a mean over seven rows ordered by ascending `date`,
with no partition and the default full-window minimum. This is a seven-row window, not
seven calendar days. A window with fewer than seven non-null sales values produces null;
the output restores the original row order. The full export defines the input frame and
engine alias.

### pandas

```python
df_2 = df_1.assign(sales_ma=lambda _d: _d.sort_values('date', kind='stable')['sales'].rolling(7).mean())
```

### Polars

```python
_w = df_1.with_row_index('__rn__')
_w = _w.sort(by=['date'], descending=False)
df_2 = _w.with_columns(pl.col('sales').rolling_mean(window_size=7).alias('sales_ma')).sort('__rn__').drop('__rn__')
```

## Tips & common mistakes

- Set **min periods** to 1 to get partial windows at the start; otherwise the
  first `window − 1` rows are null. Missing target values can keep later windows
  below that required number of non-null observations.
- Always set **order by** for time series — otherwise the window follows input
  order, which may not be chronological.

## See also

- [Window function](./window-function.md) · [Row difference](./row-difference.md)
