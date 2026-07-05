---
title: Parse dates
search: parse dates to_datetime format errors coerce strptime text datetime
description: Parse text columns into real datetimes so date operations work
---

# Parse dates — `parseDates`

Parse text columns into real datetimes so date operations (sorting, Extract date
parts) work. Complements [Extract date parts](./extract-date-parts.md) (which goes
the other way: datetime → parts).

## Use cases

- Convert `"2021-01-02"` strings into datetimes before sorting or grouping by
  month.
- Clean a messy date column, sending unparseable values to null.

## What it does

Converts each matching text value to a `datetime`. Unparseable strings become `null`
when `errors=coerce` (the default).

<DataTransform
  transform="Parse dates (columns=[ordered_at], errors=coerce)"
  :before='{
    "columns":["id","ordered_at"],
    "rows":[[1,"2024-01-15"],[2,"2024-02-20"],[3,"bad date"]]
  }'
  :after='{
    "columns":["id","ordered_at"],
    "rows":[[1,"2024-01-15 00:00:00"],[2,"2024-02-20 00:00:00"],[3,null]]
  }'
  :highlight='["ordered_at"]'
/>

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `columns` | string[] | Yes | Text columns to parse |
| `format` | string | No | strptime format (e.g. `%d-%m-%Y`); empty = auto-detect |
| `errors` | string | No | `coerce` (default, bad values → null) or `raise` |

## Generated Python code

```python
df_2 = df_1.assign(ordered_at=lambda _d: pd.to_datetime(_d['ordered_at'], errors='coerce'))
```

## Tips & common mistakes

- **Give a `format` for ambiguous dates** (e.g. `%d-%m-%Y` vs `%m-%d-%Y`) so day
  and month aren't swapped.
- **`coerce` is the safe default** — it won't fail a run on one bad value. Use
  `raise` when you want to catch unexpected formats early.

## See also

- [Extract date parts](./extract-date-parts.md) · [Change types](./cast-types.md) · [Sort rows](./sort-rows.md)
