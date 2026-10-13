---
title: Calculate Elapsed Time between Date Columns
search: date difference days hours between two dates duration elapsed
description:
  Calculate elapsed time between Ciaren date columns in days, hours, minutes,
  seconds or weeks. Handle negative and null durations; compare both exports.
---

# Date difference — `dateDifference`

Compute the difference between two date columns (end − start) as a number, in a
chosen unit.

## Use cases

- Days between `order_date` and `ship_date`.
- Customer age in years from `birth_date` to today (with a constant column).
- Hours elapsed between two timestamps.

## What it does

Both columns are parsed to datetimes, then `end − start` is converted to the
chosen unit and written to a new numeric column. The result is fractional (e.g.
`1.5` days). Unparseable dates become null instead of failing the run.

## Configuration

| Config key     | Type   | Required            | Description                                       |
| -------------- | ------ | ------------------- | ------------------------------------------------- |
| `start_column` | string | Yes                 | The earlier date column                           |
| `end_column`   | string | Yes                 | The later date column (result is end − start)     |
| `unit`         | string | No (default `days`) | `days`, `hours`, `minutes`, `seconds`, or `weeks` |
| `new_column`   | string | Yes                 | Name of the result column                         |

## Generated Python code

These exports add `days_between` as `ship_date - order_date` in days, preserving
all input fields. Durations can be fractional or negative; invalid or missing
dates produce null.

### pandas

```python
df_2 = df_1.assign(days_between=lambda _d: (pd.to_datetime(_d['ship_date'], errors='coerce') - pd.to_datetime(_d['order_date'], errors='coerce')).dt.total_seconds() / 86400)
```

### Polars

```python
_sch = df_1.collect_schema()
_start = (pl.col('order_date').str.to_datetime(strict=False) if _sch['order_date'] == pl.Utf8 else pl.col('order_date').cast(pl.Datetime, strict=False))
_end = (pl.col('ship_date').str.to_datetime(strict=False) if _sch['ship_date'] == pl.Utf8 else pl.col('ship_date').cast(pl.Datetime, strict=False))
df_2 = df_1.with_columns(((_end - _start).dt.total_seconds() / 86400).alias('days_between'))
```

## Tips & common mistakes

- The result is **end − start**, so a later start gives a negative number.
- If a column is plain text, this node parses it; for full control over the
  format use [Parse dates](./parse-dates.md) first.

## See also

- [Parse dates](./parse-dates.md) ·
  [Extract date parts](./extract-date-parts.md)
