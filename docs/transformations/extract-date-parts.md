---
title: Extract date parts
search: extract date parts year month day weekday hour datetime components
description: Add columns for parts of a date/datetime column
---

# Extract date parts — `extractDateParts`

Add columns for parts of a date/datetime column.

## Use cases

- Add `year`/`month` columns to group sales by period.
- Pull `weekday` or `hour` for time-of-week analysis.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `column` | string | Yes | Date/datetime column |
| `parts` | string[] | Yes | Any of `year`, `month`, `day`, `weekday`, `hour` |

Each part becomes a new column named `<column>_<part>` (e.g. `ordered_at_year`).

## Generated Python code

```python
_dt = pd.to_datetime(df_1['ordered_at'])
df_2 = df_1.assign(**{'ordered_at_year': _dt.dt.year, 'ordered_at_month': _dt.dt.month})
```

## Tips & common mistakes

- **`weekday` is Monday=0 … Sunday=6** (consistent across pandas and polars
  exports — verified by the parity tests).
- If the source is text, [Parse dates](./parse-dates.md) or
  [Cast types](./cast-types.md) → `datetime` first; this node also parses on the
  fly but an explicit parse is clearer.

## See also

- [Parse dates](./parse-dates.md) · [Cast types](./cast-types.md)
