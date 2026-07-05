---
title: Date difference
search: date difference days hours between two dates duration elapsed
description: Difference between two date columns in a chosen unit
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

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `start_column` | string | Yes | The earlier date column |
| `end_column` | string | Yes | The later date column (result is end − start) |
| `unit` | string | No (default `days`) | `days`, `hours`, `minutes`, `seconds`, or `weeks` |
| `new_column` | string | Yes | Name of the result column |

## Generated Python code

```python
df_2 = df_1.assign(days_between=lambda _d: (pd.to_datetime(_d['ship_date'], errors='coerce') - pd.to_datetime(_d['order_date'], errors='coerce')).dt.total_seconds() / 86400)
```

## Tips & common mistakes

- The result is **end − start**, so a later start gives a negative number.
- If a column is plain text, this node parses it; for full control over the
  format use [Parse dates](./parse-dates.md) first.

## See also

- [Parse dates](./parse-dates.md) · [Extract date parts](./extract-date-parts.md)
